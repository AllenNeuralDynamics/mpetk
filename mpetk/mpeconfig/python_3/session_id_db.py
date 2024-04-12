from ast import Global
import logging
import threading
import queue
import redis
import os
import uuid
import atexit
import time
import datetime
import platform
from hashlib import md5

# from mpetk.mpeconfig import source_configuration

# CONFIG = {
#     "host": "localhost",
#     "port": "6378",
#     # "port": "6379",
#     "heartbeat_period_s": 30,
# }
AIBS_RIG_ID = os.getenv("aibs_rig_id", platform.node())
AIBS_COMP_ID = os.getenv("aibs_comp_id", platform.node())


class GlobalSessionID:
    def __init__(self,channel=AIBS_COMP_ID, host:str='localhost',port:str='6379',heartbeat_period_s:int=30,mode='passive'):
        self.channel = channel # Note that this defaults to comp name, not 'undefined'
        self.host = host
        self.port = port
        self.heartbeat_period_s = heartbeat_period_s
        # self.host = config.get('host','localhost')
        # self.port = config.get('port','6379')
        # self.heartbeat_period_s = config.get('heartbeat_period_s',30)
        self.rdb = redis.Redis(self.host, self.port)

        self.subscription = self.rdb.pubsub()
        # self.subscription.run_in_thread(sleep_time=1, daemon=True)

        self.connection_retry_period_s = 60
        self.connected = True

        self._session = None

        if True:
            self.subscribe()
            self.subscription.run_in_thread(sleep_time=1, daemon=True)
        else:
            self.session_recv_thread = threading.Thread(target=self.recv_notifications, args=[self.subscription])
            self.session_recv_thread.start()

            atexit.register(self.session_recv_thread.join)



    @property
    def session(self):
        if self._session is None:
            if time.time() - self.last_connection_retry > self.connection_retry_period_s:
                self.subscribe()
                # TODO

        return self._session

    def subscribe(self):
        try:
            self.subscription.subscribe(**{self.channel: self.update_session_id})
            self.connected = True
        except redis.exceptions.ConnectionError as e:
            if self.connected:
                logging.info("Cannot connect to redis global session database")
            self.last_connection_retry = time.time()

        # self.subscription.run_in_thread(sleep_time=1, daemon=True)

        # self.session_recv_thread = threading.Thread(target=self.recv_notifications, args=[self.subscription])
        # self.session_recv_thread.start()

        # atexit.register(self.session_recv_thread.join)  # this feels like an incorrect use of join

    def update_session_id(self, message):
        if isinstance(message, dict):
            if isinstance(message["data"], bytes):
                session = message["data"].decode()
            else:
                session = message["data"]
            self._session = session

    def recv_notifications(self, sub: redis.client.PubSub):
        connected = True
        while True:
            msg = sub.get_message(timeout=1.5 * CONFIG["heartbeat_period_s"])
            print(msg)
            if msg is None:
                if connected:
                    logging.warning("Warning, lost connection to session id server")
                connected = False
            elif isinstance(msg, dict):
                data = msg["data"]
                if data != 1:
                    if not connected:
                        logging.info("Regained connection to session id server")
                    connected = True
                    if data != "heartbeat":
                        self.session = msg

    def start_session(self, time_to_live_s):
        session_parts = [str(datetime.datetime.now()), platform.node(), str(os.getpid())]
        session_id = md5(("".join(session_parts)).encode("utf-8")).hexdigest()[:7]
        try:
            n_subscribers = self.rdb.publish(AIBS_RIG_ID, session_id, ex=time_to_live_s)
        except redis.exceptions.ConnectionError as e:
            logging.warning(f"Warning, could not publish global session id, exception, {repr(e)}")
            self._session = session_id

