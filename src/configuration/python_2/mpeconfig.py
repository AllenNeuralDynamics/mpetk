"""
A small module to specifically get MPE Configurations form our zookeeper quorum.
It supports local configurations and default configurations in the cases where zookeeper is not available.
"""
from __future__ import print_function

import atexit
import copy
import datetime
import inspect
import logging
import logging.config
import logging.handlers
import os
import platform
import socket
import shutil
from collections import namedtuple
from hashlib import md5

import pip._internal.utils.misc
import yaml
from yaml import representer
from yaml.parser import ParserError
from yaml import loader

from .config_server import ConfigServer

# yaml.add_representer(dict, lambda self, data: yaml.representer.SafeRepresenter.represent_dict(self, data.items()))

# config = mpeconfig.source_configuration("bfi", version="testv0.1.2", fetch_logging_config=True)

# log_factory = logging.getLogRecordFactory()
resource_path = os.path.dirname(__file__) + "/resources"
default_logging_dict = yaml.load(open(resource_path + "/mpe_defaults_logging.yml", "r"), Loader=loader.Loader)
default_config_dict = yaml.load(open(resource_path + "/mpe_defaults_configuration.yml", "r"), Loader=loader.Loader)

aibs_session = ""


class WebHandler(logging.handlers.SocketHandler):
    """
    Specialized socket handler that inspects the record dict for the attribute weblog.  If this attribute exists,
    logs of level INFO and higher will propagate to the log server.  This allows the following syntax:
    logging.info('My project is starting up', extra = {'weblog': True})
    """

    def __init__(self, host, port, module_name, module_version):
        super(WebHandler, self).__init__(host, port)
        self.module_name = module_name
        self.module_version = module_version

    def emit(self, record):

        if hasattr(record, "weblog") or (record.levelno > logging.INFO):
            record.rig_name = os.getenv('aibs_rig_id', 'unknown')
            record.comp_id = os.getenv('aibs_comp_id', socket.gethostname())
            record.version = self.module_version
            record.project = self.module_name
            super(WebHandler, self).emit(record)


def source_configuration(
    project_name,
    hosts="aibspi:2181",
    use_local_config=False,
    send_start_log=True,
    fetch_logging_config=True,
    fetch_project_config=True,
    version=None,
    rig_id=None,
    comp_id=None
):
    """
    Connects to the quorum and searches for the following paths:
    /mpe_defaults_27/[configuration | logging]
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
    :raises: KeyError if it can't find the default configuration
    :return:
    """

    if use_local_config:
        return build_local_configuration(
            project_name, fetch_logging_config, fetch_project_config, send_start_log, version
        )

    with ConfigServer(hosts=hosts) as zk:
        """
        Connection to the Zookeeper Server
        """

        if not version:
            version = "unknown"
            current_frame = inspect.currentframe()
            module_path = inspect.getouterframes(current_frame, 2)[1][1]  # this yields a file path
            for dist in pip._internal.utils.misc.get_installed_distributions():
                if dist.has_metadata("RECORD"):
                    lines = dist.get_metadata_lines("RECORD")
                    paths = [l.split(",")[0] for l in lines]
                elif dist.has_metadata("installed-files.txt"):
                    paths = dist.get_metadata_lines("installed-files.txt")
                else:
                    paths = []

                # This may need revision.  RECORD provides paths rooted at lib/site-packages so this could potentially
                # match the wrong file.  Need to ensure the root installation and the environment are both accounted for
                # correctly.
                filename = os.path.basename(module_path)
                for path in paths:
                    if filename in path:
                        version = dist.version

        if zk.client_state == "CLOSED":
            print("Looking for local configurations ...")
            return build_local_configuration(project_name, fetch_logging_config, fetch_project_config, send_start_log)

        mpe_defaults = fetch_configuration(zk, "/mpe_defaults_27/configuration", required=True)
        local_log_path, local_config_path = get_platform_paths(mpe_defaults, project_name)
        ensure_path(local_log_path)
        ensure_path(local_config_path)

        if fetch_logging_config:
            log_config = compile_remote_configuration(zk, project_name, "logging", rig_id = rig_id, comp_id = comp_id)
            setup_logging(project_name, local_log_path, log_config, send_start_log, version=version, rig_id = rig_id, comp_id = comp_id)
            cache_remote_config(log_config, local_log_path)

        if fetch_project_config:
            project_config = compile_remote_configuration(zk, project_name, "configuration", rig_id = rig_id, comp_id = comp_id)
            cache_remote_config(project_config, local_config_path)
            return project_config  # dict_to_namedtuple(project_config)


def ensure_path(path):
    """
    if the path for logging and configuration storage does not exist, make it.  Logging configuration will fail if
    the directory does not exist.
    :param path: A path to check and create
    """
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        os.makedirs(directory)


def build_local_configuration(
    project_name, fetch_logging_config=True, fetch_project_config=True, send_start_log=True, version=None
):
    """
    Builds logging and project configuration from local files and mpeconfig defaults as necessary.  This can be useful
    for one off configurations for testing when you don't want to edit the zookeeper rig / comp configuration.
    :param fetch_project_config: set to False if you do not want to source a project configuration
    :param fetch_logging_config: set to False if you do not want to source a logging configuration
    :param project_name: The name of the configuration, usually project name, you want to find
    :param send_start_log: Whether or not to send a log to the webserver (not desirable for libraries) [default = True]
    :param version: Module version to add to log_record
    :return:
    """
    local_log_path, local_config_path = get_platform_paths(default_config_dict, project_name)

    # setup logging configuration
    if fetch_logging_config:
        if os.path.isfile(local_log_path):
            log_config = yaml.load(open(local_log_path, "r"), Loader=loader.Loader)
        else:
            print("Didn't find a local logging configuration:  Using the default MPE logging.")
            log_config = default_logging_dict
            cache_remote_config(log_config, local_log_path)
        setup_logging(project_name, local_log_path, log_config, send_start_log, version)

    # setup project configuration
    if fetch_project_config:
        if os.path.isfile(local_config_path):
            project_config = yaml.load(open(local_config_path, "r"), Loader=loader.Loader)
            # project_config = {**default_config_dict, **project_config}
            project_config = deep_merge(copy.deepcopy(default_config_dict), project_config)

        else:
            logging.warning("Could not find a local project configuration: " + local_config_path + ".")
            project_config = default_config_dict

        return project_config


def setup_logging(project_name, local_log_path, log_config, send_start_log, version,  rig_id = None, comp_id = None):
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
    """
    logging_level_map = {"START_STOP": logging.WARNING + 5, "ADMIN": logging.WARNING + 6}
    logfile = os.path.dirname(local_log_path) + "/" + project_name
    log_config["handlers"]["file_handler"]["filename"] = logfile + ".log"
    log_config["handlers"]["debug_file_handler"]["filename"] = logfile + "_error.log"

    aibs_session = md5(str(datetime.datetime.now())).hexdigest()[:7]

    logging.config.dictConfig(log_config)

    host = '10.128.108.106' # log_config["handlers"]["socket_handler"]["host"]
    port = 9000 # log_config["handlers"]["socket_handler"]["port"]
    handler = WebHandler(host, int(port), project_name, version)
    handler.level = logging.INFO

    for level_name, level_no in logging_level_map.items():

        def level_func(message, level=level_no, *args, **kws):
            if logging.root.isEnabledFor(level):
                logging.root._log(level, message, args, extra=kws.get("extra", {}))

        logging.addLevelName(level_no, level_name)
        setattr(logging, level_name.lower(), level_func)

    logging.getLogger().addHandler(handler)

    if send_start_log:
        logging.log(logging_level_map["START_STOP"], "Action, Start, log_session, " + aibs_session)

        def send_stop_log():
            logging.log(logging_level_map["START_STOP"], "Action, Stop, log_session, " + aibs_session)

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
    local_log_path = paths["install"] + "/" + project_name + "/" + paths["local_log_config"] + "/logging.yml"
    local_config_path = paths["install"] + "/" + project_name + "/" + paths["local_config"] + "/" + project_name + ".yml"
    return local_log_path, local_config_path


def compile_remote_configuration(zk, project_name, config_type="configuration", rig_id = None, comp_id = None):
    """
    Look for various pieces of the configuration in the zookeeper tree
    :param zk: An active zookeeper connection
    :param project_name: the project name to look for
    :param config_type [hardware | projects ]
    :return: Dictionary of merged configurations
    """

    rig_name = rig_id or os.environ.get("aibs_rig_id", "")
    comp_name = comp_id or os.environ.get("aibs_comp_id", "")

    mpe_defaults = fetch_configuration(zk, "/mpe_defaults_27/" + config_type, required=True)

    if zk.exists("/projects/" + project_name + "/defaults/" + config_type):
        project_config = fetch_configuration(zk, "/projects/" + project_name + "/defaults/" + config_type)
        rig_config = fetch_configuration(zk, "/rigs/" + rig_name + "/projects/" + project_name + "/" + config_type)
        comp_config = fetch_configuration(zk, "/rigs/" + comp_name + "/projects/" + project_name + "/" + config_type)
        shared_rig_config = fetch_configuration(zk, "/rigs/" + rig_name)
        shared_comp_config = fetch_configuration(zk, "/rigs/" + comp_name)
    elif zk.exists("/hardware/" + project_name + "/defaults/" + config_type):
        project_config = fetch_configuration(zk, "/hardware/" + project_name + "/defaults/" + config_type)
        rig_config = fetch_configuration(zk, "/rigs/" + rig_name + "/projects/" + project_name + "/" + config_type)
        comp_config = fetch_configuration(zk, "/rigs/" + comp_name + "/projects/" + project_name + "/" + config_type)
        shared_rig_config = fetch_configuration(zk, "/rigs/" + rig_name)
        shared_comp_config = fetch_configuration(zk, "/rigs/" + comp_name)

    else:
        if config_type != "logging":
            logging.warning("Found no configuration available for " + project_name)
        return mpe_defaults

    rtn_dict = deep_merge(copy.deepcopy(mpe_defaults), project_config)
    rtn_dict = deep_merge(copy.deepcopy(rtn_dict), rig_config)
    rtn_dict = deep_merge(copy.deepcopy(rtn_dict), comp_config)
    shared_dict = deep_merge(copy.deepcopy(shared_rig_config), shared_comp_config)
    if shared_dict:
        rtn_dict["shared"] = shared_dict
    return rtn_dict


def fetch_configuration(server, config_path, required=False):
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
        config = yaml.load(server[config_path], Loader=loader.Loader)
    except (AttributeError, ParserError) as err:
        if required:
            logging.error(config_path + " is not valid YAML: " + err)
            exit(1)
    except KeyError:
        if required:
            logging.error("Could not find " + config_path + ".")
            exit(1)

    return config


def md5_equal(a, b):
    a_s = str(a)
    b_s = str(b)
    return md5(a_s).hexdigest() == md5(b_s).hexdigest()


def cache_remote_config(configuration, config_path):
    """
    Creates a directory and saves the configuration data.  if a configuration exists, it will be renamed with a
    timestamp.
    :param configuration: dictionary to save to dist
    :param config_path: fully qualified path to save configuration.
    :return:
    """
    if not os.path.exists(os.path.dirname(config_path)):
        os.makedirs(os.path.dirname(config_path))
    if os.path.isfile(config_path):
        config = yaml.load(open(config_path), Loader=loader.Loader)
        # if md5_equal(config, configuration):
        if config == configuration:
            return

        timestamp = datetime.datetime.strftime(datetime.datetime.now(), "%y%m%d-%H%M%S")
        backup_file = config_path + "." + timestamp + ".bck"
        logging.info("Copying previous configuration to " + backup_file)
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
                dict_prime[key] = type(value)()
            deep_merge(dict_prime[key], dict_mod[key])
        else:
            dict_prime[key] = value
    return dict_prime
