import datetime
import logging
import requests

from adaptive_card import AdaptiveCard
from collections import deque
from mpetk import mpeconfig
from typing import List, Optional

########################################################################################################################
#
#      Configuration
#
########################################################################################################################


config = mpeconfig.source_configuration("teamstk", hosts="localhost:2181", fetch_logging_config=False)


########################################################################################################################
#
#       Alerts
#
########################################################################################################################


def alert(title: str, description: str, tags: Optional[List[str]]):
    """
    Send a default alert. Default alert format:
        - Title
        - Description
        - Tags (optional)

    Args:
        title: Title of alert
        description: Description of alert
        tags: Optional tags (system engineers)
    """
    card = AdaptiveCard(title)
    card.add_description(description)

    # Add optional tags
    if not tags:
        card.add_tags(tags)

    webhook = config['webhooks']['logserver']

    send_teams_alert(card, webhook)


def alert_logserver(title: str, description: str, rig_id: str, log_link: str, tags: Optional[List[str]]):
    """
    Send a log alert. Log alert format:
        - Title
        - Description
        - Log Info
        - Tags (optional)
        - Link

    Args:
        title: Title of alert
        description: Description of alert
        rig_id: Rig ID associated with log
        log_link: Logserver link
        tags: Optional tags (system engineers)
    """
    card = AdaptiveCard(title)
    card.add_description(description)
    card.add_log_info(rig_id, log_link)

    # Add optional tags
    if tags:
        card.add_tags(tags)

    card.add_link_button(("log link", log_link))

    # Get webhook
    webhook = config['webhooks']['logserver']

    # Send adaptive card to teams
    send_teams_alert(card, webhook)


########################################################################################################################
#
#       Helpers
#
########################################################################################################################


def check_frequency() -> bool:
    """
    Checks the frequency of alerts being sent to teams

    Returns: True if within frequency limit, else False
    """
    current = datetime.datetime.now()
    if check_frequency.timestamps:
        try:
            average = len(check_frequency.timestamps) / (current - check_frequency.timestamps[-1]).total_seconds()
            if average > check_frequency.freq:
                logging.warning(
                    f"You are sending messages too frequently. Avg Freq: {average}. Max Freq: {check_frequency.freq}")
                return False
        except ZeroDivisionError:
            pass
    check_frequency.timestamps.append(current)
    return True


def send_teams_alert(adaptive_card: AdaptiveCard, webhook: str):
    """
    Sends an alert to teams

    Args:
        adaptive_card: Adaptive card object
        webhook: webhook link
    """
    if check_frequency():
        try:
            response = requests.post(webhook, json=adaptive_card.json)
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to send teams alert: {e}")
            logging.error(f"The following message failed to make it to teams {webhook}: {adaptive_card.body}")


check_frequency.timestamps = deque(maxlen=max(1, int(config['max_freq_hz'])))
check_frequency.freq = config['max_freq_hz']


########################################################################################################################
#
#       Test
#
########################################################################################################################


# Testing code...
title_test = "TEST: a run completed and we recorded failure"
description_test = "Keith/Heston Help"
rig_id_test = "BEH.TEST"
log_link_test = "http://eng-tools/test"
tags_test = ["jessy.liao@alleninstitute.org", "fakeperson@alleninstitute.org", "bademail@foopy.foop"]

alert_logserver(title_test, description_test, rig_id_test, log_link_test, tags_test)
