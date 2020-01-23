import json
import logging
import os

from flask import Flask, request, jsonify

from .tasks import process_slack_event
from .utils import redis_client

logging.basicConfig(level=os.environ.get("APP_LOGGING_LEVEL", logging.INFO))

app = Flask(__name__)


@app.route("/config")
def get_config():
    users = {}
    channels = {}
    for user_id in redis_client.scan_iter(match="U*"):
        users[user_id.decode("utf-8")] = json.loads(redis_client.get(user_id))
    for chan_id in redis_client.scan_iter(match="C*"):
        channels[chan_id.decode("utf-8")] = json.loads(redis_client.get(chan_id))
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

    process_slack_event.delay(data)
    return ("", 200)
