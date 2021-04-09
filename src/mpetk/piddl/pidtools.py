import os
import sys

import psutil
import logging
import atexit

DEFAULT_PID_DIR = "c:/ProgramData/AIBS_MPE/pids"


class PidFileError(Exception):
    pass


class PidFileAlreadyRunningError(PidFileError):
    pass


class PidFileStaleError(PidFileError):
    pass


# NOTE:  we want to check the behavior of these functions with subprocesses


def pid_filename(pid_name: str = None, pid_dir: str = None) -> str:
    """
    Generates a reproducible PID Filename.  If the PID_DIR does not exist, it will be created.
    :param pid_name: If this parameter is set, it will use this as the PID filename instead of generating it.
    :param pid_dir: Overrides the storage location of the PID File
    :raises: PidFileError if there is a failure to create the pid_dir
    :return: String representing the fully qualified path to the PID File
    """
    pid_name = pid_name or f"{os.path.basename(sys.argv[0])}"
    if not pid_name.endswith(".pid"):
        pid_name = f"{pid_name}.pid"

    pid_dir = pid_dir or DEFAULT_PID_DIR
    try:
        os.makedirs(pid_dir, exist_ok=True)
    except Exception as e:
        raise PidFileError(str(e))

    return f"{pid_dir}/{pid_name}"


def make_pid_file(pid_name: str = None, pid_dir: str = None, clobber_stale: bool = False):
    """
    Creates the actual PID file.  It will only create the PID file if one doesn't exist or process is stale and clobber
    is true.
    :param pid_name: The name of the PID file itself (represents the process name generally)
    :param pid_dir:  The directory where PID files live
    :param clobber_stale: Whether or not to clobber PID files if the process isn't running
    :raises PidFileStaleError if there is a stale file and clobber_stale = False
    """
    filename = pid_filename(pid_name, pid_dir)
    if os.path.exists(filename):
        try:
            check_for_process(filename)
        except PidFileAlreadyRunningError:
            raise
        except PidFileStaleError:
            if clobber_stale:
                os.unlink(filename)
                with open(filename, "x") as f:
                    f.write(str(os.getpid()))
            else:
                raise PidFileStaleError
    else:
        with open(filename, "x") as f:
            f.write(str(os.getpid()))

    atexit.register(atexit_handler, filename)


def check_for_process(filename: str):
    """
    Given a PID File that contains a PID, this function looks for that PID and compares it's process name to the
    process name of the application executing this function.  It raises exceptions based on the conditions it finds as
    described below
    :param filename:  Path to the PID File
    :raises PidFileStaleError: Raised when the process id is running but doesn't match the querying process or when the
    process id is not running.
    :raises PidFileAlreadyRunningError:  Raised when the process id is running and matches the querying process.
    """
    if not os.path.exists(filename):
        logging.warning(f'Could not locate PID File {filename}')
        return

    pid_file = os.path.basename(filename)
    if pid_file.endswith(".pid"):
        pid_file = pid_file[:-4]

    with open(filename, "r") as f:
        pid = int(f.read().strip())

    proc = [p for p in list(psutil.process_iter()) if p.pid == pid]
    if not proc:
        raise PidFileStaleError(f"PID File {pid_file} exists but appears stale.")

    proc = proc[0]
    if "python.exe" in proc.name() and len(proc.cmdline()) > 1:
        if pid_file == os.path.basename(proc.cmdline()[1]):
            raise PidFileAlreadyRunningError
    else:
        if pid_file == proc.name():
            raise PidFileAlreadyRunningError

    raise PidFileStaleError("PID File {pid_file} exists but appears stale.")


def remove_pid_file(filename: str):
    """
    Calls unlink with some additional error checking (isfile(), etc).  Generally intended for use by the atexit handler
    :param filename: Path to the PID File
    """
    if os.path.isfile(filename):
        try:
            os.unlink(filename)
        except PermissionError as e:
            logging.warning(f"Could not delete PID file {filename}. {e}")


def atexit_handler(filename: str):
    """
    Actions to be performed at termination time.  For example, deleting the PID file.
    :param filename: path to the pid file
    """
    remove_pid_file(filename)
