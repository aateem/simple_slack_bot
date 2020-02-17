import json
import logging

from . import utils

logger = logging.getLogger(__name__)


def chat_message(event):
    return (
        event.get("type") == "message"
        and event.get("channel_type") == "channel"
        and _get_bot_user_id() not in event.get("text")
    )


def process_chat_message(event):
    channel = event.get("channel")

    if utils.redis_client.exists(channel):
        chan_conf = json.loads(utils.redis_client.get(channel))
        phrases_users = chan_conf.get("phrases", {})

        for phrase, users in phrases_users.items():
            if phrase in event.get("text", ""):
                _notify_users(
                    user_ids=users, channel_long_id=chan_conf["long_id"], phrase=phrase,
                )


def _notify_users(user_ids, channel_long_id, phrase):
    msg = utils.NOTIFY_USER_MSG.format(utils.QUOTE_PREFIX, phrase, channel_long_id)
    for uid in user_ids:
        dm_channel = _get_dm_channel_id(uid)
        _chat_post_message(channel=dm_channel, message=msg)


def _get_dm_channel_id(user_id):
    user_conf = json.loads(utils.redis_client.get(user_id))
    dm_channel_id = user_conf.get("dm_channel_id")
    if not dm_channel_id:
        response = utils.web_api_client.conversations_open(users=[user_id])
        if not response.get("ok", False):
            logger.error(
                "Failed to open DM channel with user {}. "
                "Returned error: {}".format(user_id, response.get("error"))
            )
            return

        dm_channel_id = response.get("channel", {}).get("id")
        user_conf["dm_channel_id"] = dm_channel_id
        utils.redis_client.set(user_id, json.dumps(user_conf))

    return dm_channel_id


def message_for_app(event):
    event_type = event.get("type")
    return event_type == "app_mention" or (
        event_type == "message" and event.get("channel_type") == "im" and _check_bot_im(event)
    )


def _get_bot_user_id():
    if utils.redis_client.exists("bot_user_id"):
        bot_user_id = utils.redis_client.get("bot_user_id").decode("utf-8")
    else:
        response = utils.web_api_client.auth_test()
        if not response.get("ok", False):
            logger.error(
                "Auth test for bot user failed. Returned error: {}".format(response.get("error"))
            )
            return None
        bot_user_id = response.get("user_id")
        utils.redis_client.set("bot_user_id", bot_user_id)

    return bot_user_id


def _check_bot_im(event):
    response = utils.web_api_client.conversations_members(channel=event.get("channel"))
    if not response.get("ok", False):
        logger.error(
            "Failed to get conversation members for IM chat. Returned error: {}".format(
                response["error"]
            )
        )

    return _get_bot_user_id() in response.get("members")


def process_app_message(event):
    message = event.get("text", "")

    phrases, channels = utils.split_message(message)
    if phrases and channels:
        _update_user_config(event, phrases, channels)
    else:
        if "purge config" in message:
            _purge_user_config(event)
        elif "get config" in message:
            _get_user_config(event)
        else:
            _chat_post_message(event.get("channel"), utils.HELP_MESSAGE)


def _get_user_config(event):
    user = event.get("user")
    if not user:
        logger.warning("User is not present in incomming event, could not retrieve config")
        return
    if utils.redis_client.exists(user):
        user_conf = json.loads(utils.redis_client.get(user))
        _ack_config_get_msg(user_conf["phrases"], user_conf["channels"], event.get("channel"))
    else:
        _chat_post_message(event.get("channel"), message="You don't have any configuration!")


def _ack_config_get_msg(phrases, channels, chan_post, base_msg=None):
    msg = utils.DISPLAY_CONF_MESSAGE.format(
        "\n".join(phrase for phrase in phrases), " ".join(channels)
    )
    if base_msg:
        msg = base_msg + msg
    _chat_post_message(chan_post, msg)


def _purge_user_config(event):
    user_id = event.get("user")

    if utils.redis_client.exists(user_id):
        utils.redis_client.delete(user_id)

    for chan_id in utils.redis_client.scan_iter(match="C*"):
        chan_conf = json.loads(utils.redis_client.get(chan_id))
        phrases_users = chan_conf.get("phrases", {})

        stale_phrases = []
        for phrase, users in phrases_users.items():
            if user_id in users:
                users.remove(user_id)
                if not users:
                    stale_phrases.append(phrase)
        for phrase in stale_phrases:
            del phrases_users[phrase]

        utils.redis_client.set(chan_id, json.dumps(chan_conf))

    _chat_post_message(channel=event.get("channel"), message="I have purged your configuration!")


def _update_user_config(event, phrases, channels):
    user = event.get("user")
    if not user:
        logger.error("User is not present in the message description, cannot set the config")
        return

    user_conf = {"phrases": phrases, "channels": channels}
    utils.redis_client.set(user, json.dumps(user_conf))

    # stip phrases of quotes representation symbols
    chan_phrases = [phrase.strip(utils.QUOTE_PREFIX) for phrase in phrases]

    for chan in channels:
        chan_id = chan.split("|")[0].strip("<").strip("#")

        if not utils.redis_client.exists(chan_id):
            chan_conf = {
                "long_id": chan,
                "phrases": {phrase: [user] for phrase in chan_phrases},
            }
        else:
            chan_conf = json.loads(utils.redis_client.get(chan_id))
            for phrase in chan_phrases:
                phrase_users = chan_conf["phrases"].setdefault(phrase, [])
                if user not in phrase_users:
                    phrase_users.append(user)
        utils.redis_client.set(chan_id, json.dumps(chan_conf))

    _ack_config_get_msg(
        phrases, channels, event.get("channel"), base_msg="Updated your configuration!\n"
    )


def _chat_post_message(channel, message):
    response = utils.web_api_client.chat_postMessage(channel=channel, text=message)
    if not response.get("ok", True):
        logger.error(
            "Send message operation for channel {} unsuccessful."
            "Returned error msg: {}".format(channel, response["error"])
        )
