from celery import Celery

from .process_event import chat_message, message_for_app, process_app_message, process_chat_message
from .utils import REDIS_HOST, REDIS_PORT, REDIS_QUEUE_DB

app = Celery("tasks", broker=f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_QUEUE_DB}",)


@app.task
def process_slack_event(data):
    if data.get("type") == "event_callback":
        event = data.get("event", {})

        if event.get("subtype") != "bot_message":
            if message_for_app(event):
                process_app_message(event)

            if chat_message(event):
                process_chat_message(event)
