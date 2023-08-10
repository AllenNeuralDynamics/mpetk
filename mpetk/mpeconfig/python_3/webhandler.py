import logging.handlers
import queue

log_qs = {}


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


def get_q_handler(name="", max_size=1000, log_level=logging.INFO, logger=None):
    name = name or "default"
    if name in log_qs:
        return log_qs[name]
    logger = logger or logging.getLogger()
    q = queue.Queue(maxsize=max_size)
    handler = logging.handlers.QueueHandler(q)
    handler.setLevel(log_level)
    logger.addHandler(handler)
    log_qs[name] = handler
