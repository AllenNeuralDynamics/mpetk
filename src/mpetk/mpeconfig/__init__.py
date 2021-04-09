import sys

PYTHON_VERSION = int(sys.version[0])

if PYTHON_VERSION == 2:
    from .python_2 import *

if PYTHON_VERSION == 3:
    from .python_3 import *

