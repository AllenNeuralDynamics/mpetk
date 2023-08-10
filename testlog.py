import logging
from mpetk.mpeconfig import ConfigServer, source_configuration

"""
c = ConfigServer()
c.start()
print(c.client_state)
print(c.connected)
"""

c = source_configuration("mouse_director")


