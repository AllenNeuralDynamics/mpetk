import os


def ensure_path(path: str):
    """
    if the path for logging and configuration storage does not exist, make it.  Logging configuration will fail if
    the directory does not exist.
    :param path: A path to check and create
    """

    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        os.makedirs(directory)
