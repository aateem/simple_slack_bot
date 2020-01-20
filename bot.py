import logging
import os

from flask import Flask, request, jsonify
from slack import WebClient

from process_text import get_app_message, split_message, HELP_MESSAGE, ACK_MESSAGE, QUOTE_PREFIX

logging.basicConfig(level=os.environ.get("APP_LOGGING_LEVEL", logging.INFO))

app = Flask(__name__)

USER_CONFIG = {"users": {}, "channels": {}}


# debug
@app.route("/config")
def get_config():
    return jsonify(USER_CONFIG)


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
    if channel in USER_CONFIG["channels"]:
        channel_conf = USER_CONFIG["channels"][channel]
        phrases_conf = channel_conf.get("phrases", {})

        for phrase in phrases_conf.keys():
            if phrase in event.get("text", ""):
                _notify_users(
                    user_ids=phrases_conf[phrase],
                    channel_long_id=channel_conf["long_id"],
                    phrase=phrase,
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
    dm_channel_id = USER_CONFIG["users"][user_id].get("dm_channel_id")
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
        USER_CONFIG["users"][user_id]["dm_channel_id"] = dm_channel_id

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
    message = get_app_message(event.get("text", ""))

    if message.strip().startswith("help"):
        chat_post_message(event.get("channel"), HELP_MESSAGE)
        return

    phrases, channels = split_message(message)

    if phrases and channels:
        update_user_config(event, phrases, channels)
    else:
        chat_post_message(event.get("channel"), HELP_MESSAGE)


def update_user_config(event, phrases, channels):
    user = event.get("user")
    if not user:
        logging.error("User is not present in the message description, cannot set the config")
        return

    USER_CONFIG["users"][user] = {"phrases": phrases, "channels": channels}

    for chan in channels:
        chan_id = chan.split("|")[0].strip("<").strip("#")
        conf_channel = USER_CONFIG["channels"].setdefault(chan_id, {"long_id": chan, "phrases": {}})
        for phrase in phrases:
            conf_phrase = conf_channel["phrases"].setdefault(phrase.strip(QUOTE_PREFIX), [])
            conf_phrase.append(user)

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
