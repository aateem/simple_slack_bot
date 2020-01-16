import logging
import os

from flask import Flask, request
from slack import WebClient

from process_text import get_bot_mention_message, get_channels, get_phrases, HELP_MESSAGE

logging.basicConfig(level=os.environ.get("APP_LOGGING_LEVEL", logging.INFO))

app = Flask(__name__)

# CMD_REGEX = (
#     '.*listen\s*for\s*phrases\:\s*(\["?[a-zA-Z0-9].*"?\|*\])*\s?'
#     "in\s?channels\:\s*([a-zA-Z0-9].*\,*)"
# )


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

        if event.get("type") == "app_mention":
            process_bot_command(event)
        if event.get("type") == "message.channels":
            check_message(event)

    return ("", 200)


def process_bot_command(event):
    message = get_bot_mention_message(event.get("text", ""))
    if message.strip().startswith("help"):
        give_help(event.get("channel"))

    phrases = get_phrases(message)
    channels = get_channels(message)

    if phrases and channels:
        user = event.get("user", "")
        update_user_config(user, phrases, channels)
    else:
        give_help(event.get("channel"))


def give_help(channel):
    web_client = WebClient(token=os.environ["SLACK_API_TOKEN"])
    response = web_client.chat_postMessage(channel=channel, text=HELP_MESSAGE)
    if not response.get("ok", True):
        logging.error(
            "Send help message operation unsuccessful."
            "Returned error msg: {}".format(response["error"])
        )


def update_user_config(user, phrases, channels):
    pass


def check_message(event):
    pass
