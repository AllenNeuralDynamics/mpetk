# -*- coding: utf-8 -*-

__author__ = """ross hytnen"""
__email__ = 'rossh@alleninstitute.org'
<<<<<<< HEAD
__version__ = '0.2.1.dev0'
=======
__version__ = '0.2.0.dev5'
>>>>>>> 25b3ae225c94580687c1999c3b3bf6a56f2fe0ef
__url__ = 'http://aibspi/piddl.git'

from .piddl import InstanceLocks
from .piddl import one_instance
from .pidtools import PidFileStaleError, PidFileError, PidFileAlreadyRunningError, make_kill_file, delete_kill_file, register_kill_callback
