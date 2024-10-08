import atexit
import datetime
import getpass
import logging
import logging.config
import logging.handlers
import os
import platform
import sys
import traceback
from hashlib import md5

from queue import Queue

default_logging_dict = """
disable_existing_loggers: true
formatters:
  detailed:
    datefmt: '%m/%d/%Y %I:%M:%S %p'
    format: '%(asctime)s, %(levelname)s, %(module)s::%(lineno)s, %(message)s'
  log_server:
    datefmt: '%Y-%m-%d %H:%M:%S'
    format: '%(asctime)s\n%(name)s\n%(levelname)s\n%(funcName)s (%(filename)s:%(lineno)d)\n%(message)s'
  simple:
    datefmt: '%m/%d/%Y %I:%M:%S %p'
    format: '%(asctime)s, %(message)s'
handlers:
  console_handler:
    class: logging.StreamHandler
    formatter: simple
    level: INFO
    stream: ext://sys.stdout
  file_handler:
    backupCount: 20
    class: logging.handlers.RotatingFileHandler
    encoding: utf8
    filename: log.log
    formatter: simple
    level: INFO
    maxBytes: 10485760
  web_handler:
    class: mpetk.mpeconfig.log.WebHandler
    formatter: log_server
    host: eng-logtools.corp.alleninstitute.org
    level: DEBUG
    port: 9000
loggers:
  web_logger:
    handlers:
      - console_handler
      - file_handler
      - web_handler
    level: DEBUG
    propagate: false
root:
  handlers:
    - console_handler
    - file_handler
    - web_handler
  level: INFO
  propagate: false
version: 2
"""

log_record_factory = logging.getLogRecordFactory()
q = Queue()
queue_handlers = {}

logging_level_map = {"START_STOP": logging.WARNING + 5, "ADMIN": logging.WARNING + 6, "LIMS": logging.WARNING + 7,
                     "MTRAIN": logging.WARNING + 8, "SLIMS":logging.WARNING + 9}


def setup_logging(project_name: str, local_log_path: str, log_config: dict, send_start_log: bool, version: str,
                  rig_id: str = None, comp_id: str = None, always_pass_exc_info=False):
    """
    Logging setup consists of
      1.  applying the logging configuration to the Python logging module
      2.  injecting additional data into the log records via the log factory
      3.  sending a start log and registering to send a stop log
    :param project_name: The name of the configuration, usually project name, you want to find
    :param local_log_path: The path to store log files
    :param log_config:  The dictionary containing the logging configuration
    :param send_start_log: Whether to send a log to the webserver (not desirable for libraries) [default = True]
    :param version: The version of the software to record in the log record
    :param rig_id: Rig ID Override
    :param comp_id: Comp ID Override
    :param always_pass_exc_info: whether to always check for exc_info
    """

    # Process all handlers from default logging configs + custom project logging configs
    handlers = log_config["handlers"]
    for handler in handlers:
        # Configure all file handlers
        if "FileHandler" in handlers[handler]["class"] and "filename" in handlers[handler]:
            if handler == "file_handler":  # Default handler, insert project name to directory path
                logfile = f"{os.path.dirname(local_log_path)}/{project_name}"
                handlers["file_handler"]["filename"] = f"{logfile}.log"

            # Create directory if it does not exist (needed or else logging configuration will fail)
            os.makedirs(os.path.dirname(handlers[handler]["filename"]), exist_ok=True)

    session_parts = [str(datetime.datetime.now()), platform.node(), str(os.getpid())]
    aibs_session = md5((''.join(session_parts)).encode("utf-8")).hexdigest()[:7]

    def record_factory(*args, **kwargs):
        record = log_record_factory(*args, **kwargs)
        if not record.exc_info and always_pass_exc_info:
            record.exc_info = sys.exc_info()
            record.exc_text = traceback.format_exc()
        record.rig_name = rig_id or os.getenv("aibs_rig_id", "undefined")
        record.comp_id = comp_id or os.getenv("aibs_comp_id", "undefined")
        record.version = version
        record.project = project_name
        record.log_session = aibs_session
        if type(record.msg) is str:
            record.msg = record.msg if record.msg and record.msg[-1] == ',' else record.msg + ','
        if isinstance(record.msg, dict):
            record.msg = ", ".join([str(item) for keyval in record.msg.items() for item in keyval])
        return record
    logging.setLogRecordFactory(record_factory)

    """ Uses dictionary to configure the logging module. Dictionary pulls info config from:
            1. defaults: defined above (caches locally after running once) OR pulled from local config file
            2. logging_v2" from a custom project [Optional]
    """
    logging.config.dictConfig(log_config)

    for level_name, level_no in logging_level_map.items():
        def level_func(message, level=level_no, *args, **kws):
            if logging.root.isEnabledFor(level):
                logging.root._log(level, message, args, extra=kws.get("extra", {}))  # noqa

        logging.addLevelName(level_no, level_name)
        setattr(logging, level_name.lower(), level_func)

    if send_start_log:
        logging.log(logging_level_map["START_STOP"],
                    f"Action, Start, log_session, {aibs_session}, WinUserID, {getpass.getuser()},")

        def send_stop_log():
            logging.log(logging_level_map["START_STOP"],
                        f"Action, Stop, log_session, {aibs_session}, WinUserID, {getpass.getuser()},")

        atexit.register(send_stop_log)


class WebHandler(logging.handlers.SocketHandler):
    """
    Specialized socket handler that inspects the record dict for the attribute weblog.  If this attribute exists,
    logs of level INFO and higher will propagate to the log server.  This allows the following syntax:
    logging.info('My project is starting up', extra = {'weblog': True})
    """

    def __init__(self, host, port):
        super().__init__(host, port)

    def emit(self, record):
        if not getattr(record, "emit_exc", False):
            record.exc_info = None
            record.exc_text = None

        if record.levelno > logging.INFO:
            super().emit(record)

        elif getattr(record, "weblog", False):
            super().emit(record)


def get_queue_handler(name: str = "", queue: Queue = None, max_size: int = 1000, log_level: int = logging.INFO,
                      logger: logging.Logger = None) -> logging.handlers.QueueHandler:
    """
       QueueHandlers are a place to aggregate logs for review internally in your app.  For example, a status bar might
       want to create a queue, so it can view logs and add their text to the status bar without messing up locationgit quit
       information.
       You can create arbitrarily named queues and reference them later in your application.  If a handler with name
       already exists, that will be returned to you.

        :param name: [default] The name of the handler.  The default is "default"
        :param max_size: [1000] The number of logs the queue can contain.  If full, insertion of logs will block.
        :param log_level: [logging.INFO] The log level (INFO, WARNING, ERROR, etc)
        :param logger: [root] A logger on which to attach the handler.
        :param queue: [None] A queue object to pass to a new QueueHandler.  One will be created if queue=None
        :returns handler:  The QueueHandler you requested
    """

    name = name or "default"
    if name in queue_handlers:
        return queue_handlers[name]

    queue = queue or Queue(maxsize=max_size)
    handler = logging.handlers.QueueHandler(queue)
    handler.setLevel(log_level)

    logger = logger or logging.getLogger()
    logger.addHandler(handler)
    queue_handlers[name] = handler

    return handler
