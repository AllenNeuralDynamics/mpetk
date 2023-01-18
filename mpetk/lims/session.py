# -*- coding: utf-8 -*-
import datetime
import json
import logging
import os
import platform
import re
import subprocess

import requests
import yaml
import zmq

from . import exceptions
from .. import mpeconfig


def move_file(source, destination, remove_source=False):
    """
    Copies files via the system api for windows (robocopy) and linux (cp)
    :param source: A file or directory
    :param destination: A file or directory
    :param remove_source: whether or not to delete the original files
    """
    if not os.path.exists(source):
        logging.warning(f"Source location does not exist: {source}")
        return

    if "windows" in platform.platform().lower():
        if os.path.isdir(source):
            subprocess.run(["robocopy", "/E", source, destination])
        elif os.path.isfile(source):
            source_filename = os.path.basename(source)
            source_path = os.path.dirname(source)
            dest_filename = os.path.basename(destination)
            dest_path = os.path.dirname(destination)
            try:
                os.makedirs(dest_path, exist_ok=True)
                subprocess.run(["robocopy", source_path, dest_path, source_filename])
                if dest_filename:
                    os.rename(f"{dest_path}/{source_filename}", f"{dest_path}/{dest_filename}")
            except OSError as e:
                logging.warning(f"Could not copy {source} to {destination}: {e}")
                return
        else:
            logging.error("Can not copy {source}: unexpected filetype")

    else:  # linux / mac
        subprocess.run(["cp -r", source, destination])

    if remove_source:
        try:
            os.remove(source)
        except OSError as e:
            logging.warning(f"Could not remove {source}: {e}")


class Session(object):
    def __init__(self, session_type, project_name, **kwargs):
        """
        Creates a session object for interacting with LIMS
        :param session_type: a session type as defined in the limstk_Config file.  Example: 'ophys' or 'multipatch'
        :param config_file: name of the src config file to load
        :param override_local: if True, copy the remote configuration over the local configuration
        :param kwargs: a list of arguments to be passed into the trigger file for this session
        """
        self.config = mpeconfig.source_configuration("limstk", send_start_log=False, fetch_logging_config=False)
        self.project_config = mpeconfig.source_configuration(project_name, send_start_log=False,
                                                             fetch_logging_config=False)
        self.config = {**self.config, **self.project_config}
        self.session_type = session_type
        self.session = self.config[session_type]
        self.lims_variables = kwargs
        self.trigger_data = {}
        self.path_data = {}
        self.build_trigger_file()
        self.manifest = []
        self.manifest_filename = None
        self.log_comment = None
        self.overwrite_destination = False

    def build_trigger_file(self):
        """
        Constructs a dictionary for the trigger file by doing the following steps:

        Looks up the URL query data for the current session type and substiitutes the URLs
        key values into the URL string.  The returned data is then scanned for expected return
        keys and stored in the trigger_data variable.

        Location data, either present in the returned data or the default present in the config
        file is then written to trigger_data.

        Finally, kwargs that are defined in the configuration data are placed in trigger_data.
        """

        if "trigger_requests" in self.session:
            for request_type, request in self.session["trigger_requests"].items():
                try:
                    keys = [self.lims_variables[key] for key in request["keys"]]
                except KeyError:
                    logging.error(f'Session type {self.session_type}, expects the keyword arguments: {request["keys"]}')
                    raise

                url = request["url"].format(*keys)
                logging.info("Making GET request to {}".format(url))
                response = requests.get(url)
                if response.status_code != 200:
                    logging.warning("GET request to {} failed with status {}.".format(url, response.status_code))
                    continue
                data = json.loads(response.text)
                if request["returns"] is not None:
                    for key, mapped_name in request["returns"].items():
                        self.trigger_data[mapped_name] = data[key]

                if "project" in data:
                    if "trigger_dir" in data["project"]:
                        location = data["project"]["trigger_dir"].replace("trigger", "")
                        if not re.match("^//", location):
                            location = re.sub("^/", "//", location)
                        location = os.path.normpath(location)
                        self.path_data["location"] = location
                        self.path_data["trigger_dir"] = os.path.join(location, "trigger")

        if "location" not in self.path_data:
            logging.info("LIMS did not return location data; using default values")
            self.path_data["location"] = self.config["default_paths"]["incoming"]
            self.path_data["trigger_dir"] = self.config["default_paths"]["trigger"]

        if "local" in self.session:
            for key, mapped_name in self.session["local"].items():
                self.trigger_data[mapped_name] = self.lims_variables[key]

    @property
    def online(self):
        """
        Tests the LIMS base url to see if it's available.

        :return: bool [True if online]
        """
        return self._online()

    def _online(self):
        """
        Tests the LIMS base url to see if it's available.
        :raises LIMSUnavailableError: if lims_url can't be resolved
        :return: bool [True if online]
        """
        try:
            logging.info("Connecting to {}".format(self.config["lims_url"]))
            request_code = requests.get(self.config["urls"]["base_url"]).status_code
            if request_code == 200:
                return True
        except Exception as error:
            logging.error("LIMS unavailable: {}".format(error))
            raise exceptions.LIMSUnavailableError(error)
        return False

    def request(self, request_type, **kwargs):
        """
        Create GET requests for LIMS URLS and return a dict of the response values.
        These requests do no alter the trigger file.
        :param request_type: a string (defined in limstk_config) that defines this request
        :param kwargs: a set of key words to search for key-values for the get
        :return: a dictionary of the JSON response.
        :raises KeyError: if the request type is invalid or if a key is not in kwargs
        """

        request_vars = kwargs
        request = self.session["requests"][request_type]
        keys = [request_vars[key] for key in request["keys"]]
        url = request["url"].format(*keys)
        url = url.replace(";", "%3B")
        # logging.info('GET request to {}'.format(url))
        response = requests.get(url)
        if response.status_code != 200:
            raise exceptions.LIMSUnavailableError(
                "GET request to {} failed with status {}.".format(url, response.status_code)
            )
        return json.loads(response.text)

    def write_manifest(self, manifest_filename="", trigger_filename="", start_time=None):
        """
        Given a YAML serializable object, write a YAML file and ensure it has:
            * A correct file extension
            * A filename defaulting to datetime.now()
            * Writable acess
        :param manifest_filename: location to write the manifest file
        :param trigger_filename: location (not including path) to write the trigger file)
        """

        if not manifest_filename:
            manifest_filename = datetime.datetime.now().strftime("%y%m%d%H%M%S") + "_lims_manifest.yml"
        self.manifest_filename = f'{self.config["manifest_path"]}/{manifest_filename}'
        if not trigger_filename:
            trigger_filename = datetime.datetime.now().strftime("%y%m%d%H%M%S")

        extension = self.session.get("file_ext", 'tr2')
        if not trigger_filename.endswith(extension):
            trigger_filename = f"{trigger_filename}.{extension}"

        manifest_yml = {
            "trigger_file": trigger_filename,
            "trigger_dir": self.path_data["trigger_dir"],
            "location": self.path_data["location"],
            "root_path": self.config["default_paths"]["root"],
            "trigger_data": self.trigger_data,
            "overwrite_destination": self.overwrite_destination,
            "files": [],
        }
        if self.log_comment:
            manifest_yml['log_comment'] = self.log_comment

        if start_time:
            manifest_yml['start_time'] = start_time

        for src, dst, rm in self.manifest:
            manifest_yml["files"].append(dict(source=src, destination=dst, remove_source=rm))
        try:
            os.makedirs(self.config["manifest_path"], exist_ok=True)
            os.makedirs(self.config["manifest_error_path"], exist_ok=True)
            os.makedirs(self.config["manifest_complete_path"], exist_ok=True)
            os.makedirs(self.config["manifest_working_path"], exist_ok=True)

            with open(self.manifest_filename, "w") as f:
                f.write(str(yaml.dump(manifest_yml, default_flow_style=False)))

            manifest_id = os.path.basename(manifest_filename).replace("_lims", "").replace("_manifest.yml", "")
            logging.info(f"Action, Wrote Manifest, ManifestID, {manifest_id}", extra={"weblog": True})

        except Exception as error:
            logging.error("Error writing manifest:".format(error))
            raise

    def add_to_manifest(self, filename, dst_filename="", remove_source=True):
        """
        Adds a filename to the session manifest if the filename does not exist
        :param filename: a full path/filename string
        :param dst_filename: destination file to copy to (without path)
        """
        if len(dst_filename) == 0:
            dst_filename = os.path.basename(filename)
        destination = os.path.join(self.path_data["location"], dst_filename)
        self.manifest.append((filename, destination, remove_source))

    # TODO:  This isn't coherent with how lims_scheduler_d processes time stamps.  Needs to be looked at more carefully.
    def schedule_manifest(self, manifest_file=None, trigger_file=None, date_time=None):
        """
        Write the manifest file and schedule the transfer
        :param date_time:
        :param trigger_file: filename for the trigger file (defaults to a timestamp)
        :param manifest_file: filename for the manifest file (defaults to a timestamp)
        """
        self.write_manifest(trigger_filename=trigger_file, manifest_filename=manifest_file)
        job = dict(start_time=str(date_time or datetime.datetime.now()), manifest_file=self.manifest_filename)
        logging.info(f'Scheduling {job["manifest_file"]} for {job["start_time"]}')
        sender = zmq.Context().socket(zmq.PUSH)
        sender.connect('{self.config["connection_string"]}')
        sender.send_string(json.dumps(job))

    def commit_manifest(self, trigger_file=None):
        """
        Similar to schedule manifest but non-scheduled and immediate.
        :param trigger_file: Name of the trigger file to write
        """
        location = self.path_data["location"]
        try:
            if not os.path.exists(location):
                logging.info("Creating directory: {}.format(location)")
                if not os.path.isdir(location):
                    os.makedirs(location)

        except Exception as error:
            # py3 uses permissionerror but py2 uses oserror with some errono codes.
            # I may circle back and do something more appropriate here.
            logging.error("Error creating path: {}".format(error))
            raise

        if not trigger_file:
            trigger_file = datetime.datetime.now().strftime("%y%m%d%H%M%S")

        extension = self.session.get("file_ext", 'tr2')
        if not trigger_file.endswith(extension):
            trigger_file = ".".join((trigger_file, extension))

        missing_files = []
        for source, destination, remove_source in self.manifest:
            if not os.path.exists(source):
                missing_files.append(source)
                continue
            logging.info("Copying {} to {}".format(source, destination))
            move_file(source, destination, remove_source)

        if missing_files:
            logging.warning("Could not find the following files listed in the manifest: {}".format(missing_files))

        for path in (self.config["default_paths"]["root"], self.path_data["trigger_dir"]):
            if not os.path.isdir(path):
                os.makedirs(path)

        logging.info("Writing trigger file ({}) to {}".format(trigger_file, self.path_data["trigger_dir"]))
        with open(self.path_data["trigger_dir"] + "/" + trigger_file, "w") as f:
            yaml_text = str(yaml.safe_dump(self.trigger_data, default_flow_style=False))
            f.write(yaml_text.replace("'''", "'"))  # fixes an obtuse behavior of the yaml spec
