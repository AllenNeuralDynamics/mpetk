import time


from mpetk.mpeconfig.python_3.mpeconfig import source_configuration
from mpetk.mpeconfig.python_3.session_id_db import GlobalSessionID, CONFIG


def test():

    host = CONFIG["host"]
    port = CONFIG["port"]

    sm1 = GlobalSessionID(host=host, port=port)
    sm2 = GlobalSessionID(host=host, port=port)
    sm3 = GlobalSessionID(host=host, port=port)

    # print(sm1.session, sm2.session, sm3.session)

    sm1.start_session(None)

    time.sleep(0.5)

    print(sm1.session, sm2.session, sm3.session)

    # sm2.start_session(None)

    assert sm1.session == sm2.session == sm3.session

def test_source_config():
    camstim = source_configuration('camstim',send_start_log=False)
    mvr = source_configuration('mvr',send_start_log=False)
    
if __name__ == "__main__":
    test()
