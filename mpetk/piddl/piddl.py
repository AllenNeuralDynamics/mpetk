import enum
import logging
from sys import exit

from . dltools import make_socket
from . pidtools import make_pid_file, PidFileStaleError, PidFileAlreadyRunningError


class InstanceLocks(enum.Enum):
    PID_FILE = 1
    DAEMON_LOCK = 2


def one_instance(mode: InstanceLocks = InstanceLocks.PID_FILE, clobber_stale: bool = True):
    """
    A decorator intended for main() so that an application won't start twice.
    :param mode: An assortment of possible lock mechanisms
    :param clobber_stale: Whether or not to delete stale PID files [False]
    """
    if mode == InstanceLocks.PID_FILE:
        def decorator(function):
            def inner_function(*args, **kwargs):
                try:
                    make_pid_file(clobber_stale=clobber_stale)
                except PidFileAlreadyRunningError:
                    logging.warning('This application is already running.  Exiting.')
                    exit(2)
                except PidFileStaleError:
                    logging.warning('A PID File for this application exists but appears stale.')
                    exit(1)
                function(*args, **kwargs)

            return inner_function

        return decorator

    elif mode == InstanceLocks.DAEMON_LOCK:
        def decorator(function):
            def inner_function(*args, **kwargs):
                try:
                    make_socket()
                except OSError:
                    logging.warning('This application is already running.  Exiting.')
                    exit(2)
                function(*args, **kwargs)

            return inner_function

        return decorator
