import logging
from mpetk import mpeconfig

c = mpeconfig.source_configuration("mouse_director", version="fake", send_start_log=False, always_pass_exc_info=True)

a = {'b': 0}
try:
   print(a['c'])
except Exception:
    logging.warning("Ignore me")




