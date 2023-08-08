"""
A small module to specifically get MPE Configurations form our zookeeper quorum.
It supports local configurations and default configurations in the cases where zookeeper is not available.
"""
import atexit
import copy
import datetime
import getpass
import logging
import logging.config
import logging.handlers
import os
import platform
import shutil
from collections import namedtuple
from enum import Enum, auto
from hashlib import md5

import yaml
from yaml import loader
from yaml.parser import ParserError

from .config_server import ConfigServer

# yaml.add_representer(dict, lambda self, data: yaml.representer.SafeRepresenter.represent_dict(self, data.items()))

log_factory = logging.getLogRecordFactory()
resource_path = f"{os.path.dirname(__file__)}/resources"

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
    debug_file_handler:
        backupCount: 20
        class: logging.handlers.RotatingFileHandler
        encoding: utf8
        filename: debug.log
        formatter: detailed
        level: ERROR
        maxBytes: 10485760

    file_handler:
        backupCount: 20
        class: logging.handlers.RotatingFileHandler
        encoding: utf8
        filename: log.log
        formatter: simple
        level: INFO
        maxBytes: 10485760
    info_socket_handler:
        class: logging.handlers.SocketHandler
        formatter: log_server
        host: eng-logtools.corp.alleninstitute.org
        level: INFO
        port: 9000
    socket_handler:
        class: logging.handlers.SocketHandler
        formatter: log_server
        host: eng-logtools.corp.alleninstitute.org
        level: WARNING
        port: 9000
loggers:
    web_logger:
        handlers:
            - console_handler
            - debug_file_handler
            - info_socket_handler
        level: INFO
        propagate: false
    root:
        handlers:
            - console_handler
            - file_handler
            - debug_file_handler
            - socket_handler
        level: INFO
        propagate: false
version: 1
"""

default_config_dict = """
linux_install_paths:
    install: ~/.config/AIBS_MPE
    local_config: config
    local_log_config: logs
    python: /opt/mcpython3
services:
    log_server: eng-logtools.corp.alleninstitute.org:9000
    python_index: http://eng-logtools.corp.alleninstitute.org:3141/aibs/dev
    zookeeper: eng-logtools.corp.alleninstitute.org:2181
windows_install_paths:
    install: /ProgramData/AIBS_MPE
    local_config: config
    local_log_config: logs
    python: /mcpython3
"""

aibs_session = ""


class SerializationTypes(Enum):
    YAML = auto(),
    JSON = auto(),
    XML = auto(),
    PLAINTEXT = auto(),
    PROTOBUF = auto(),
    INI = auto()


class WebHandler(logging.handlers.SocketHandler):
    """
    Specialized socket handler that inspects the record dict for the attribute weblog.  If this attribute exists,
    logs of level INFO and higher will propagate to the log server.  This allows the following syntax:
    logging.info('My project is starting up', extra = {'weblog': True})
    """

    def __init__(self, host, port):
        super().__init__(host, port)

    def emit(self, record):
        if hasattr(record, "weblog"):
            super().emit(record)


def source_configuration(
    project_name: str,
    hosts: str = "eng-tools.corp.alleninstitute.org:2181",
    use_local_config: bool = False,
    send_start_log: bool = True,
    fetch_logging_config: bool = True,
    fetch_project_config: bool = True,
    version: str = None,
    rig_id: str = None,
    comp_id: str = None,
    serialization: str = "yaml"
):
    """
    Connects to the quorum and searches for the following paths:
    /mpe_defaults/[configuration | logging]
    /[projects | hardware]/<project_name>/defaults/[configuration | logging]
    /rigs/<rig_id>/[projects | hardware]/[configuration | logging]
    /rigs/<rig_id>

    :param fetch_project_config: set to False if you do not want to source a project configuration
    :param fetch_logging_config: set to False if you do not want to source a logging configuration
    :param project_name: The name of the configuration, usually project name, you want to find
    :param use_local_config: whether or not to use the local cache [default = True]
    :param hosts: The quorum to connect to (currently there is only aibspi)
    :param send_start_log: Whether or not to send a log to the webserver (not desirable for libraries) [default = True]
    :param version: Current software version.  Can be specified but will be auto-detected if None
    :param rig_id: override for rig_id
    :param comp_id: override for comp_id
    :raises: KeyError if it can't find the default configuration
    :return:
    """

    if use_local_config:
        return build_local_configuration(
            project_name, fetch_logging_config, fetch_project_config, send_start_log, version, serialization

        )

    with ConfigServer(hosts=hosts) as zk:
        """
        Connection to the Zookeeper Server
        """

        if not version:
            version = "unknown"

        if not zk.connected:
            print("Looking for local configurations ...")
            return build_local_configuration(project_name, fetch_logging_config, fetch_project_config, send_start_log)

        mpe_defaults = fetch_configuration(zk, f"/mpe_defaults/configuration", required=True)
        local_log_path, local_config_path = get_platform_paths(mpe_defaults, project_name)
        project_config = None

        if fetch_project_config:
            project_config = compile_remote_configuration(zk, project_name, "configuration", rig_id=rig_id,
                                                          comp_id=comp_id, serialization=serialization)
            local_log_path, local_config_path = get_platform_paths(project_config, project_name)
            ensure_path(local_config_path)
            cache_remote_config(project_config, local_config_path)

        if fetch_logging_config:
            ensure_path(os.path.expandvars(local_log_path))
            log_config = compile_remote_configuration(zk, project_name, "logging", rig_id=rig_id, comp_id=comp_id)
            setup_logging(project_name, os.path.expandvars(local_log_path), log_config, send_start_log, version=version,
                          rig_id=rig_id,
                          comp_id=comp_id)
            cache_remote_config(log_config, local_log_path)

        return project_config


def ensure_path(path: str):
    """
    if the path for logging and configuration storage does not exist, make it.  Logging configuration will fail if
    the directory does not exist.
    :param path: A path to check and create
    """

    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        os.makedirs(directory)


def build_local_configuration(
    project_name, fetch_logging_config=True, fetch_project_config=True, send_start_log=True, version=None,
    serialization="yaml"
):
    """
    Builds logging and project configuration from local files and mpeconfig defaults as necessary.  This can be useful
    for one off configurations for testing when you don't want to edit the zookeeper rig / comp configuration.
    :param fetch_project_config: set to False if you do not want to source a project configuration
    :param fetch_logging_config: set to False if you do not want to source a logging configuration
    :param project_name: The name of the configuration, usually project name, you want to find
    :param send_start_log: Whether or not to send a log to the webserver (not desirable for libraries) [default = True]
    :param version: Module version to add to log_record
    :param serialization: What document format to parse
    :return:
    """
    default_config = yaml.load(default_config_dict, Loader=loader.Loader)
    default_logging = yaml.load(default_logging_dict, Loader=loader.Loader)
    local_log_path, local_config_path = get_platform_paths(default_config, project_name)

    # setup logging configuration
    if fetch_logging_config:
        if os.path.isfile(local_log_path):
            log_config = yaml.load(open(local_log_path, "r"), Loader=loader.Loader)
        else:
            print("Didn't find a local logging configuration:  Using the default MPE logging.")
            log_config = default_logging
            cache_remote_config(log_config, local_log_path)
        setup_logging(project_name, local_log_path, log_config, send_start_log, version)

    # setup project configuration
    if fetch_project_config:
        if os.path.isfile(local_config_path):
            project_config = yaml.load(open(local_config_path, "r"), Loader=loader.Loader)
            project_config = deep_merge(copy.deepcopy(default_config), project_config)
        else:
            logging.warning(f"Could not find a local project configuration: {local_config_path}.")
            project_config = default_config

        return project_config


def setup_logging(project_name: str, local_log_path: str, log_config: dict, send_start_log: bool, version: str,
                  rig_id: str = None, comp_id: str = None):
    """
    Logging setup consists of
      1.  applying the logging configuration to the Python logging module
      2.  injecting additional data into the log records via the log factory
      3.  adding a special socket handler to send data to the AIBSPI log server
      4.  sending a start log and registering to send a stop log
    :param project_name: The name of the configuration, usually project name, you want to find
    :param local_log_path: The path to store log files
    :param log_config:  The dictionary containing the logging configuration
    :param send_start_log: Whether or not to send a log to the webserver (not desirable for libraries) [default = True]
    :param version: The version of the software to record in the log record
    :param rig_id: Rig ID Override
    :param comp_id: Comp ID Override
    """
    logging_level_map = {"START_STOP": logging.WARNING + 5, "ADMIN": logging.WARNING + 6, "LIMS": logging.WARNING + 7,
                         "MTRAIN": logging.WARNING + 8}

    logfile = f"{os.path.dirname(local_log_path)}/{project_name}"
    log_config["handlers"]["file_handler"]["filename"] = f"{logfile}.log"
    log_config["handlers"]["debug_file_handler"]["filename"] = f"{logfile}_error.log"

    session_parts = [str(datetime.datetime.now()), platform.node(), str(os.getpid())]

    aibs_session = md5((''.join(session_parts)).encode("utf-8")).hexdigest()[:7]

    def record_factory(*args, **kwargs):
        record = log_factory(*args, **kwargs)
        record.rig_name = rig_id or os.getenv("aibs_rig_id", "undefined")
        record.comp_id = comp_id or os.getenv("aibs_comp_id", "undefined")
        record.version = version
        record.project = project_name
        if type(record.msg) is str:
            record.msg = record.msg if record.msg and record.msg[-1] == ',' else record.msg + ','
        return record

    logging.setLogRecordFactory(record_factory)

    logging.config.dictConfig(log_config)

    host = log_config["handlers"]["socket_handler"]["host"]
    port = log_config["handlers"]["socket_handler"]["port"]
    handler = WebHandler(host, int(port))
    handler.level = logging.INFO
    for level_name, level_no in logging_level_map.items():
        def level_func(message, level=level_no, *args, **kws):
            if logging.root.isEnabledFor(level):
                logging.root._log(level, message, args, extra=kws.get("extra", {}))

        logging.addLevelName(level_no, level_name)
        setattr(logging, level_name.lower(), level_func)

    logging.getLogger().addHandler(handler)
    logging.getLogger(project_name).addHandler(handler)

    if send_start_log:
        logging.log(
            logging_level_map["START_STOP"],
            f"Action, Start, log_session, {aibs_session}, WinUserID, {getpass.getuser()},")

        def send_stop_log():
            logging.log(
                logging_level_map["START_STOP"],
                f"Action, Stop, log_session, {aibs_session}, WinUserID, {getpass.getuser()},")

        atexit.register(send_stop_log)


def get_platform_paths(config, project_name):
    """
    Installation and other meta-data is described in the mpe defaults configuration.  This function figures out the
    proper pathing for a given OS based on that coniguration and returns it.
    :param config: configuration dictionary containing the install paths
    :param project_name: The name of the configuration, usually project name, you want to find
    :return: (local_log_path: str, local_config_path: str)
    """
    if "windows" in platform.platform().lower():
        paths = config["windows_install_paths"]
    else:
        paths = config["linux_install_paths"]
        paths["install"] = os.path.expanduser(paths["install"])
    local_log_path = f'{paths["install"]}/{project_name}/{paths["local_log_config"]}/logging.yml'
    local_config_path = f'{paths["install"]}/{project_name}/{paths["local_config"]}/{project_name}.yml'
    return os.path.expandvars(local_log_path), os.path.expandvars(local_config_path)


def compile_remote_configuration(zk, project_name, config_type="configuration", rig_id=None, comp_id=None,
                                 serialization='yaml'):
    """
    Look for various pieces of the configuration in the zookeeper tree
    :param zk: An active zookeeper connection
    :param project_name: the project name to look for
    :param config_type [hardware | projects ]
    :param rig_id: Rig ID Override
    :param comp_id: Comp ID Override
    :return: Dictionary of merged configurations
    """

    project_config = {}
    rig_config = {}
    comp_config = {}
    shared_config = {"shared": {}}

    rig_name = rig_id or os.environ.get("aibs_rig_id", "")
    comp_name = comp_id or os.environ.get("aibs_comp_id", "")

    mpe_defaults = fetch_configuration(zk, f"/mpe_defaults/{config_type}", required=True, serialization=serialization)

    if zk.exists(f"/projects/{project_name}"):
        project_config = fetch_configuration(zk, f"/projects/{project_name}/defaults/{config_type}",
                                             serialization=serialization)
        rig_config = fetch_configuration(zk, f"/rigs/{rig_name}/projects/{project_name}/{config_type}",
                                         serialization=serialization)
        comp_config = fetch_configuration(zk, f"/rigs/{comp_name}/projects/{project_name}/{config_type}",
                                          serialization=serialization)

        shared_rig_config = fetch_configuration(zk, f"/rigs/{rig_name}")
        shared_comp_config = fetch_configuration(zk, f"/rigs/{comp_name}")

    elif zk.exists(f"/hardware/{project_name}"):
        project_config = fetch_configuration(zk, f"/hardware/{project_name}/defaults/{config_type}",
                                             serialization=serialization)
        rig_config = fetch_configuration(zk, f"/rigs/{rig_name}/hardware/{project_name}/{config_type}",
                                         serialization=serialization)
        comp_config = fetch_configuration(zk, f"/rigs/{comp_name}/hardware/{project_name}/{config_type}",
                                          serialization=serialization)
        shared_rig_config = fetch_configuration(zk, f"/rigs/{rig_name}", serialization=serialization)
        shared_comp_config = fetch_configuration(zk, f"/rigs/{comp_name}", serialization=serialization)

    else:
        if config_type != "logging":
            logging.warning(f"Found no configuration available for {project_name}")
        return mpe_defaults

    if serialization == 'plain_text':
        return project_config.decode()

    rtn_dict = deep_merge(copy.deepcopy(mpe_defaults), project_config)
    rtn_dict = deep_merge(copy.deepcopy(rtn_dict), rig_config)
    rtn_dict = deep_merge(copy.deepcopy(rtn_dict), comp_config)
    if config_type != "logging":
        rtn_dict = deep_merge(copy.deepcopy(rtn_dict), shared_config)
        shared_dict = deep_merge(copy.deepcopy(shared_rig_config), shared_comp_config)
        if shared_dict:
            rtn_dict['shared'] = shared_dict
    return rtn_dict


def fetch_configuration(server, config_path, required=False, serialization='yaml'):
    """
    Pull a configuration from a zk path and deserialize it.
    :param server: active zk connection
    :param config_path: path to pull data from
    :param required: whether or not it has to exist [default = False]
    :return: YAML deserialization
    :raises: AttributeError if required and can't be deserialized
    :raises: KeyError if required but not found
    """
    config = {}
    try:
        config = server[config_path]
        if serialization == 'yaml':
            config = yaml.load(server[config_path], Loader=loader.Loader)
    except (AttributeError, ParserError) as err:
        if required:
            logging.error(f"{config_path} is not valid YAML: {err}")
            exit(1)
    except KeyError:
        if required:
            logging.error(f"Could not find {config_path}.")
            exit(1)

    return config if config else {}


def md5_equal(a, b):
    a_s = str(a).encode()
    b_s = str(b).encode()
    return md5(a_s).hexdigest() == md5(b_s).hexdigest()


def cache_remote_config(configuration, config_path):
    """
    Creates a directory and saves the configuration data.  if a configuration exists, it will be renamed with a
    timestamp.
    :param configuration: dictionary to save to dist
    :param config_path: fully qualified path to save configuration.
    :return:
    """
    config_path = os.path.expandvars(config_path)
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    if os.path.isfile(config_path):
        config = yaml.load(open(config_path), Loader=loader.Loader)
        if config == configuration:
            return

        timestamp = datetime.datetime.strftime(datetime.datetime.now(), "%y%m%d-%H%M%S")
        backup_file = f"{config_path}.{timestamp}.bck"
        logging.info(f"Copying previous configuration to {backup_file}")
        shutil.copyfile(config_path, backup_file)

    with open(config_path, "w") as f:
        yaml.dump(configuration, f, default_flow_style=False)


def dict_to_namedtuple(dictionary):
    """
    Utility function to change dictionaries to namedtuples recursively
    :param dictionary: the dictionary to convert
    :return: a named tupled version of the dictionary contents
    """
    for key, value in dictionary.items():
        if isinstance(value, dict):
            dictionary[key] = dict_to_namedtuple(value)
    return namedtuple("configDict", dictionary.keys())(**dictionary)


def deep_merge(dict_prime, dict_mod):
    """
    Utility function to do a deep merge on dictionaries.  Recommended to deep copy dict_prime when it's passed in as
    an argument as the original dictionary values are modified.  If a key is a list in both dicts, does not combine or
    merge these lists.  Instead it favors the list from dict_mod.
    :param dict_prime: The dictionary to be merged into
    :param dict_mod: The dictionary to merge into the first parameter
    :return: the deep merged dictionary
    """
    for key, value in dict_mod.items():
        if isinstance(value, dict):
            if key not in dict_prime:
                dict_prime[key] = type(value)()  # For subclasses of dict
            deep_merge(dict_prime[key], dict_mod[key])
        else:
            dict_prime[key] = value
    return dict_prime
