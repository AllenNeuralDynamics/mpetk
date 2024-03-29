import pathlib as pl

import pytest

from mpetk.credentials import credentials

@pytest.fixture
def creds():
    return credentials.CredentialManager()

def test_write_creds_files_manually(creds:credentials.CredentialManager):

    # Write DATS/PTS credentials
    creds.write_local_credentials(
        "Allen Services API",
        file=creds.secrets_folder / "allen_services_api_config.ini",
        extra_keys=["url"],
        env_variable="ALLEN_SERVICE_API_CONFIG",
        format="ini",
    )

    # Write AWS credentials
    creds.write_local_credentials(
        "AWS",
        file=pl.Path.home() / ".aws" / "credentials-test",
        format="ini",
    )

def test_write_creds_files_builtin():
    credentials.setup_allen_services_api_credentials()
    credentials.setup_aws_credentials()



@pytest.mark.parametrize("username,password,valid", (("")))
def test_pw_validation(creds:credentials.CredentialManager, username, password, valid):
    username = input("Enter Username:")
    password = input("Enter Password:")

    creds.validate_credential(username=username, password=password)


def test_extra_db(creds:credentials.CredentialManager):

    creds.add_keepass_db(
        r"C:\ProgramData\AIBS_MPE\.secrets\sipe_infrastructure.kdbx",
        keyfile=r"C:\ProgramData\AIBS_MPE\.secrets\sipe_infrastructure.keyx",
    )

    creds.get_credentials(title="gitlab user token")


def test_different_config(creds:credentials.CredentialManager):
    cfg = {
        # "secrets_folder": r"C:\\ProgramData\AIBS_MPE\.secrets",
        "keepass_databases": [
            {
                "dbfile": r"\\allen\aibs\mpe\keepass\sipe_sw_passwords.kdbx",
                "keyfile": r"C:\\ProgramData\AIBS_MPE\.secrets\sipe_sw_passwords.keyx",
            },
            {
                "dbfile": r"C:\ProgramData\AIBS_MPE\.secrets\sipe_infrastructure.kdbx",
                "keyfile": r"C:\ProgramData\AIBS_MPE\.secrets\sipe_infrastructure.keyx",
            }
        ],
    }

    # creds = credentials.CredentialManager(keepass_databases=cfg['keepass_databases'])
    creds = credentials.CredentialManager()
    
    creds.get_credentials(title="gitlab user token")
    creds.get_credentials(title='SLIMS')


def test_ala_mouse_director(dbfile):
    creds = credentials.CredentialManager(keepass_databases=[])
    db_pw = creds.get_keyring_password('sipe','keepass')
    creds.add_keepass_db(dbfile,password=db_pw)

test_write_creds_files_manually(credentials.CredentialManager())