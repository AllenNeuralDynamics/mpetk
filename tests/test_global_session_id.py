import time
import os
import subprocess
import logging
import sys
import pathlib as pl

import pytest

sys.path.append(pl.Path(__file__).parent.parent)
from mpetk.mpeconfig.python_3.session_id_db import SharedSessionId, start_session, end_session

from tests.mock_apps import mock_md, mock_sync


def start_redis():
    os.system("wsl service redis-server start")


def stop_redis():
    os.system("wsl service redis-server stop")


def generate_sessions(n: int, *args, **kwargs):
    sessions = []
    for _ in range(3):
        sessions.append(SharedSessionId(*args, **kwargs))
    return sessions


def sessions_match(sessions: list[SharedSessionId]):
    print([sm.session for sm in sessions])
    return len(set([sm.session for sm in sessions])) == 1


## Tests


@pytest.mark.parametrize("mode", ("threaded_polling", "checking", "event_sub"))
def test_subscribe(mode):
    sessions: list[SharedSessionId] = generate_sessions(
        3,
        heartbeat_period_s=2,
        mode=mode,
    )
    sessions[0].start_session(None)

    time.sleep(4)

    assert sessions_match(sessions)


def test_time_to_live():
    sessions: list[SharedSessionId] = generate_sessions(3)
    sessions[0].start_session(4)

    time.sleep(5)

    assert not sessions_match(sessions) or sessions[0].session is None


# def test_active():
#     sessions:list[SharedSessionId] = generate_sessions(3,heartbeat_period_s=1,mode='active')
#     sessions[0].start_session(None)

#     time.sleep(3)

#     assert sessions_match(sessions)


def test_different_rigs():
    """Test as if there were different rigs"""
    sessions1: list[SharedSessionId] = generate_sessions(3, channel="Rig1")
    sessions1[0].start_session(None)

    time.sleep(0.2)

    sessions2: list[SharedSessionId] = generate_sessions(3, channel="Rig2")
    sessions2[0].start_session(None)

    time.sleep(1)

    metrics = [
        sessions_match(sessions1),
        sessions_match(sessions2),
        sessions1[0].session != sessions2[0].session,
    ]

    assert all(metrics)


def test_end_session():
    """Ensure that ending a shared session removes the id"""
    sessions: list[SharedSessionId] = generate_sessions(3, heartbeat_period_s=1)
    sessions[0].start_session(None)

    time.sleep(2)

    sessions_match(sessions)

    sessions[1].end_session()

    time.sleep(2)

    assert sessions_match(sessions) and sessions[0].session == None

def test_end_session():
    start_session(1)
    time.sleep(2)
    end_session()

def mock(app: str, *args):
    """Mocks an app running in a subprocess"""
    print(["python", "./tests/mock_apps.py", app] + [str(a) for a in args])
    subprocess.Popen(
        ["python", "./tests/mock_apps.py", app] + [str(a) for a in args],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )


def test_mock_apps():
    """ Tests with two apps sharing a session.
    Ensure that the logserver output looks like session_app_test_output.txt
    """

    mock("md", True, False, 30)
    mock("sync", 20)
    time.sleep(10)
    mock("md", False, True)
    time.sleep(30) # sleep for long enough for the subprocesses to finish


if __name__ == "__main__":
    # start_redis()
    # test_subscribe('checking')
    # test_different_rigs()
    # test_active()
    # test_end_session()
    # test_mock_apps()
    # test_one_app()
    test_end_session()
