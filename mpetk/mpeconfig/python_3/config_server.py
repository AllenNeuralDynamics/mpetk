# -*- coding: utf-8 -*-
from kazoo.client import KazooClient
from kazoo.handlers.threading import KazooTimeoutError


class ConfigServer(KazooClient):
    """
    A dictionary and context API wrapper around the zookeeper interface.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
        self.start()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.stop()
