import os
import pathlib as pl
from configparser import ConfigParser
import toml
import yaml
import json
from enum import Enum, auto
from typing import Optional
import logging

import keyring
from pykeepass.pykeepass import PyKeePass, Entry, Group

from ..mpeconfig import source_configuration


# # Alternate way to specify config with pydantic validation like waterlog
# class KeepassConfig():
#     dbfile: pl.Path
#     keyfile: Optional[pl.Path]
#     password: Optional[str]

# class Config():
#     secrets_folder: pl.Path = r"C:\\ProgramData\AIBS_MPE\.secrets"
#     keepass_databases: list[KeepassConfig] = [KeepassConfig(
#         dbfile=r"\\allen\aibs\mpe\keepass\sipe_sw_passwords.kdbx",
#         keyfile=r"C:\\ProgramData\AIBS_MPE\.secrets\sipe_sw_passwords.keyx",
#     )]


CONFIG = {
    "secrets_folder": r"C:\\ProgramData\AIBS_MPE\.secrets",
    "keepass_databases": [
        {
            "dbfile": r"\\allen\aibs\mpe\keepass\sipe_sw_passwords.kdbx",
            "keyfile": r"C:\\ProgramData\AIBS_MPE\.secrets\sipe_sw_passwords.keyx",
        }
    ],
}

CONFIG.update(source_configuration("mpe_credentials", fetch_logging_config=False, send_start_log=False))

SECRETS_FOLDER = pl.Path(CONFIG["secrets_folder"])


class CredentialManager:

    def __init__(
        self,
        secrets_folder: pl.Path = SECRETS_FOLDER,
        keepass_databases:list[dict[str,str]]=CONFIG['keepass_databases'],
    ):
        self.secrets_folder = secrets_folder
        self._databases: dict[str,PyKeePass] = {}

        for dbinfo in keepass_databases:
            self.add_keepass_db(**dbinfo)

    def add_keepass_db(self, dbfile, keyfile=None, password=None, name=None):
        """ Add a keepass database with either a keyfile or password, and an optional name
        
        Parameters
        ----------
        :param dbfile: full path to keepass database file (.kdbx)
        :param keyfile: optional, full path to keepass keyfile
        :param password: optional, password to database
        :param name: optional name for database. if not provided, will use filename
        """
        try:
            if password:
                kpdb = PyKeePass(dbfile, password=password)
            else:
                kpdb = PyKeePass(dbfile, keyfile=keyfile)
        except Exception as e:
            logging.warning(
                f"Warning, Could not initialize keepass database, Database File, {dbfile}, Message, {repr(e)}"
            )

        if name == None:
            name = pl.Path(dbfile).stem

        self._databases[name] = kpdb

    def write_local_credentials(
        self,
        groupname: str,
        file: pl.Path,
        database_name:Optional[str] = None,
        extra_keys: tuple[str] = (),
        env_variable: Optional[str] = None,
        format: str = "ini",
        **keepass_kwargs,
    ):
        """Writes the entries contained in a keepass group into a local file.

        Parameters
        ----------
        :param groupname: The name of the keepass group to extract
        :param file: Full desired file path of the generated credentials file
        :param extra_keys:  optional keepass.Entry fields to include in config file sections
            other than those in entry.custom_properties. e.g. 'url', 'username'
        :param env_variable: str, optional, If present, will set an environment variable
            with this name and value equal to the cred file path
        :param format: one of ('toml','yaml','json','ini'), default 'ini'
            File format with which to write credentials file

        """

        groups = self.get_keepass_groups(database_name=database_name,**keepass_kwargs)
        if len(groups) == 0:
            raise LookupError(f'No groups found in keepass databases matching {keepass_kwargs}')
        elif len(groups) == 1:
            group = groups[0]
        else:
            raise LookupError(f'Multiple groups found in keepass databases matching {keepass_kwargs}')
        
        data = {}
        for entry in group.entries:
            data[entry.title] = entry.custom_properties
            for k in extra_keys:
                if hasattr(entry, k) and entry.__getattribute__(k) is not None:
                    data[entry.title][k] = entry.__getattribute__(k)

        with open(file, "w") as f:
            if dump_func := {"toml": toml.dump, "yaml": yaml.dump, "json": json.dump}.get(format):
                dump_func(data, f)
            elif format == "ini":
                parser = ConfigParser()
                parser.read_dict({k: v for k, v in data.items() if v})
                parser.write(f)

        if env_variable is not None:
            os.environ[env_variable] = str(file)

    def get_credentials(self, **kwargs) -> list:
        # if group in self._keepass
        creds = []
        for name,db in self._databases.items():
            creds.extend(db.find_entries(**kwargs))
        
        creds.append(keyring.get_credential(*list(kwargs.values())[:1]))
        return creds

    def validate_credential(self,**kwargs):
        creds = self.get_credentials(**kwargs)
        return len(creds) > 0
    
    def get_keepass_groups(self,database_name=None,**kwargs)->list[Group]:

        # ugh
        if database_name in self._databases.items():
            dbs = [self._databases[database_name]]
        else:
            dbs = self._databases.values()

        groups = []
        for db in dbs:
            groups.extend(db.find_groups(**kwargs))
        return groups

    def get_keepass_entries(self,dbname:str, *args, **kwargs) -> list[Entry]:
        creds = []
        for name,db in self._databases.items():
            creds.extend(db.find_groups(**kwargs))
        return creds

    def get_username_password(self,dbname, title: str, *args, **kwargs) -> tuple[str, str]:
        entry: Entry = self._databases[dbname].find_entries(title, first=True, *args, **kwargs)
        return entry.username, entry.password
    
    ## Keyring API

    def get_keyring_username(self, group: str, username: str, title: str = None):
        cred = keyring.get_credential(group, None)
        if cred is not None:
            return cred.username

    def get_keyring_password(self, group: str, username: str, title: str = None) -> str:
        if title is not None:
            service_name = f"{title}@{group}" # This is how keyring handles collisions
        else:
            service_name = group
        return keyring.get_password(service_name, username)

    def set_keyring_password(self, group: str, username: str, password: str):
        if self.get_keyring_password(group,username):
            pass
        keyring.set_password(group, username, password)


def setup_allen_services_api_credentials(credential_manager: Optional[CredentialManager] = None):
    if credential_manager is None:
        credential_manager = CredentialManager(CONFIG)

    credential_manager.write_local_credentials(
        "Allen Services API",
        file=credential_manager.secrets_folder / "allen_services_api_config.ini",
        extra_keys=["url"],
        env_variable="ALLEN_SERVICE_API_CONFIG",
        format="ini",
    )


def setup_aws_credentials(credential_manager: Optional[CredentialManager] = None):
    if credential_manager is None:
        credential_manager = CredentialManager(CONFIG)

    credential_manager.write_local_credentials(
        "AWS",
        file=pl.Path.home() / ".aws" / "credentials-test",
        format="ini",
    )

    # alternately
    import os
    os.environ['AWS_ACCESS_KEY_ID'] = credential_manager.get_credential()#'AKIA3VVOXUPG2YKLRNK2'
    os.environ['AWS_SECRET_ACCESS_KEY'] = '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'
