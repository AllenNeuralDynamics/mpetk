# -*- coding: utf-8 -*-
"""
proxy.py

@author: derricw

Proxy device and manager for ZRO devices.

`DeviceProxy` is a remote object proxy designed to interact with objects
extending `BasePubRepDevice` (from device.py). 

`DeviceManager` is a remote object manager that uses a json config file to
create and manage remote objects.  It can ping devices, get uptime, platform
information, and also return `RemoteObject` objects by name, so that you don't
have to create them by ip address.

"""
import time
import datetime

import zmq

from .config import ConfigFile
from .error import ZroError
from .misc import get_address


class DeviceManager(object):
    """
    Manages devices. Requires a json config file.

    Args:
        config (str, dict, ConfigFile): path to json config file.

    Example:
        >>> dm = DeviceManager("config.json")
        >>> stage = dm.get_proxy("stage")
        >>> stage.set_pos(x=500, y=100)

        >>> dm.ping_device("stage")
        0.0070123

        >>> dm.device_exists("stage")
        True

    """
    def __init__(self, config):
        if isinstance(config, str):
            self.config = ConfigFile(config).get_config()
        elif isinstance(config, dict):
            self.config = config
        elif isinstance(config, ConfigFile):
            self.config = config.get_config()
        else:
            raise TypeError("Config file should be file path or dictionary.")

        self.devices = self.config['devices']

    def get_device_info(self, device_name):
        """
        Returns device info by name.

        Args:
            device_name (str): name of device in configuration.

        Returns:
            dict: dictionary of device information.

        """
        for dev in self.devices:
            if dev['name'].lower() == device_name.lower():
                return dev
        raise KeyError("Device '%s' not found in config." % device_name)

    def get_devices(self, ip="*", name=""):
        """
        Returns the device list.  Optionally takes an ip or name and only
            returns devices matching that ip or name.

        Args:
            ip (Optional[str]): ip to filter by.  Defaults to "*"
            name (Optional[str]): name to filter by.  Defaults to ""

        Returns:
            list: device list matching any filters.
        """
        devs = self.devices
        if ip != "*":
            devs = [d for d in devs if ip in d['ip']] # filter ips
        if name:
            devs = [d for d in devs if name in d['name']] # filter names
        return devs

    def get_device_names(self):
        """
        Returns a list of all device names.

        Returns:
            list: list of device names.
        """
        devs = self.get_devices()
        return [d['name'] for d in devs]

    def device_exists(self, device_name):
        """
        Checks whether a device exists in the configuration.

        Args:
            device_name (str): name of device to look for.

        Returns:
            bool: True if device is in configuration.
        """
        for dev in self.devices:
            if dev['name'].lower() == device_name.lower():
                return True
        return False

    def device_active(self, device_name, timeout=3.0):
        """
        Returns True if a device responds within the timeout.  Raises exception
            if device doesn't exist.

        Args:
            device_name (str): name of device to poll
            timeout (Optional[float]): timeout for device in seconds. Defaults
                to 3.0.

        Returns:
            bool: True if device responds within timeout.

        Raises:
            KeyError: When device isn't in configuration.
        """
        if self.device_exists(device_name):
            prox = self.get_proxy(device_name, timeout=timeout)
            try:
                p = prox.rep_port
                return True
            except zmq.ZMQError:
                return False
        else:
            raise KeyError("Device %s not in config." % device_name)

    def ping_device(self, device_name, timeout=3.0, attempts=3):
        """
        Returns time in seconds for device to respond to a single request.

        Args:
            device_name (str): name of device to ping
            timeout (Optional[float]): timeout for device in seconds. Defaults
                to 10.0.

        Returns:
            float: Average response time in seconds if device responds.  -1.0
                otherwise.

        Raises:
            KeyError: Device not in configuration.

        """
        if self.device_exists(device_name):
            prox = self.get_proxy(device_name, timeout=timeout)
            failures = 0
            times = []
            for i in range(attempts):
                try:
                    t = time.clock()
                    p = prox.rep_port
                    times.append(time.clock()-t)
                except zmq.ZMQError:
                    failures += 1
            if failures == attempts:
                return -1.0
            else:
                return sum(times)/len(times)
        else:
            raise KeyError("Device %s not in config." % device_name)

    def ping_all_devices(self, timeout=3.0, attempts=3):
        """
        Pings all devices.

        Args:
            timeout (float): timeout for pings in seconds
            attempts (int): # of attempts for each device

        Returns:
            dict: {device_name: ping, ...}

        """
        pings = {}
        for dev_name in self.get_device_names():
            pings[dev_name] = self.ping_device(dev_name, timeout, attempts)
        return pings

    def get_uptime(self, device_name, timeout=3.0, convert_to_datetime=True):
        """
        Gets the uptime of the device in seconds.

        Args:
            device_name (str): name of device to request uptime from.
            timeout (Optional[float]): timeout for device in seconds. Defaults
                to 10.0.
            convert_to_datetime (Optional[bool]): whether to convert output to
                str datetime format.

        Returns:
            uptime: either float or str

        Raises:
            KeyError: Device not in configuration.

        """
        if self.device_exists(device_name):
            prox = self.get_proxy(device_name, timeout=timeout)
            if convert_to_datetime:
                return datetime.timedelta(seconds=prox.get_uptime())
            else:
                return prox.uptime
        else:
            raise KeyError("Device %s not in config." % device_name)

    def get_platform_info(self, device_name, timeout=3.0):
        """
        Gets the platform info of the device.

        Args:
            device_name (str): name of device to get platform info
            timeout (Optional[float]): timeout for device in seconds. Defaults
                to 10.0.

        Returns:
            dict: dictionary of platform information.

        Raises:
            KeyError: Device not in configuration.

        """
        if self.device_exists(device_name):
            prox = self.get_proxy(device_name, timeout=timeout)
            return prox.platform_info
        else:
            raise KeyError("Device %s not in config." % device_name)


    def get_proxy(self, device_name, timeout=10.0):
        """
        Returns a DeviceProxy object by device name, with the specified
            timeout.

        Args:
            device_name (str): configuration name of device
            timeout (Optional[float]): timeout for proxy in secounds.  Defaults
                to 10.0.

        Returns:
            DeviceProxy: remote object proxy
        """
        info = self.get_device_info(device_name)
        return DeviceProxy(info['ip'], info['rep_port'], timeout)


class DeviceProxy(object):
    """
    Proxy object for a BasePubRepDevice.

    args:
        ip (Optional[str]): IP/DNS address of actual device. Defaults to
            "localhost".
        port (Optional[int]): REP port for actual device, if it isn't include
            in IP.
        timeout (Optional[float]): Timeout in seconds for all commands.
            Defaults to 10.
        serialization (Optional[str]): Serialization method.  "pickle" (default)
            or "json".

    Example:
        >>> dev = DeviceProxy("localhost:5556")
        >>> dev.call_method_on_device(some_argument)
        >>> dev.attr_on_device = 5

    """
    _context = zmq.Context()
    _context.setsockopt(zmq.LINGER, 1)
    
    def __init__(self,
                 ip="localhost",
                 port=None,
                 timeout=10.0,
                 serialization='pickle',
                 ):

        super(DeviceProxy, self).__init__()
        self.__dict__['ip'] = ip
        self.__dict__['rep_port'] = port
        self.__dict__['timeout'] = timeout
        self.__dict__['serialization'] = serialization.lower()

        self._setup_socket()
        #self._setup_getset()

    def __setattr__(self, name, value):
        """
        Overwrite __setattr__ so that attributes are set on target object
            instead of this object.
        """
        packet = {"command": "set", "args": (name, value)}
        self._send_packet(packet)
        response = self.__dict__['recv']()
        if response == "0":
            return None
        else:
            raise ZroError(message=str(response))

    def __getattr__(self, name):
        """
        Overwrite __getattr__ so that attributes are grabbed from target object
            instead of this object.
        """
        packet = {"command": "get", "args": (name,)}
        self._send_packet(packet)
        response = self.__dict__['recv']()
        if isinstance(response, ZroError):
            raise ZroError(message=str(response))
        elif response in ('callable', "__callable__"):
            self.__dict__['to_call'] = name  # HOLD ON TO YOUR BUTTS
            return self._call
        else:
            return response

    def __dir__(self):
        """
        Overwrite __dir__ so that attributes and methods come from target
            object.
        """
        self.__dict__['to_call'] = "get_attribute_list"
        attrs = self._call()
        self.__dict__['to_call'] = "get_command_list"
        methods = self._call()
        return attrs + methods

    def _send_packet(self, packet):
        """
        Sends a packet.  Attempts to reconnect once if there is a failure.

        #TODO: Make packet a class.
        """
        try:
            self.__dict__['send'](packet)
        except zmq.ZMQError:
            self.__dict__['req_socket'].close()
            self._setup_socket()
            self.__dict__['send'](packet)

    def _setup_socket(self):
        """
        Sets up the request socket.
        """
        ip = self.__dict__['ip']
        rep_port = self.__dict__['rep_port']
        addr_str = get_address(ip, rep_port)
        timeout = self.__dict__['timeout']
        self.__dict__['req_socket'] = self._context.socket(zmq.REQ)
        self.__dict__['req_socket'].setsockopt(zmq.SNDTIMEO, int(timeout*1000))
        self.__dict__['req_socket'].setsockopt(zmq.RCVTIMEO, int(timeout*1000))
        self.__dict__['req_socket'].connect(addr_str)

        if self.__dict__['serialization'] in ["pickle", "pkl", "p"]:
            self.__dict__['send'] = self.__dict__['req_socket'].send_pyobj
            self.__dict__['recv'] = self.__dict__['req_socket'].recv_pyobj
        elif self.__dict__['serialization'] in ["json", "j"]:
            self.__dict__['send'] = self.__dict__['req_socket'].send_json
            self.__dict__['recv'] = self.__dict__['req_socket'].recv_json
        else:
            raise ValueError("Incorrect serialization type. Try 'pickle' or 'json'.")

    def _call(self, *args, **kwargs):
        """
        Used for calling arbitrary methods in the device.
        """
        packet = {"command": "run", "callable": self.to_call, "args": args,
                  "kwargs": kwargs}
        self.__dict__['send'](packet)
        response = self.__dict__['recv']()
        if isinstance(response, ZroError):
            raise ZroError(message=str(response))
        return response

    def __del__(self):
        """
        Close the socket on cleanup.
        """
        self.__dict__['req_socket'].close()


    @classmethod
    def as_gui(cls, 
               ip="localhost",
               port=None,
               timeout=10.0,
               serialization='pickle',
               command_list=None,
               attribute_list=None,
               ):
        from PyQt4 import QtGui
        app = QtGui.QApplication([])
        qwidget = DeviceProxy.as_qwidget(ip=ip,
                                         port=port,
                                         timeout=timeout,
                                         serialization=serialization,
                                         command_list=command_list,
                                         attribute_list=attribute_list,)
        qwidget.setWindowTitle(ip)
        qwidget.show()
        app.exec_()

    @classmethod
    def as_qwidget(cls,
                   ip="localhost",
                   port=None,
                   timeout=10.0,
                   serialization="pickle",
                   command_list=None,
                   attribute_list=None,
                   ):
        from .gui import ProxyWidget
        prox = DeviceProxy(ip, port, timeout=timeout, serialization=serialization)
        return ProxyWidget(proxy=prox,
                           command_list=command_list,
                           attribute_list=attribute_list,)


Proxy = DeviceProxy

if __name__ == '__main__':
    pass
