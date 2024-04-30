import logging
import threading
import redis
import os
import time
import datetime
import typing
import platform
from hashlib import md5
from typing import Literal

# CONFIG = {
#     "host": "localhost",
#     "port": "6378",
#     # "port": "6379",
#     "heartbeat_period_s": 30,
# }

#### This is from the docs on keyspace events:

# K     Keyspace events, published with __keyspace@<db>__ prefix.
# E     Keyevent events, published with __keyevent@<db>__ prefix.
# g     Generic commands (non-type specific) like DEL, EXPIRE, RENAME, ...
# $     String commands
# l     List commands
# s     Set commands
# h     Hash commands
# z     Sorted set commands
# t     Stream commands
# d     Module key type events
# x     Expired events (events generated every time a key expires)
# e     Evicted events (events generated when a key is evicted for maxmemory)
# m     Key miss events (events generated when a key that doesn't exist is accessed)
# n     New key events (Note: not included in the 'A' class)
# A     Alias for "g$lshztxed", so that the "AKE" string means all the events except "m" and "n".

# 1) "psubscribe"
# 2) "*"
# 3) (integer) 1
# 1) "pmessage"
# 2) "*"
# 3) "__keyspace@0__:mykey"
# 4) "set"
# 1) "pmessage"
# 2) "*"
# 3) "__keyevent@0__:set"
# 4) "mykey"
# 1) "pmessage"
# 2) "*"
# 3) "__keyspace@0__:mykey"
# 4) "set"
# 1) "pmessage"
# 2) "*"
# 3) "__keyevent@0__:set"
# 4) "mykey"
# 1) "pmessage"
# 2) "*"
# 3) "__keyspace@0__:mykey"
# 4) "expire"
# 1) "pmessage"
# 2) "*"
# 3) "__keyevent@0__:expire"
# 4) "mykey"
# 1) "pmessage"
# 2) "*"
# 3) "__keyspace@0__:mykey"
# 4) "expired"
# 1) "pmessage"
# 2) "*"
# 3) "__keyevent@0__:expired"
# 4) "mykey"


class SharedSessionId:
    def __init__(
        self,
        channel=None,
        host: str = "localhost",
        port: str = "6379",
        heartbeat_period_s: int = 30,
        mode: set[Literal["threaded_polling", "checking", "event_sub"]] = {"event_sub"},
    ):

        # Note that this defaults to comp name, not 'undefined'
        self.channel = channel or os.getenv("aibs_rig_id", platform.node())
        self.host = host
        self.port = port
        self.heartbeat_period_s = heartbeat_period_s

        self.mode = mode

        self.rdb = redis.Redis(self.host, self.port)

        self._session = None

        self.last_get = 0

        self.connected = True

        self.update_session_id()

        if "threaded_polling" in mode:
            self.polling_thread = threading.Thread(target=self.threaded_refresh_session_id, daemon=True)
            self.polling_thread.start()

        if "event_sub" in mode:
            self.rdb.config_set("notify-keyspace-events", "KEA")
            self.subscription = self.rdb.pubsub()
            self._subscribe()
            self.subscription.run_in_thread(sleep_time=1, daemon=True)

    def update_session_id(self, sub_msg=None):
        """Query the database for a session id and modify self._session"""
        value = self._get()

        if isinstance(value, bytes):
            self._session = value.decode()
            self.last_get = time.time()
        else:
            self._session = None

    def start_session(self, time_to_live_s:int, kill_existing:bool=True):
        if session_id := self._get() and not kill_existing:
            self._set(session_id, ex=time_to_live_s)
        else:
            session_parts = [str(datetime.datetime.now()), platform.node(), str(os.getpid())]
            session_id = md5(("".join(session_parts)).encode("utf-8")).hexdigest()[:7]
            self._set(session_id, ex=time_to_live_s)

        self._session = session_id
        logging.info({"Action": "Began shared session"}, extra={"weblog": True})


    def end_session(self):
        logging.info(
            {"Action": "Ended shared session"},
            extra={"weblog": True},
        )
        self.rdb.delete(self.channel)

    @property
    def session(self):
        if "checking" in self.mode:
            print(self._session, time.time() - self.last_get, self.last_get)
            if time.time() - self.last_get > self.heartbeat_period_s:
                self.update_session_id()

        return self._session

    def threaded_refresh_session_id(self):
        while True:
            self.update_session_id()
            time.sleep(self.heartbeat_period_s)

    def _subscribe(self):
        """Subscribe to keyspace events
        __keyspace@0__:mykey
        __keyevent@0__:set"""
        try:
            self.subscription.psubscribe(
                **{
                    # self.channel: self.update_session_id,
                    f"__keyspace*__:{self.channel}": self.update_session_id,
                }
            )
            self.connected = True
        except redis.exceptions.ConnectionError as e:
            if self.connected:
                logging.info("Cannot connect to redis global session database")
            self.last_connection_retry = time.time()

    def _set(self, value, *args, **kwargs):
        try:
            self.rdb.set(self.channel, value, *args, **kwargs)
            self.update_session_id()
            logging.info(
                {"Action": "Set Global Session Key", "Time To Live": kwargs.get("ex", -1)},
                # extra={"weblog": True},
            )
            self.connected = True
        except redis.exceptions.ConnectionError as e:
            if self.connected:
                logging.warning(
                    {
                        "Warning": "could not publish global session id",
                        "Suggestion": "It's possible redis is not running",
                        "Exception": repr(e),
                    }
                )
            self.connected = False

    def _get(self, *args, **kwargs):
        try:
            value = self.rdb.get(self.channel)
            if not self.connected:
                logging.info("Connected to redis global session database")
            self.connected = True
            return value
        except redis.exceptions.ConnectionError as e:
            if self.connected:
                logging.info("Cannot connect to redis global session database")
            self.connected = False
            self.last_connection_retry = time.time()

    # @property
    # def session(self):
    #     if self._session is None:
    #         if time.time() - self.last_connection_retry > self.connection_retry_period_s:
    #             self.subscribe()
    #             # TODO

    #     return self._session

    # def publish(self,content='',*args,**kwargs):
    #     try:
    #         n_subscribers = self.rdb.publish(self.channel, content, *args,**kwargs)
    #         logging.info(
    #             {
    #                 "Action": f"Shared session started on {self.channel}",
    #                 "Number of Subscribers": n_subscribers,
    #             }
    #         )
    #         return True
    #     except redis.exceptions.ConnectionError as e:
    #         logging.warning(
    #             {
    #                 "Warning": "could not publish global session id",
    #                 "Suggestion": "It's possible redis is not running",
    #                 "Exception": repr(e),
    #             }
    #         )
    #         return False

    # def update_session_id(self, message):
    #     print(message)
    #     if isinstance(message, dict):
    #         if isinstance(message["data"], bytes):
    #             session = message["data"].decode()
    #         else:
    #             session = message["data"]
    #         self._session = session

    # def recv_notifications(self, sub: redis.client.PubSub):
    #     connected = True
    #     while True:
    #         msg = sub.get_message(timeout=1.5 * self.heartbeat_period_s)
    #         print(msg)
    #         if msg is None:
    #             if connected:
    #                 logging.warning("Warning, lost connection to session id server")
    #             connected = False
    #         elif isinstance(msg, dict):
    #             data = msg["data"]
    #             if data != 1:
    #                 if not connected:
    #                     logging.info("Regained connection to session id server")
    #                 connected = True
    #                 if data != "heartbeat":
    #                     self.session = msg


session_manager = SharedSessionId()


start_session: typing.Callable = session_manager.start_session
end_session: typing.Callable = session_manager.end_session
