import os

from redis import Redis
from slack import WebClient


QUOTE_PREFIX = "&gt; "
CHANNEL_ID_PREFIX = "<#C"

HELP_MESSAGE = """
Whislteblower bot notifies you in DM whenever
any of defined phrases pops up in any channel from
a set.

Both phrase and channel lists are given by you, just
say smth like:
> *@whistleblowerbot* listen for phrases: ["foo bar" | "foozah" ] in channels: [channel_1 | channel_2 | channel_3]

The bot will be sending notifications until explicitly disabled via:
> *@whislteblowerbot* cease!
"""

ACK_MESSAGE = """
Updated your configuration.

You are listening for phrases\n{}
in channels [{}]"""

NOTIFY_USER_MSG = """
Phrase:\n
{}{}\n
has appeared in {}
"""

redis_client = Redis(
    host=os.environ["REDIS_HOST"], port=os.environ["REDIS_PORT"], db=os.environ["REDIS_CONFIG_DB"],
)
web_api_client = WebClient(token=os.environ["SLACK_API_TOKEN"])


def split_message(text):
    if "listen for phrases" in text.lower() and "in channels" in text.lower():
        phrases_substr, channels_substr = text.split("in channels")
        return _get_phrases(phrases_substr), _get_channels(channels_substr)
    return None, None


def _get_phrases(phrases_substring):
    return [phrase for phrase in phrases_substring.split("\n") if phrase.startswith(QUOTE_PREFIX)]


def _get_channels(channels_substring):
    return [
        channel for channel in channels_substring.split() if channel.startswith(CHANNEL_ID_PREFIX)
    ]
