# -*- coding: utf-8 -*-

import logging
from logging.handlers import SocketHandler
import os
import socket

__author__ = """ben sutton"""
__email__ = "ben.sutton@alleninstitute.org"
__version__ = "1.2.7"

from .config_server import ConfigServer  # noqa
from .mpeconfig import fetch_configuration
from .mpeconfig import source_configuration  # noqa
from .mpeconfig import source_configuration as source_project_configuration  # noqa

# module_version = __version__
# module_name = 'mpeconfig_27x'
#
#
# class LogPy2(SocketHandler):
#     def __init__(self, host, port):
#         super(LogPy2, self).__init__(host, port)
#         self.host = host
#         self.port = port
#
#     def emit(self, record):
#         if record.levelno <= logging.INFO and not hasattr(record, 'weblog'):
#             return
#         record.rig_name = os.getenv('aibs_rig_id', 'unknown')
#         record.comp_id = os.getenv('aibs_comp_id', socket.gethostname())
#         record.version = module_version
#         record.project = module_name
#         super(LogPy2, self).emit(record)
#
#
# handler = LogPy2('aibspi', 9000)
# rootlogger = logging.getLogger()
# rootlogger.setLevel(logging.INFO)
# rootlogger.addHandler(handler)
