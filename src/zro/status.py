"""
Status monitor device.  Loads a configuration of system and publishes uptime,
    ping, etc.

SUPER OUTDATED

"""

from __future__ import print_function
import logging
import os
import time
import datetime
import socket

import zmq

from device import BasePubRepDevice
from proxy import DeviceProxy
from config import ConfigFile


class SystemStatus(BasePubRepDevice):
    """
    Loads a config file and polls devices to maintain a map of
        connected devices.  Publishes the status on its pub port.
    """

    empty_confg = {
        "devices": [],
        "system": {},
    }

    def __init__(self, ip, pub_port, rep_port, config_json):
        logging.info("Initializing BasePubRepDevice.")
        super(SystemStatus, self).__init__(ip=ip, pub_port=pub_port,
                                           rep_port=rep_port)
        self.config_json = config_json

        self.devices = []
        self.context = zmq.Context()
        self.config = ConfigFile(config_json)
        self._info = {'name':'status',
                      "available": True,
                      "pub_port": pub_port,
                      "rep_port": rep_port,
                      "ip": socket.gethostbyname(socket.gethostname()),
                      "ping": 0.0,
                      "uptime": 0.0,
                      }

        self._setup(self.config)

        self._update_count = 0
        self.print_status = True

        logging.info("Status Device initialized.")

    def _setup(self, config):
        devices = config.get_devices()
        #system = config.get_system()

        for dev in devices:
            self._add_device_port(dev)

    def _add_device_port(self, dev):
        proxy = DeviceConnection(dev)
        self.devices.append(proxy)
        logging.info("Device added: %s" % dev)

    def _publish(self):
        to_publish = self._get_device_status()
        self._info['uptime'] = str(datetime.timedelta(seconds=self.get_uptime()))
        to_publish.insert(0, self._info)
        
        if self.print_status:
            self._show_status(to_publish)
        self._update_count += 1
        time.sleep(1.0)
        return to_publish


    def _get_device_status(self):
        """
        Gets the status of all configured devices.
        """
        responses = []
        for proxy in self.devices:
            data = proxy.ping()
            #print(data)
            responses.append(data)
        status = []
        for i, response in enumerate(responses):
            device_status = self.config.get_devices()[i].copy()
            if response == False:
                device_status['available'] = False
                device_status['ping'] = "*"
                device_status['uptime'] = "0:00:00:00"
                try:
                    #try to reconnect periodically
                    if self._update_count % 10 == 0:
                        self.devices[i].connect()
                except Exception as e:
                    print(e)
            else:
                device_status['available'] = True
                device_status['ping'] = str(response[0])[:5]
                device_status['uptime'] = str(response[1])
            status.append(device_status)
        return status


    def _show_status(self, status):
        form = "{0: ^5}{1: ^15}{2: ^15}{3: ^10}{4: ^10}{5: ^15}{6: ^10}{7: ^20}"
        header = form.format("i","name","ip","rep_port","pub_port","available",
                             "ping","uptime")
        
        #clear the terminal
        #print(chr(python_2) + "[2J")  # linux?
        os.system("cls")

        print(header)
        for i, stat in enumerate(status):
            print(form.format(i, stat['name'], stat['ip'], stat['rep_port'],
                              stat['pub_port'], stat['available'],
                              stat['ping'], stat['uptime']))


class DeviceConnection(object):
    """ A connection to a device. """
    def __init__(self, config):
        super(DeviceConnection, self).__init__()
        self.config = config

        self.ip = config['ip']
        self.rep_port = config['rep_port']

        self.connect()

        self.uptime_sec = 0.0

    def connect(self):
        """
        Create a proxy connection to the device.
        """
        self.proxy = DeviceProxy(self.ip,
                                 self.rep_port,
                                 timeout=2.0)

    def ping(self):
        """
        Pings a device.  Returns False if device doesn't respond.  If it does
            respond, returns time and whether is it publishing.
        """
        t = time.clock()
        try:
            rep_port = self.proxy.rep_port
            return (time.clock()-t, self.uptime())
        except zmq.ZMQError as e:
            return False
        self.ping_counter += 1

    def uptime(self):
        """
        Gets the devices uptime.
        """
        self.uptime_sec = self.proxy.get_uptime()
        return datetime.timedelta(seconds=self.uptime_sec)
        


if __name__ == '__main__':
    
    logging.basicConfig(level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("-c", "--config", type=str, help="The config file.",
                        default="C:/tmp/status.json")

    args = parser.parse_args()

    sd = SystemStatus("*", 5600, 5601, args.config)

    sd.publishing = True

    sd.run_forever()
