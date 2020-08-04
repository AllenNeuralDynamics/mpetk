import atexit
import codecs
import os
import socket
import sys
import uuid


def make_socket(port: int = None):
    """
    Creates a socket whose port is based on the application name.  You can override the port manually.
    :param port: override the generated port number
    :raises OSError: This will throw if the socket is already opened
    """
    port = port or generate_port()
    global s
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', port))
    atexit.register(atexit_handler)


def generate_port() -> int:
    """
    Takes the application name (or first argument to python) and hashes it to an integer 1024 < i < 10000
    :return:
    """
    app_name = os.path.basename(sys.argv[0])
    if app_name == 'python.exe' and len(sys.argv > 1):
        app_name = os.path.basename(sys.argv[1])
    app_name = app_name.zfill(16)[:16]
    uuid_key = codecs.encode(app_name.encode(), 'hex')
    return uuid.UUID(uuid_key.decode()).int % 8976 + 1024


def atexit_handler():
    """
    Handle final maintenance like closing the socket
    :return:
    """
    s.close()
