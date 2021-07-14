#!/usr/bin/env python
# -*- coding: latin-1 -*-

from abc import ABC, abstractmethod
import codecs
import getpass
import logging
import os
import socket
import sys
import uuid
from collections import defaultdict
from datetime import datetime
from inspect import signature
from socket import AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST, SO_RCVTIMEO
import zmq
import graphviz
from graphviz import Digraph, ExecutableNotFound
from .exceptions import *
from .. import aibsmw_messages_pb2
#import multiprocessing
import threading
import psutil

class Router(object):
    def __init__(self, host='*', port=None, timeout=100):
        """

        :param publisher_port:
        :param subscriber_port:
        """
        self.log = logging.getLogger(sys.argv[0])
        self.context = zmq.Context()

        user = getpass.getuser().zfill(16)[:16]  # Some user names are long (svc_mfishoperator) UUID wants 16 exactly.
        uuid_key = codecs.encode(user.encode(), 'hex')

        self._router_port = port or uuid.UUID(uuid_key.decode()).int % 8976 + 1024
        self._router = self.context.socket(zmq.ROUTER)
        self._router.identity = b'router'
        self._router.bind(f'tcp://*:{self._router_port}')
        self._router.RCVTIMEO = timeout
        self.log.info(f'router connected to: tcp://{host}:{self._router_port}')

        # self._broadcast_port = self._router_port + 1
        # self._broadcast_socket = socket.socket(AF_INET, SOCK_DGRAM)
        # self._broadcast_socket.bind(('', self._broadcast_port))
        # self._broadcast_socket.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        # self._broadcast_socket.setsockopt(SOL_SOCKET, SO_RCVTIMEO, 100)
        # self.log.info(f'router broadcasting to port  {self._broadcast_port}')

        self.keep_polling = True
        self.remote_devices = {}
        self.registration = defaultdict(list)
        self.header_retention = 100
        self.message_headers = []
        self.clients = set()

        self._routers = set()
        # self.announce_router()

    def announce_router(self):
        message_list = []
        for client, topics in self.registration.items():
            message_list.extend(topics)

        message = aibsmw_messages_pb2.router_alive()
        message_id = message.DESCRIPTOR.name
        message.header.host = socket.gethostname()
        message.header.process = sys.argv[0]
        message.header.timestamp = datetime.now().timestamp()
        message.header.message_id = message_id
        for topic in set(message_list):
            message.append(topic)
        self._broadcast_socket.sendto(message.SerializeToString(), ('<broadcast>', self._broadcast_port))

    def stop(self):
        """


        :return:
        """
        self.keep_polling = False

    def start(self):
        """

        :return:
        """
        self.keep_polling = True
        self._poll()

    def write_to_router(self, router, message):
        """

        :param message:
        :return:
        """
        message_id = message.DESCRIPTOR.name
        message.header.host = socket.gethostname()
        message.header.process = sys.argv[0]
        message.header.timestamp = datetime.now().timestamp()
        message.header.message_id = message_id
        self._router.send_multipart([b'router', message_id.encode(), message.SerializeToString()])

## Should we get rid of this??
    def generate_traffic_report(self):
        return
        registered_clients = []
        for k, v in self.registration.items():
            registered_clients += v
        registered_clients = list(set(registered_clients))
        publishing_clients = list(set(header[0] for header in self.message_headers))
        dot = Digraph(comment=f'{socket.gethostname()} Traffic Report')
        for client in self.clients:
            dot.attr('node', width='3')
            dot.node(str(client), str(client))

        for message in self.message_headers:
            for client in self.registration[message[1]]:
                dot.edge(str(message[0]), str(client), label=message[1].decode())

        gv_file = 'traffic_report.gv'
        dot.render(gv_file, view=False, format='png')

    def _poll(self):
        """

        :return:
        """
        time_since_last_report = datetime.now()

        while self.keep_polling:
            # recv broadcast packets:
            """
            try:
                router_alive = self._broadcast_socket.recv(1024)
                message = aibsmw_messages_pb2.router_alive()
                message.ParseFromString(router_alive)
                if message.header.host != socket.gethostname():
                    self.announce_router()
                    handler = ZMQHandler(aibsmw_messages_pb2, host=message.header.host)
                    self._routers.add(handler)
                    for msg_id in message.registered_messages:
                        handler.register_for_message(msg_id.decode())
            except Exception:
                pass
            """
            try:
                packet = self._router.recv_multipart()
            except zmq.error.Again as e:
                t2 = datetime.now()
                delta = t2 - time_since_last_report
                if delta.seconds > 30:
                    time_since_last_report = t2
                continue
            if packet[1] == b'':
                self.log.info(f'new connection from {packet[0]}')
                self._router.send_multipart(packet)
                continue

            client, message_id, serialized_message = packet
            self.clients.add(client)
            self.log.info(f'{client} -> {message_id}')
            self.message_headers.append((client, message_id))
            if len(self.message_headers) > self.header_retention:
                self.message_headers.pop(0)

            if message_id == b'register_for_message':
                message = aibsmw_messages_pb2.register_for_message()
                message.ParseFromString(serialized_message)
                if client not in self.registration[message_id]:
                    self.registration[message.message_id.encode()].append(client)
                    self.log.info(f'{client} registered for {message.message_id.encode()}')
                for router in self._routers:
                    router.register_for_message(message.message_id)

            if message_id == b'deregister_for_message':
                message = aibsmw_messages_pb2.deregister_for_message()
                message.ParseFromString(serialized_message)
                if client in self.registration[message_id]:
                    self.registration[message_id].remove(client)
                for router in self._routers:
                    router.write([b'router', message_id, serialized_message])

            for cli in self.registration[b'*']:
                if cli != client:
                    packet[0] = cli
                    self._router.send_multipart(packet)
                    self.log.info(f'{cli} <- {message_id}')

            for cli in self.registration[message_id]:
                if cli != client:
                    packet[0] = cli
                    self._router.send_multipart(packet)
                    self.log.info(f'{cli} <- {message_id}')



class IOHandler(ABC):

    @abstractmethod
    def write(self):
        pass

    @abstractmethod
    def receive(self):
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def _poll(self):
        pass


def get_process_name(process):

    if 'python' in process.name() and len(process.cmdline())>1:
        return process.cmdline()[1]
    return process.name()


class ZMQHandler(IOHandler):
    def __init__(self, message_module, host='127.0.0.1', port=None, timeout=100, identity = None):

        super().__init__()
        """

        :param message_module:
        :param host:
        :param publisher_port:
        :param subscriber_port:
        """
        self.log = logging.getLogger(sys.argv[0])
        self.context = zmq.Context()

        user = getpass.getuser().zfill(16)[:16]
        uuid_key = codecs.encode(user.encode(), 'hex')

        self._router_port = port or uuid.UUID(uuid_key.decode()).int % 8976 + 1024
        self._router = self.context.socket(zmq.ROUTER)
        self._router.RCVTIMEO = timeout
        if not identity:
            process_name = get_process_name(psutil.Process(os.getpid()))
            thread_id = threading.current_thread().ident
            self._router.identity = f'{socket.gethostname()}_{process_name}_{thread_id}'.encode()
        else:
            self._router.identity = identity.encode()

        self._router.probe_router = 1
        self._router.connect(f'tcp://{host}:{self._router_port}')
        try:
            self._router.recv_multipart()
        except:
            pass
        self.log.info(f'router connected to: tcp://{host}:{self._router_port}')

        self.keep_polling = True
        self.message_callbacks = {}
        self.messages = [message_module]

    def add_message_bundle(self, bundle):
        self.messages.append(bundle)

    def register_for_message(self, message_id, callback=None):
        """

        :param message_id:
        :param callback:
        :return:
        """
        if callback:
            self.message_callbacks[message_id] = callback

        self.write(aibsmw_messages_pb2.register_for_message(message_id=message_id.encode()))

    def deregister_for_message(self, message_id):
        """

        :param message_id:
        :return:
        """
        if message_id in self.message_callbacks:
            self.message_callbacks.pop(message_id)

        self.log.info(f'deregistered for message {message_id}')

    def _parse_message(self, message_id, packet):
        """

        :param message_id:
        :param packet:
        :return:
        """
        for bundle in self.messages:
            try:
                message = getattr(bundle, message_id)()
                message.ParseFromString(packet)
                return message
            except AttributeError:
                continue
            except Exception as err:
                logging.warning(f'Error decoding message {message_id}: {err}')

        else:
            logging.warning(f'{message_id} is not defined in messages.')

    def write(self, message):
        """

        :param message:
        :return:
        """
        message_id = message.DESCRIPTOR.name
        message.header.host = socket.gethostname()
        message.header.process = sys.argv[0]
        message.header.timestamp = datetime.now().timestamp()
        message.header.message_id = message_id
        self._router.send_multipart([b'router', message_id.encode(), message.SerializeToString()])

    def receive(self):
        """

        :return:
        """
        from pprint import pprint
        try:
            client, message_id, message = self._router.recv_multipart()
        except Exception:
            raise zmq.error.Again

        message_id = message_id.decode()

        if message_id in self.message_callbacks:
            message = self._parse_message(message_id, message)
            self.message_callbacks[message_id](message_id, message, datetime.now(), self)
            return message

        elif b'*' in self.message_callbacks:
            message = self._parse_message(message_id, message)
            self.message_callbacks['*'](message_id, message, datetime.now(), self)
            return message

    def start(self):
        """

        :return:
        """
        self.keep_polling = True
        self._poll()

    def stop(self):
        """

        :return:
        """
        self.keep_polling = False

    def _poll(self):
        """

        :return:
        """
        import errno
        poller = zmq.Poller()
        poller.register(self._router, zmq.POLLIN)
        while self.keep_polling:
            try:
                client, message_id, message = self._router.recv_multipart()
            except Exception as e:
                continue

            message_id = message_id.decode()

            if message_id in self.message_callbacks:
                message = self._parse_message(message_id, message)
                self.message_callbacks[message_id](message_id, message, datetime.now(), self)

            elif '*' in self.message_callbacks:
                message = self._parse_message(message_id, message)
                self.message_callbacks['*'](message_id, message, datetime.now(), self)
