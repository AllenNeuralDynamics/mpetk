import logging
import os
import platform
import typing
import uuid

import redis

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

logger = logging.getLogger(__name__)


class SharedSessionId:
    def __init__(
        self,
        channel=None,
        host: str = "localhost",
        port: int = 6379,
        db: int = 2,
        heartbeat_period_s: int = 30,
    ):

        self.channel = channel or os.getenv("aibs_rig_id", platform.node())
        if not channel and not os.getenv("aibs_rig_id", None):
            logger.warning(f"Host {self.channel} has no aibs_rig_id.  Using hostname instead.")

        logger.info(f"Connecting to GSID DB: {host}:{port}, db={db}")

        self.rdb = redis.Redis(host, port, db)
        if not self.ping():
            logger.warning(f"Failed to connect GSID DB")
            return

        self.rdb.config_set("notify-keyspace-events", "KEA")
        self.subscriber = self.rdb.pubsub()

        self.session = self.rdb.get(channel)
        self.subscriber.psubscribe(**{f"__keyspace*__:{self.channel}": self.process_key_event})

        self.heartbeat_period_s = heartbeat_period_s
        self._session = None
        self.last_get = 0

        self.session = self.rdb.get(channel)

        self.subscriber.run_in_thread(sleep_time=1, daemon=True)

    @property
    def connected(self):
        return self.rdb.ping()

    @property
    def session(self):
        return self._session

    @session.setter
    def session(self, key):
        if isinstance(key, bytes):
            key = key.decode()
        self._session = key

    def process_key_event(self, event):
        """
        Events do not pass values.  You have to test data for the operation type and dispatch accordingly.

        Args:
            event: {
                'type': 'pmessage',
                'pattern': b'__keyspace*__:channel',
                'channel': b'__keyspace@2__:channel',
                'data': b'set'  # del, # expired
            }
        Returns:

        """
        data = event.data.decode()

        if data == 'set':
            self.session = self.rdb.get(self.channel)
        elif data in ('expired', 'del'):
            self.session = None

    def start_session(self, time_to_live_s: int, kill_existing: bool = True):
        if self.session == self.rdb.get(self.channel) and not kill_existing:  # I think we don't do anything here
            raise ValueError('A session is already running. Pass `kill_existing=True` to replace it.')
        key = uuid.uuid4().hex
        self.rdb.set(self.channel, key, ex=time_to_live_s)
        logger.info(f"Action: Beginning shared session {key}", extra={"weblog": True})

    def end_session(self):
        logging.info({"Action": "Ended shared session {self.session}"}, extra={"weblog": True}, )
        self.rdb.delete(self.channel)

