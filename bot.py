import json
import logging
import os

from flask import Flask, request, jsonify
import redis
from slack import WebClient

from process_text import get_app_message, split_message, HELP_MESSAGE, ACK_MESSAGE, QUOTE_PREFIX

logging.basicConfig(level=os.environ.get("APP_LOGGING_LEVEL", logging.INFO))

app = Flask(__name__)


@app.route("/config")
def get_config():
    r_client = redis.Redis(
        host=os.environ["REDIS_HOST"],
        port=os.environ["REDIS_PORT"],
        db=os.environ["REDIS_CONFIG_DB"],
    )
    users = {}
    channels = {}
    for user_id in r_client.scan_iter(match="U*"):
        users[str(user_id)] = json.loads(r_client.get(user_id))
    for chan_id in r_client.scan_iter(match="C*"):
        channels[str(chan_id)] = json.loads(r_client.get(chan_id))
    return jsonify({"users": users, "channels": channels})


@app.route("/ping")
def ping():
    return "I'm alive and fine, thank you very much! How're ye doing?!\n"


@app.route("/event-listener", methods=["POST"])
def event_listener():
    data = request.get_json()

    # handle the Slack's Event API request URL
    # registration request
    if data.get("type") == "url_verification":
        return data.get("challenge", "")

    if data.get("type") == "event_callback":
        event = data.get("event", {})

        if message_for_app(event):
            process_app_message(event)

        if chat_message(event):
            process_chat_message(event)

    return ("", 200)


def chat_message(event):
    return event.get("type") == "message" and event.get("channel_type") == "channel"


def process_chat_message(event):
    channel = event.get("channel")

    r_client = redis.Redis(
        host=os.environ["REDIS_HOST"],
        port=os.environ["REDIS_PORT"],
        db=os.environ["REDIS_CONFIG_DB"],
    )

    if r_client.exists(channel):
        chan_conf = json.loads(r_client.get(channel))
        phrases_users = chan_conf.get("phrases", {})

        for phrase, users in phrases_users.items():
            if phrase in event.get("text", ""):
                _notify_users(
                    user_ids=users, channel_long_id=chan_conf["long_id"], phrase=phrase,
                )


def _notify_users(user_ids, channel_long_id, phrase):
    msg = f"""
Phrase:\n
{QUOTE_PREFIX}{phrase}\n
has appeared in {channel_long_id}
"""
    for uid in user_ids:
        dm_channel = _get_dm_channel_id(uid)
        chat_post_message(channel=dm_channel, message=msg)


def _get_dm_channel_id(user_id):
    r_client = redis.Redis(
        host=os.environ["REDIS_HOST"],
        port=os.environ["REDIS_PORT"],
        db=os.environ["REDIS_CONFIG_DB"],
    )

    user_conf = json.loads(r_client.get(user_id))
    dm_channel_id = user_conf.get("dm_channel_id")
    if not dm_channel_id:
        web_client = WebClient(token=os.environ["SLACK_API_TOKEN"])
        response = web_client.conversations_open(users=[user_id])
        if not response.get("ok", False):
            logging.error(
                "Failed to open DM channel with user {}. "
                "Returned error: {}".format(user_id, response.get("error"))
            )
            return

        dm_channel_id = response.get("channel", {}).get("id")
        user_conf["dm_channel_id"] = dm_channel_id
        r_client.set(user_id, json.dumps(user_conf))

    return dm_channel_id


def message_for_app(event):
    event_type = event.get("type")
    return event_type == "app_mention" or (
        event_type == "message"
        and event.get("subtype") != "bot_message"
        and event.get("channel_type") == "im"
        and _check_bot_im(event)
    )


def _get_bot_user_id(web_api_client):
    response = web_api_client.auth_test()
    if not response.get("ok", False):
        logging.error(
            "Auth test for bot user failed. Returned error: {}".format(response.get("error"))
        )

    return response.get("user_id")


def _check_bot_im(event):
    web_api_client = WebClient(token=os.environ["SLACK_API_TOKEN"])
    response = web_api_client.conversations_members(channel=event.get("channel"))
    if not response.get("ok", False):
        logging.error(
            "Failed to get conversation members for IM chat. Returned error: {}".format(
                response["error"]
            )
        )

    return _get_bot_user_id(web_api_client) in response.get("members")


def process_app_message(event):
    message = get_app_message(event.get("text", "")).strip()

    if message.startswith("help"):
        chat_post_message(event.get("channel"), HELP_MESSAGE)
        return

    if message.startswith("purge config"):
        purge_user_config(event)
        return

    phrases, channels = split_message(message)

    if phrases and channels:
        update_user_config(event, phrases, channels)
    else:
        chat_post_message(event.get("channel"), HELP_MESSAGE)


def purge_user_config(event):
    user_id = event.get("user")

    r_client = redis.Redis(
        host=os.environ["REDIS_HOST"],
        port=os.environ["REDIS_PORT"],
        db=os.environ["REDIS_CONFIG_DB"],
    )

    if r_client.exists(user_id):
        r_client.delete(user_id)

    for chan_id in r_client.scan_iter(match="C*"):
        chan_conf = json.loads(r_client.get(chan_id))
        phrases_users = chan_conf.get("phrases", {})

        stale_phrases = []
        for phrase, users in phrases_users.items():
            if user_id in users:
                users.remove(user_id)
                if not users:
                    stale_phrases.append(phrase)
        for phrase in stale_phrases:
            del phrases_users[phrase]

        r_client.set(chan_id, json.dumps(chan_conf))

    chat_post_message(channel=event.get("channel"), message="I have purged your configuration!")


def update_user_config(event, phrases, channels):
    user = event.get("user")
    if not user:
        logging.error("User is not present in the message description, cannot set the config")
        return

    r_client = redis.Redis(
        host=os.environ["REDIS_HOST"],
        port=os.environ["REDIS_PORT"],
        db=os.environ["REDIS_CONFIG_DB"],
    )

    user_conf = {"phrases": phrases, "channels": channels}
    r_client.set(user, json.dumps(user_conf))

    for chan in channels:
        chan_id = chan.split("|")[0].strip("<").strip("#")

        if not r_client.exists(chan_id):
            chan_conf = {"long_id": chan, "phrases": {phrase: [user] for phrase in phrases}}
        else:
            chan_conf = json.loads(r_client.get(chan_id))
            for phrase in phrases:
                phrase_users = chan_conf["phrases"].setdefault(phrase.strip(QUOTE_PREFIX), [])
                if user not in phrase_users:
                    phrase_users.append(user)
        r_client.set(chan_id, json.dumps(chan_conf))

    msg = ACK_MESSAGE.format("\n".join(phrase for phrase in phrases), " ".join(channels))
    chat_post_message(event.get("channel"), msg)


def chat_post_message(channel, message):
    web_client = WebClient(token=os.environ["SLACK_API_TOKEN"])
    response = web_client.chat_postMessage(channel=channel, text=message)
    if not response.get("ok", True):
        logging.error(
            "Send message operation for channel {} unsuccessful."
            "Returned error msg: {}".format(channel, response["error"])
        )
