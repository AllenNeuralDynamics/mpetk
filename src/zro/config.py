"""

config.py

@author: derricw

Config file reading/writing module.

"""

import json
import os


EMPTY_CONFIG = {
    "devices": [],
    "system": {},
    }


class ConfigFile(object):
    """
    Configuration file that stores IPs and Ports for named devices, as well as
        arbitrary system variables.

    Args:
        path (str): path to config file to open or create.

    Example:
        >>> cf = ConfigFile("my_config.json")
        >>> cf.add_device("stage", "192.168.0.5", rep_port=5555)
        >>> cf.save()

    """
    def __init__(self, path):
        super(ConfigFile, self).__init__()

        ## TODO: support yaml, etc?
        self.config = self.load_json(path)
        self.save = self.save_json

    def load_json(self, json_path):
        """
        Loads a config file at a specified path.  If one doesn't exist, it
            creates a new one.

        Args:
            json_path (str): path to config file.

        Returns:
            dict: configuration information for system.

        """
        self.path = json_path
        #basename = os.path.basename(json_path)
        dirname = os.path.dirname(json_path)

        # if file doesn't exist we make a new one
        if dirname:
            if not os.path.isdir(dirname):
                os.makedirs(dirname)
        if not os.path.isfile(json_path):
            self.save_json(json_path, EMPTY_CONFIG)

        with open(json_path, "r") as f:
            config = json.load(f)

        return config

    def save_json(self, json_path="", config=None):
        """
        Saves a config to a specified path.

        Args:
            json_path (Optional[str]): json path to save to.  If empty, saves to
                last path loaded.
            config (Optional[dict]): config dictionary to save. If empty, saves the current
                configuration.

        """
        if not json_path:
            json_path = self.path

        if json_path[-5:] != ".json":
            json_path = "{}.json".format(json_path)

        dirname = os.path.dirname(json_path)
        if dirname:
            if not os.path.isdir(dirname):
                os.makedirs(dirname)
        with open(json_path, "w") as f:
            if not config:
                config = self.config
            json.dump(config, f, sort_keys=True,
                      indent=4, separators=(",", ": "))

    def add_device(self,
                   name,
                   ip,
                   rep_port,
                   pub_port=None,
                   push_port=None,
                   pull_port=None,):
        """
        Add a device to the configuration.

        Args:
            name (str): name of device to add
            ip (str): ip address of device to add
            rep_port (int): reply port of device to add
            pub_port (Optional[int]): publishing port of device to add
            push_port (Optional[int]): push port of device
            pull_port (Optional[int]): pull port of device

        Raises:
            ValueError: port/ip conflict

        """
        # check for conflicts first
        # TODO: make this not filthy
        # HOLD MY BEER
        for dev in self.config['devices']:
            if name.lower() == dev['name'].lower():
                raise KeyError("Name %s already exists!" % name)
            if ip == dev["ip"]:
                if (pub_port is not None) and (pub_port == dev['pub_port']):
                    raise ValueError("Pub port %s:%s already in use." % (ip,
                                                                     pub_port))
                elif rep_port == dev['rep_port']:
                    raise ValueError("Rep port %s:%s already in use." % (ip,
                                                                     rep_port))
                elif (push_port is not None) and (push_port == dev['push_port']):
                    raise ValueError("Push port %s:%s already in use." % (ip,
                                                                     push_port))
                elif (pull_port is not None) and (pull_port == dev['pull_port']):
                    raise ValueError("Pull port %s:%s already in use." % (ip,
                                                                     pull_port))

        self.config['devices'].append({"ip": ip,
                                       "name": name,
                                       "pub_port": pub_port,
                                       "rep_port": rep_port,
                                       "push_port": push_port,
                                       "pull_port": pull_port,
                                       })

    def remove_device(self, name):
        """
        Remove a device from the configuration.

        Args:
            name (str): name to remove

        Raises:
            KeyError: device doesn't exist

        """
        for i, v in enumerate(self.config['devices']):
            if name.lower() == v['name'].lower():
                self.config['devices'].pop(i)
                return
        raise KeyError("Device named %s not in configuration." % name)

    def set_system_var(self, name, value):
        """
        Add a system variable to the config file.  This is just an arbitrary
            key-value pair that you want to keep in the configuration file.

        Args:
            name (str): name of variable to set
            value (object): value of variable to set

        #TODO: Check if value is json compatible before setting.

        """
        self.config['system'][name] = value

    def get_system_var(self, name):
        """
        Just returns the value of a system variable.

        Args:
            name (str): name of variable.

        """
        return self.config['system'][name]

    def remove_system_var(self, name):
        """
        Remove a key from the system variables.

        Args:
            name (str): name of variable to remove

        Raises:
            KeyError: key doesn't exist

        """
        if name in self.config['system'].keys():
            del self.config['system'][name]
        else:
            raise KeyError("Variable name doesn't exist.")

    def get_devices(self):
        """
        Returns the devices of the current configuration.

        Returns:
            list: list of device information

        """
        return self.config['devices']

    def get_device_names(self):
        """
        Returns the device names.

        Returns:
            list: list of device names
        """
        names = [d['name'] for d in self.config['devices']]
        return names

    def get_system(self):
        """
        Returns the system variables of the current configuration.

        Returns:
            dict: dictionary of system variable keys and values
        """
        return self.config['system']

    def get_config(self):
        """
        Returns the complete configuration as a dictionary.

        Returns:
            dict: complete configuration
        """
        return self.config

if __name__ == '__main__':
    pass