from typing import Optional

from . import mpeconfig
from . import piddl
from . import zro
from . import teams
from pykeepass import PyKeePass

__version__ = '0.5.2.dev2'


def kp_db(key_file=r'//allen/aibs/mpe/keepass/sipe_sw_passwords.kdbx',
          db_file=r'c:\ProgramData\AIBS_MPE\.secrets\sipe_sw_passwords.kdbx'):
    from pykeepass import PyKeePass
    return PyKeePass(db_file, keyfile=key_file)


def kp_query(key_file=r'//allen/aibs/mpe/keepass/sipe_sw_passwords.kdbx',
             db_file=r'c:\ProgramData\AIBS_MPE\.secrets\sipe_sw_passwords.kdbx',
             query: Optional[dict[str, any]]=None):


    keepass = kp_db(key_file, db_file)
    query = query or dict()

    # Query by group requires a group object rather than group name as str.
    if group_name := query.get("group"):
        query["group"] = keepass.find_groups(name=group_name, first=True)

    return keepass.find_entries(**query, first=True)
