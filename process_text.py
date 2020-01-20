import re


MENTION_REGEXP = "^<@(|[WU].+?)>(.*)"
PHRASE_LIST_REGEXP = '.*listen\s*for\s*phrases\:\s*(\["?[a-zA-Z0-9].*"?\|*\])*\s?'
CHANNEL_LIST_REGEXP = ".*in\s?channels\:\s*([a-zA-Z0-9].*\,*)"


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


def get_app_message(text):
    substrings = re.split(MENTION_REGEXP, text)

    if len(substrings) > 1:
        return substrings[2]

    return substrings[0]


def _separate_strings(matched_group):
    for s in matched_group.strip().strip("]").strip("[").split("|"):
        yield s


def get_phrases(message):
    phrases = None
    match = re.match(PHRASE_LIST_REGEXP, message)
    if match:
        phrases = [phrase.strip().strip('"') for phrase in _separate_strings(match.group(1))]
    return phrases


def get_channels(message):
    channels = None
    match = re.match(CHANNEL_LIST_REGEXP, message)
    if match:
        channels = [chan.strip() for chan in _separate_strings(match.group(1))]
    return channels
