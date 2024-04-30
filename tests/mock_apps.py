import logging
import time
import sys
import ast

from mpetk.mpeconfig.python_3.mpeconfig import source_configuration
from mpetk.mpeconfig.python_3.session_id_db import start_session, end_session


def mock_md(start=True, stop=True, ttl=20):
    source_configuration("mouse_director")
    if start:
        start_session(ttl)

    time.sleep(4)

    logging.info("Log 1", extra={"weblog": True})

    time.sleep(2)

    if stop:
        end_session()

    time.sleep(2)

    logging.info("one last log", extra={"weblog": True})


def mock_sync(n_logs=15):
    source_configuration("sync", fetch_project_config=False)

    for n in range(int(n_logs)):
        logging.info(f"Sync log {n}", extra={"weblog": True})
        time.sleep(1)


if __name__ == "__main__":
    if sys.argv[1] == "md":
        mock_md(*[ast.literal_eval(a) for a in sys.argv[2:]])
    elif sys.argv[1] == "sync":
        mock_sync(*[ast.literal_eval(a) for a in sys.argv[2:]])
