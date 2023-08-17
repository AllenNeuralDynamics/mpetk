import datetime
import logging
import os
import socket
from collections import deque

import pymsteams

from mpetk import mpeconfig

config = mpeconfig.source_configuration("teamstk", hosts="aibspi:2181", fetch_logging_config=False)


def make_source_section():
    hostname = socket.gethostname()
    section = pymsteams.cardsection()
    section.title("Source")
    # section.addFact('application', logging.getLogger().handlers[0].get_name())
    section.addFact('rig id', os.getenv("aibs_rig_id", "unknown"))
    section.addFact('comp id', os.getenv("aibs_comp_id", "unknown"))
    section.addFact('hostname', hostname)
    section.addFact("ip address", socket.gethostbyname(hostname))

    return section


def alert(title, message, error=False, webhook='default', links=()):
    """
    Sends a Teams Messenger cqrd
    Args:
        title: The title of the card
        message: Main text to display
        error: boolean [False]  While toggle the color of the alert to red if true
        webhook: URL [default] what teams channel are you using?
        links: tuple of pairs.  Example ([Link Text, Link URL],)

    Returns:  Boolean for success or fail

    """
    current = datetime.datetime.now()
    if alert.timestamps:
        try:
            average = len(alert.timestamps) / (current - alert.timestamps[-1]).total_seconds()
            if average > alert.freq:
                logging.warning(
                    f"You are sending messages too frequently.  Avg Freq: {average}.  Max Freq: {alert.freq}")
                return False
        except ZeroDivisionError:
            pass
    alert.timestamps.append(current)

    if webhook not in config['webhooks']:
        logging.warning(f"Could not find webhook {webhook}.  Using default.")
        webhook = 'default'
    url = config['webhooks'].get(webhook, "default")

    connector = pymsteams.connectorcard(url)
    connector.title(title)
    connector.text(message)
    if error:
        connector.color("#FF0000")
    connector.addSection(make_source_section())

    for link in links:
        connector.addLinkButton(link[0], link[1])

    try:
        connector.send()
    except Exception as e:
        logging.error(f"Failed to send teams alert: {e}")
        logging.error(f"The follow message failed to make it to teams {webhook}: {title}, {message}")
        return False
    return True



alert.timestamps = deque(maxlen=max(1, int(config['max_freq_hz'])))
alert.freq = config['max_freq_hz']
