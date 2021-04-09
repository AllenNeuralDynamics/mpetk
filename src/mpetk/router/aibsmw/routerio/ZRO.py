#!/usr/bin/env python
# -*- coding: latin-1 -*-

import logging
import socket
import sys
import threading
from abc import abstractmethod
from datetime import datetime
from inspect import signature

import yaml
# import zmq.green as zmq
import zmq
from zmq.eventloop import ioloop
from zmq.eventloop.ioloop import PeriodicCallback
from zmq.eventloop.zmqstream import ZMQStream

from .. import aibsmw_messages_pb2 as messages

import platform
import os


class ZROServiceType(type):
    """
    Metaclass for ZRO services that ensures __init__ is defined with a signature containing 'context' and 'client'
    This is the type class for ZROService and isn't intended for API use.
    """

    def __new__(mcs, name, base_classes, dictionary):
        if '__init__' not in dictionary:
            raise TypeError(f'{name} does not implement __init__()')
        init = dictionary['__init__']
        sig = signature(init)
        if 'context' not in sig.parameters or 'client' not in sig.parameters:
            raise TypeError(f'{mcs}.__init__() must define "context" and "client" as parameters')
        return type(name, base_classes, dictionary)


class ZROService(metaclass=ZROServiceType):
    @abstractmethod
    def __init__(self, context, client):
        """
        this must be present in any zroservice to accept the context and client
        :param context: a ZMQ context
        :param client:  the client object to attach the service
        """
        if not context or not client:
            raise ValueError('context and client must be defined.')

    @abstractmethod
    def start(self):
        """
        standard entry function for the service.  this function is executed in a thread seperate from other
        services
        """
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        """
        standard call for zroservices to turn themselves off.  implementation is required.
        """
        raise NotImplementedError

    @property
    def child_services(self):
        return []


def create_platfom_info_packet():
    packet = messages.platform_info()
    packet.start_time = datetime.now().timestamp()

    packet.header.host = socket.gethostname()
    packet.header.process = sys.argv[0]
    packet.header.timestamp = datetime.now().timestamp()
    packet.header.message_id = packet.DESCRIPTOR.name

    packet.python.build_number = platform.python_build()[0]
    packet.python.build_date = platform.python_build()[1]
    packet.python.compiler = platform.python_compiler()
    packet.python.branch = platform.python_branch()
    packet.python.implementation = platform.python_implementation()
    packet.python.revision = platform.python_revision()
    packet.python.version = platform.python_version()
    packet.python.exec_prefix = sys.exec_prefix
    packet.python.is_conda = os.path.exists(f'sys.exec_prefix/conda-meta')

    packet.host.machine = platform.machine()
    packet.host.node = platform.node()
    packet.host.platform = platform.platform()
    packet.host.processor = platform.processor()
    packet.host.release = platform.release()
    packet.host.system = platform.system()
    packet.host.version = platform.version()
    packet.host.sys_platform = sys.platform
    packet.host.byteorder = sys.byteorder

    return packet


class PlatformInfo(ZROService):

    def __init__(self, context, client, service_host=('*', 6006), io_loop=None):
        """
        Service to distribute platform information that an object is residing on.
        :param context: ZMQ Context provided by ZROHost
        :param client: target object
        :param service_host: (host, port) to serve ('*', 6005)
        :param io_loop: IOLoop provided by ZROHost
        """
        super().__init__(context, client)
        self.io_loop = io_loop
        self._context = context
        self._service_host = service_host
        self._client = client
        self._socket = self._context.socket(zmq.REP)
        self._stream = ZMQStream(self._socket)
        self._socket.setsockopt(zmq.RCVTIMEO, 0)
        self._socket.bind(f'tcp://{self._service_host[0]}:{self._service_host[1]}')

        self.packet = create_platfom_info_packet()

    def start(self):
        poller = zmq.Poller()
        poller.register(self._socket, zmq.POLLIN)
        while True:
            polled = dict(poller.poll(100))
            if self._socket in polled and polled[self._socket] == zmq.POLLIN:
                packet = self._socket.recv()
                self._socket.send(self.packet)

    def stop(self):
        """

        :return:
        """


class Heartbeat(ZROService):
    """
    ZROService that sends a heartbeat message on an interval (default = 1 second)
    """

    def __init__(self, context, client, interval=1000, router_host=('127.0.0.1', 3860), io_loop=None, message=None):
        """
        Heartbeat service that can be attached to a ZROHost
        :param context: ZMQContext provided by ZROHost
        :param client: Target object
        :param interval: time in ms (default = 1000)
        :param router_host: (host, port) of router service
        :param io_loop: io_loop provided by ZROHost
        """
        super().__init__(context, client)
        self.io_loop = io_loop
        self.interval = interval
        self.router_host = router_host
        self.context = context
        self.client = client

        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.connect(f'tcp://{router_host[0]}:{router_host[1]}')
        logging.info(f'publishing to: tcp://{router_host[0]}:{router_host[1]}')
        self.heartbeat_message = message or self.create_heartbeat_message()
        self.callback_timer = PeriodicCallback(self.send_heartbeat, self.interval, io_loop=self.io_loop)

    def create_heartbeat_message(self):
        """
        Defines the values of the remote_device_heartbeat message.
        :return:  a remote_device_heartbeat object
        """
        heartbeat_message = messages.generic_heartbeat()
        heartbeat_message.header.host = socket.getfqdn()
        heartbeat_message.header.timestamp = datetime.now().timestamp()
        heartbeat_message.header.message_id = heartbeat_message.DESCRIPTOR.name
        heartbeat_message.header.process = sys.argv[0]

        return heartbeat_message

    def send_heartbeat(self):
        """
        Called on an self.interval to generate a heartbeat message and publish it.
        """
        self.heartbeat_message.header.timestamp = datetime.now().timestamp()
        message = self.heartbeat_message.header.message_id.encode() + b' ' + self.heartbeat_message.SerializeToString()
        self.publisher.send(message)

    def start(self):
        """
        Standard entry point for ZROHost Services.  Called in a separate thread.
        :return:
        """
        self.stop()
        logging.info(f'Starting heartbeat at interval {self.interval}')
        self.callback_timer.start()
        self.io_loop.start()

    def stop(self):
        """
        Standard exit point for ZROHost Services
        """
        if self.callback_timer.is_running():
            logging.info('Heartbeat Stopped')
            self.callback_timer.stop()


class RemoteObjectService(ZROService):
    def __init__(self, context, client, service_host=('*', 6005), router_host=('127.0.0.1', 3860), io_loop=None,
                 heartbeat=True):
        """
        Service that acts as a local object.
        :param context: ZMQ Context provided by ZROHost
        :param client: target object
        :param service_host: (host, port) to serve ('*', 6005)
        :param router_host: (host, port) of router ('127.0.0.1, 6000)
        :param io_loop: IOLoop provided by ZROHost
        """
        super().__init__(context, client)
        self._io_loop = io_loop
        print('service host = ', service_host)
        self._context = context
        self._service_host = service_host
        self._router_host = router_host
        self._client = client
        self._socket = self._context.socket(zmq.REP)
        self._stream = ZMQStream(self._socket)
        self._socket.setsockopt(zmq.RCVTIMEO, 0)
        self._socket.bind(f'tcp://{self._service_host[0]}:{self._service_host[1]}')
        self._platform_packet = create_platfom_info_packet()
        self._heartbeat = self._create_heartbeat() if heartbeat else None

    @property
    def child_services(self):
        return [self._heartbeat] if self._heartbeat else []

    def _create_heartbeat(self):
        """

        :return:
        """
        message = messages.remote_device_heartbeat()
        message.header.host = socket.gethostname()
        message.header.process = sys.argv[0]
        message.header.message_id = message.DESCRIPTOR.name
        message.device_name = self._client.__class__.__name__
        message.ip_address = socket.gethostbyname(socket.gethostname())
        message.port = self._router_host[1]
        message.start_time = datetime.now().timestamp()
        return Heartbeat(self._context, self._client, message=message, io_loop=self._io_loop)

    def _handle_request(self, request):
        """
        handler to initiate processing of the command
        :param request: remote_servie_request object
        """
        try:
            message = self._parse_message(request)
        except Exception as err:
            logging.info(f'error parsing message {err}')
            return
        self._process_command(message)

    @staticmethod
    def _parse_message(request):
        """
        parses a remove_service_request
        :param request: serialized remote_service_request object
        :return: a remote_service_object
        """
        message = messages.remote_service_request()
        message.ParseFromString(request)
        return message

    def _process_command(self, command):
        """
        The remote command to execute on the target object.  Differentiates command types
        like GET, SET and CALLABLE and executes the appropriate calls.  The command results are stored
        in the object passed to _reply
        :param command: remote_service_request object
        """

        # TODO check hasattr(self, platform_info)
        if command.command_type == command.CMD_PLATFORM_INFO:
            self._platform_packet.header.timestamp = datetime.now().timestamp()
            self._socket.send(self._platform_packet.SerializeToString())
            return
        if not hasattr(self._client, command.target):
            self._reply('No attribute on client', failed=True)
            # print(dir(self._client))
            return

        args = yaml.load(command.args)
        if not args:
            args = ''
        kwargs = yaml.load(command.kwargs)
        if not kwargs:
            kwargs = {}
        result = None

        try:
            if command.command_type == command.CMD_RUN:
                # TODO: special case handling of close and set_reply_ip
                result = getattr(self._client, command.target)(*args, **kwargs)
            elif command.command_type == command.CMD_SET:
                setattr(self._client, command.target, args)
            elif command.command_type == command.CMD_GET:
                result = getattr(self._client, command.target)
            elif command.command_type == command.CMD_CALLABLE:
                result = callable(getattr(self._client, command.target))
        except Exception as err:
            self._reply(f'error in command: {err}', failed=True)

        self._reply(result)

    def _reply(self, result, failed=False):
        """
        Contains the reply message corresponding to a particular command.
        :param result: string
        :param failed: True / False for success status
        """
        try:
            reply = messages.remote_service_reply(reply=yaml.dump(result))
        except TypeError:
            logging.exception('cant reply?')
            print(result)
            return

        message_id = reply.DESCRIPTOR.name
        reply.header.host = socket.gethostname()
        reply.header.process = sys.argv[0]
        reply.header.timestamp = datetime.now().timestamp()
        reply.header.message_id = message_id
        reply.call_result = reply.RESULT_PROCESSED
        self._socket.send(reply.SerializeToString())

    def start(self):
        """
        Standard entry point for ZMQService

        """
        poller = zmq.Poller()
        poller.register(self._socket, zmq.POLLIN)
        while True:
            polled = dict(poller.poll(100))
            if self._socket in polled and polled[self._socket] == zmq.POLLIN:
                packet = self._socket.recv()
                self._handle_request(packet)

    def stop(self):
        """
        Standard Exit point for ZMQService
        :return:
        """
        pass


class ZROHost(object):
    """
    ZROHost Wraps a target object and applies provides network services (ZROService Objects) that reference the target.
    """

    def __init__(self, target, io_loop=None, context=None):
        """
        Instantiate a ZROHost wrapper
        :param target: The object ZROService objects will refer to.
        :param io_loop: If none, ZMQs IOLoop will be used.
        """
        self._context = context or zmq.Context()
        self._io_loop = io_loop or ioloop.IOLoop()
        self._target = target
        self.services = []

    def add_service(self, service, *args, **kwargs):
        """
        Appends a ZROService to the host.
        :param service: ZROService like Heartbeat or RemoteServiceObject
        :param args: any arguments to pass to the service
        :param kwargs: keyword arguments to pass to the service
        """
        new_service = service(self._context, self._target, io_loop=self._io_loop, *args, **kwargs)
        self.services.append(new_service)
        for child_service in new_service.child_services:
            self.services.append(child_service)

    def start(self):
        """
        Spawns each service added by add_service in a thread as a Daemon.
        Each service is then started via a call to start() and joined.
        """
        threads = []
        for service in self.services:
            t = threading.Thread(target=service.start)
            t.setDaemon(True)
            threads.append(t)
            t.start()

        [t.join() for t in threads]

    def stop(self):
        """
        Halts services by calling the services stop() method.
        """
        for service in self.services:
            service.stop()


class ZROProxy(object):
    """
    Service used by client code to attach to the RemoteObjectService
    """

    def __init__(self, host=('127.0.0.1', '6001'), timeout=1.0):
        """
        Create connection to a remote object service
        :param host: (host, port) to connec to.  ('127.0.0.1', 6005)
        :param timeout: How long to wait on a request.  10 seconds
        """
        self.__context = zmq.Context()
        self.__timeout = timeout * 1000
        self.__host = host
        self.__socket = None
        self.setup_socket()
        self.__to_call = None

    def setup_socket(self):
        """
        Called to create a fresh REQ socket.  It will get recreated in the event that a remote object
        times out and doesn't send a RESP
        """
        self.__socket = self.__context.socket(zmq.REQ)
        self.__socket.setsockopt(zmq.LINGER, 0)
        self.__socket.setsockopt(zmq.SNDTIMEO, int(self.__timeout))
        self.__socket.setsockopt(zmq.RCVTIMEO, int(self.__timeout))
        self.__socket.connect(f'tcp://{self.__host[0]}:{self.__host[1]}')

    def __setattr__(self, name, value):
        """
        Calls super().__setattr__ for mangled names and remote_set for everything else.
        :param name:  property to set
        :param value: value to set
        """

        if name.startswith('_ZROProxy__'):
            super().__setattr__(name, value)
        else:
            self.remote_set(name, value)

    def __getattr__(self, name):
        """
        overrides __getattr__ to build a remote request.  It attempts to detect if name is callable and
        configures the command message accordingly.
        :param name: name of method or property on remote object
        :return: either the object callable or value of the property
        """
        if name == 'platform_info':
            return self.remote_get(name)

        self.__to_call = name
        request = messages.remote_service_request()
        request.target = name
        request.command_type = request.CMD_CALLABLE
        is_callable = self.send(request)
        if is_callable is None:
            return None
        return self.remote_call if is_callable else self.remote_get(name)

    def __dir__(self):
        """
        Override of __dir__ to provide the __dir__ of the remote object
        :return:
        """
        return messages.remote_service_request(target='__dir__',
                                               command_type=messages.remote_service_request.CMD_RUN)

    def remote_call(self, *args, **kwargs):
        """
        The function callable returned in getattr to refer to the remote object
        :param args:  method arguments on remote callable
        :param kwargs: method keyword arguments on remote callable
        :return:
        """
        request = messages.remote_service_request(target=self.__to_call,
                                                  command_type=messages.remote_service_request.CMD_RUN,
                                                  args=yaml.safe_dump(args),
                                                  kwargs=yaml.safe_dump(kwargs))
        response = self.send(request)
        return response

    def remote_get(self, name):
        """
        Valued returned from getattr(name) on the remote object
        :param name: property to get
        :return:
        """

        request = messages.remote_service_request()
        request.target = self.__to_call
        if name == 'platform_info':
            request.command_type = request.CMD_PLATFORM_INFO
            return self.send(request, message_type=messages.platform_info)
        else:
            request.command_type = request.CMD_GET
            return self.send(request)

    def remote_set(self, name, value):
        """
        performs a setattr(name, value) on remote object
        :param name: attribute to set
        :param value: value to set
        :return:
        """
        request = messages.remote_service_request()
        request.target = name
        request.command_type = request.CMD_SET
        request.args = yaml.safe_dump(value)
        self.send(request)

    def __del__(self):
        """
        overrides __del__ to close the socket rather than delete the proxy object.
        :return:
        """
        self.__socket.close()

    def send(self, request, message_type=messages.remote_service_reply):
        """
        Sends a command request to the remote object.
        :param request:  remote_service_request()
        :return: the reply message
        """
        request.header.host = socket.gethostname()
        request.header.process = sys.argv[0]
        request.header.timestamp = datetime.now().timestamp()
        request.header.message_id = request.DESCRIPTOR.name
        self.__socket.send(request.SerializeToString())
        try:
            reply = self.receive(message_type=message_type)
            return reply
        except zmq.error.Again:
            logging.warning(f'Error communicating with remote service at {self.__host[0]}:{self.__host[1]}')

    def receive(self, message_type=messages.remote_service_request):
        """
        Receives a message from the remote object in response to a particular command.
        :return: value of object returned from the executed command
        """

        try:
            packet = self.__socket.recv()
        except zmq.error.Again:
            self.setup_socket()
            raise
        if message_type == messages.platform_info:
            reply = messages.platform_info()
            reply.ParseFromString(packet)
            return reply
        else:
            reply = messages.remote_service_reply()
            reply.ParseFromString(packet)
            return yaml.load(reply.reply)
