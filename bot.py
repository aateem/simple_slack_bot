import logging
import os

from flask import Flask, request, jsonify
from slack import WebClient

from process_text import get_app_message, split_message, HELP_MESSAGE, ACK_MESSAGE

logging.basicConfig(level=os.environ.get("APP_LOGGING_LEVEL", logging.INFO))

app = Flask(__name__)

USER_CONFIG = {}


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

        if accept_event(event):
            process_app_message(event)

    return ("", 200)


def accept_event(event):
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

    USER_CONFIG[user] = {"phrases": phrases, "channels": channels}

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
