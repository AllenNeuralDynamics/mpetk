# -*- coding: utf-8 -*-
from kazoo.client import KazooClient
from kazoo.handlers.threading import KazooTimeoutError


class ConfigServer(KazooClient):
    """
    A dictionary and context API wrapper around the zookeeper interface.
    """

    def __init__(self, hosts="aibspi:2181", timeout=1):
        self.hosts = hosts
        super(ConfigServer, self).__init__(hosts=hosts, timeout=1)

    def __getitem__(self, key):
        if self.exists(key):
            return self.get(key)[0]
        else:
            raise KeyError(key)

    def __setitem__(self, key, value):
        self.ensure_path(key)
        self.set(key, value)

    def __delitem__(self, key):
        if self.exists(key):
            self.delete(key)

    def __enter__(self):
        try:
            self.start(timeout=1)
        except KazooTimeoutError:
            pass
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.stop()
