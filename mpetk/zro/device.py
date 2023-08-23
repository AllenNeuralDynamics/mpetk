# -*- coding: utf-8 -*-
"""
device.py

@author: derricw

This module contains base classes for the ZRO remote objects.

"""
from collections import OrderedDict
import sys
import logging
import time
import traceback
import datetime
import threading
import pickle
import json
import inspect
import socket

try:
    import zmq
    from zmq.auth.ioloop import IOLoopAuthenticator
    from zmq.eventloop.zmqstream import ZMQStream
    from zmq.eventloop import ioloop
except ImportError:
    raise ImportError("Error importing pyzmq.  Try pip install pyzmq==14.7")

ioloop.install()
ioloop_instance = ioloop.IOLoop.instance()

from .proxy import Proxy
from .error import ZroError
from .misc import get_address, is_valid_ipv4_address


__version__ = "0.5.0.dev2"
class RemoteObject(object):
    """
    Remote object device designed to be extended.  It serializes responses to
        match the request.

    Args:
        ip (Optional[str]): IP address to broadcast on.
        rep_port (Optional[int]): Port to REP on.  Port chosen automatically
            if not supplied.

    Example:

        class MyRemoteObject(RemoteObject):
            def __init__(self, ip, port):
                super(MyRemoteObject, self).__init__(ip, port)
                self.my_attribute = 0

            def my_method(self):
                self.my_attribute += 1

    """
    _context = zmq.Context()

    _command_list = {
        "set": "_set",
        "get": "_get",
        "run": "_run",
    }

    def __init__(self,
                 ip="*",
                 rep_port=None,
                 ):

        self.ip = ip
        self.rep_port = rep_port
        self._authentication = False

        self._rep_sock = None
        self._auth = None
        self._stream = None
        self._update_timer = None
        self._whitelist = []
        self._blacklist = []
        self.set_reply_ip(ip, rep_port)

        self._start_time = time.perf_counter()
        self.start_datetime = datetime.datetime.now()

        # prevents ipython autocomplete from throwing warnings
        self.trait_names = []

        self.full_traceback_on = False
        self._async_results = {}
        self._async_handle_index = 0
        self._async_handle_list = []
        self._async_callbacks = {}
        self._update_interval = 0.0
        self.threaded_async = False

        self._obj_ = self  # object we will be serving.

        self.init()

    def set_reply_ip(self, ip="", port=None):
        """
        Sets the reply socket to the specified IP

        Args:
            ip (Optional[str]): ip mask for replying.  Default is "".
            port (Optional[int]): port to reply on.  Default is None (chosen
                randomly).
        """
        addr_str = get_address(ip, port)

        if self._rep_sock:
            #doesn't work yet
            self._rep_sock.close()
        if self._auth:
            self._auth.stop()
        if self._stream:
            self._stream.close()

        # set up authentication
        if self._authentication:
            self._setup_auth()

        # set up the socket
        self._rep_sock = self._context.socket(zmq.REP)
        self._rep_sock.zap_domain = b'global'
        self._stream = ZMQStream(self._rep_sock)
        self._stream.on_recv(self._handle_request)
        self._rep_sock.setsockopt(zmq.RCVTIMEO, 0)
        self.__send_func = self._rep_sock.send_pyobj

        if not addr_str.endswith(":None"):
            self._rep_sock.bind(addr_str)
            logging.info("Reply socket bound to {}".format(addr_str))
        else:
            addr_str = addr_str.replace(":None", "")
            self.rep_port = self._rep_sock.bind_to_random_port(addr_str)
            logging.info("Reply socket bound randomly to {}:{}".format(addr_str,
                self.rep_port))

    def _setup_auth(self):
        """
        Sets up strawhouse authentication.  Just white/black list for now.
        """
        self._auth = IOLoopAuthenticator(context=self._context,
                                         io_loop=ioloop_instance)
        self._auth.start()
        if self._whitelist:
            self._auth.allow(*self._whitelist)
            logging.info("Whitelist set to {}".format(self._whitelist))
        if self._blacklist:
            self._auth.deny(*self._blacklist)
            logging.info("Blacklist set to {}".format(self._blacklist))

    def set_whitelist(self, *addresses):
        """
        Sets the whitelist ip addresses.

        Args:
            addresses: addresses to put on the whitelist.

        CANNOT BE SET REMOTELY.

        """
        addresses = ['127.0.0.1' if addr=='localhost' else addr for addr in addresses]
        addresses = [socket.gethostbyname(addr) if not
            is_valid_ipv4_address(addr) else addr for addr in addresses]
        self._whitelist = addresses
        self._authentication = True
        # have to set reply port up again after changing whitelist
        self.set_reply_ip(self.ip, self.rep_port)

    def set_blacklist(self, *addresses):
        """
        Sets the blacklist ip addresses.

        Args:
            addresses: addresses to put on the blacklist.

        CANNOT BE SET REMOTELY.

        """
        addresses = ['127.0.0.1' if addr=='localhost' else addr for addr in addresses]
        addresses = [socket.gethostbyname(addr) if not
            is_valid_ipv4_address(addr) else addr for addr in addresses]
        self._blacklist = addresses
        self._authentication = True
        # have to set reply port up again after changing blacklist
        self.set_reply_ip(self.ip, self.rep_port)

    @property
    def update_interval(self):
        """
        Gets the update interval.
        """
        return self._update_interval

    @update_interval.setter
    def update_interval(self, ms):
        """
        Sets the update interval in ms.
        """
        self._update_interval = ms
        if ms > 0:
            self._update_timer = ioloop.DelayedCallback(self._update_callback,
                                                        self._update_interval)
            self._update_timer.start()
        elif ms == 0:
            if self._update_timer:
                self._update_timer.stop()
        else:
            raise ValueError("Cannot have negative update interval.")

    def _update_callback(self):
        self._onupdate()
        if self.update_interval > 0:
            self._update_timer.start()

    def run_forever(self):
        """
        Starts the event loop.  Waits for incoming requests and handles them.
        """
        try:
            ioloop_instance.start()
        except KeyboardInterrupt:
            ioloop_instance.stop()
            self.close()

    def init(self):
        """
        Initialize device-specific stuff.  Doubles as reset method.
        """
        return True

    def _onupdate(self):
        """
        Called every n ms where n is `update_interval`
        """
        pass

    def _set(self, name, value):
        """
        Sets a device attribute.
        """
        # http://stackoverflow.com/questions/35566680/pythons-hasattr-sometimes-returns-incorrect-results
        try:
            getattr(self._obj_, name)
            setattr(self._obj_, name, value)
            return "0"
        except AttributeError as e:
            error = ZroError(self, name, 1)
            logging.warning(error)
            return error
        except Exception as e:
            return e

    def _get(self, name):
        """
        Returns a device attribute.
        """
        # http://stackoverflow.com/questions/35566680/pythons-hasattr-sometimes-returns-incorrect-results
        try:
            val = getattr(self._obj_, name)
            if callable(val):
                return "__callable__"
            else:
                return val
        except AttributeError as e:
            error = ZroError(self, name, 1)
            logging.warning(error)
            return error
        except Exception as e:
            return e

    def _run(self, name, args, kwargs):
        """
        Attempts to run a class method with args and kwargs.

        """
        if hasattr(self._obj_, name):
            to_call = getattr(self._obj_, name)
            if callable(to_call):
                try:
                    response = to_call(*args, **kwargs)
                    return response
                except TypeError as e:
                    if self.full_traceback_on:
                        e = "\n%s" % traceback.format_exc()
                    error = ZroError(self, name, 5, e)
                    logging.warning(error)
                    return error
                except Exception as e:
                    if self.full_traceback_on:
                        e = "\n%s" % traceback.format_exc()
                    error = ZroError(self, name, 4, e)
                    logging.exception(error)
                    return error
            else:
                error = ZroError(self, name, 3)
                logging.warning(error)
                return error
        else:
            error = ZroError(self, name, 2)
            logging.warning(error)
            return error

    def call_async(self, callable_name, *args, **kwargs):
        """
        Calls a method by name after returning a handle.  The return value of the
            called method can be retrieved later using `get_async_result()`.

        Args:
            callable_name (str): name of the callable to call asynchronously.
            *args: arguments to pass to the callable
            **kwargs: kwargs to pass to the callable

        Returns:
            hanlde(int) if callable exists.
            ZroError if callable doesn't exist.

        """
        if hasattr(self._obj_, callable_name):
            to_call = getattr(self._obj_, callable_name)
            if not callable(to_call):
                error = ZroError(self, callable_name, 3)
                logging.warning(error)
                return error
            else:
                # set up handle for retrieving return value
                kwargs['__async_handle'] = self._async_handle_index
                self._async_handle_list.append(self._async_handle_index)
                if self.threaded_async:
                    t = threading.Timer(0.1,
                                        self._call_async,
                                        [to_call]+list(args),
                                        kwargs)
                    t.start()
                else:
                    ioloop_instance.call_later(0.1,
                                               self._call_async,
                                               *([to_call]+list(args)),
                                               **kwargs)
                self._async_handle_index += 1
                return kwargs['__async_handle']
        else:
            error = ZroError(self, callable_name, 2)
            logging.warning(error)
            return error

    def register_async_callback(self, callable_name, dest_address, dest_callable):
        """
        Register a callback for a device function.  Upon completion, any asynchronous
            call to that function will send its return value to the specified
            destination.

        Args:
            callable_name (str): name of the device method we'd like to use.

        """
        if hasattr(self._obj_, callable_name):
            to_call = getattr(self._obj_, callable_name)
            if not callable(to_call):
                error = ZroError(self, callable_name, 3)
                logging.warning(error)
                return error
            else:
                # set up handle for retrieving return value
                callback = dest_address, dest_callable
                if callable_name in self._async_callbacks.keys():
                    self._async_callbacks[callable_name].append(callback)
                else:
                    self._async_callbacks[callable_name] = [callback]

        else:
            error = ZroError(self, callable_name, 2)
            logging.warning(error)
            return error

    def unregister_async_callback(self, callable_name, dest_address, dest_callable):
        """
        Unregister a callback.
        """
        if callable_name in self._async_callbacks.keys():
            for callback in self._async_callbacks[callable_name]:
                if callback == (dest_address, dest_callable):
                    self._async_callbacks[callable_name].remove(callback)

    def _call_async(self, *args, **kwargs):
        """
        Callback for callasync timer.
        """
        to_call = args[0]
        args = args[1:]
        async_handle = kwargs['__async_handle']
        del kwargs['__async_handle']

        try:
            # get function result
            self._async_results[async_handle] = to_call(*args, **kwargs)
            # if a callback is registered
            try:
                if inspect.isfunction(to_call):
                    ## TODO: fix this py2/py3 difference or just get rid of py2 stuff
                    try:
                        callable_name = to_call.func_name          # py2
                    except AttributeError:
                        callable_name = to_call.__name__           # py3
                elif inspect.ismethod(to_call):
                    try:
                        callable_name = to_call.im_func.func_name  # py2
                    except AttributeError:
                        callable_name = to_call.__func__.__name__  # py3
                else:
                    raise TypeError("callable isn't.")
                if callable_name in self._async_callbacks.keys():
                    self._send_async_result(callable_name,
                                            self._async_results[async_handle])
            except Exception as e:
                if self.full_traceback_on:
                    e = "\n%s" % traceback.format_exc()
                error = ZroError(self, str(to_call), 9, e)
                logging.exception(error)
        except Exception as e:
            if self.full_traceback_on:
                e = "\n%s" % traceback.format_exc()
            error = ZroError(self, str(to_call), 4, e)
            logging.exception(error)
            self._async_results[async_handle] = error

    def _send_async_result(self, async_callback_name, result):
        """
        Sends the result of an async call to a destination defined in
            `_async_callbacks`.
        TODO: don't use exec
        """
        for destination in self._async_callbacks[async_callback_name]:
            addr, method = destination
            p = Proxy(addr)
            exec("p.{}(result)".format(method))

    def get_async_result(self, handle, clear_data=True):
        """
        Gets the result of an async call.

        Args:
            handle (int): handle for async result
            clear_data (bool): clear result after returning

        Returns:
            object: result of asynchronous call.
        """
        try:
            result_waiting = self.async_result_waiting(handle)
        except ZroError as e:
            raise(e)

        if result_waiting:
            result = self._async_results[handle]
            if clear_data:
                self._async_handle_list.remove(handle)
                del self._async_results[handle]
        else:
            if handle in self._async_handle_list:
                raise ZroError(self, str(handle), 8)
            else:
                raise ZroError(self, str(handle), 6)
        return result

    def async_result_waiting(self, handle):
        """
        Returns True if a async result is waiting.

        Args:
            handle (int): handle to check.

        Returns:
            bool: True if result is waiting to be read.

        Raises:
            ZroError: When handle is invalid.

        """
        if handle in self._async_results:
            return True
        else:
            if handle in self._async_handle_list:
                return False
            else:
                raise ZroError(self, str(handle), 7)

    def _call_later(self, delay, callback, *args, **kwargs):
        """ Calls something later using IOLoop, passes kwargs.
        """
        ioloop_instance.call_later(delay,
                                   callback,
                                   *args,
                                   **kwargs)
        logging.debug("Calling {} {} seconds from now.".format(callback, delay))

    def _check_rep(self):
        """
        Checks the reply socket, and handles request if necessary.

        """
        try:
            request = self._rep_sock.recv()
            self._handle_request([request])
        except zmq.error.Again as e:
            #timout is 0 so we just return
            pass

    def _handle_request(self, request):
        """
        Handles a command from a proxy.

        request is formatted like so:

        {'command': command_name, 'args': args}
        OPTIONAL KEYS FOR CALLABLES: ["callable", "kwargs"]

        """
        logging.debug("Incoming request -> %s" % request)

        if isinstance(request, (list, tuple)):
            # request is from event loop callback
            for req in request:
                try:
                    data = self.__decode_request(req)
                    self._handle_request(data)
                except ValueError as e:
                    data = ZroError("Failed to decode request: {}".format(e))
                    self.__send_func(str(data))
        else:
            command = request["command"]
            args = request['args']

            if command in self._command_list.keys():
                if command == "run":
                    to_call = request['callable']
                    kwargs = request['kwargs']
                    if to_call in ["close", 'set_reply_ip']:
                        # special case for close because after we close we won't
                        # be able to send the response.  thus we send it first.
                        self.__send_func("0")
                        getattr(self, self._command_list[command])(to_call, args, kwargs)
                        return
                    result = getattr(self, self._command_list[command])(to_call, args, kwargs)
                else:
                    result = getattr(self, self._command_list[command])(*args)
            else:
                result = ZroError(self, command, 2)

            try:
                if isinstance(result, ZroError) and self.__send_func != self.__send_pyobj:
                    result = result.to_JSON()
                self.__send_func(result)
            except TypeError as e:
                logging.exception("Failed to serialize response: {}".format(result))
                # at least send a str representation of our object
                self.__send_func(str(result))

    def __decode_request(self, request):
        """ Deserializes request data and chooses appropriate response serialization.
        """
        try:
            data = pickle.loads(request)
            self.__send_func = self.__send_pyobj
            return data
        except (KeyError, ValueError, pickle.UnpicklingError) as e:
            try:
                data = json.loads(request)
                self.__send_func = self._rep_sock.send_json
                return data
            except Exception as e:
                raise ValueError("Unable to decode request.")

    def __send_pyobj(self, data):
        """ Using instead of socket.send_pyobj because we want to be able
                to specify the protocol for py2 compatibility.
        """
        data_s = pickle.dumps(data, protocol=2)
        self._rep_sock.send(data_s)

    def _onclose(self):
        """
        Runs when publisher is shut down.  Overwrite in extending class.
        """
        pass

    @property
    def uptime(self):
        """
        Time in seconds since the device started.

        Returns:
            float: uptime in seconds
        """
        return time.perf_counter()-self._start_time

    def get_uptime(self):
        """
        Deprecated.

        Returns the time in seconds since the device started.

        Returns:
            float: uptime in seconds
        """
        return self.uptime

    @property
    def platform_info(self):
        """
        Platform and version info.

        Returns:
            dict: platform info

        """
        import platform
        from mpetk import zro
        info = {
            "zro": __version__,
            "zmq": zmq.zmq_version(),
            "pyzmq": zmq.pyzmq_version(),
            "python": sys.version.split()[0],
            "os": (platform.system(), platform.release(), platform.version()),
            "hardware": (platform.processor(), platform.machine())
        }
        return info

    def get_platform_info(self):
        """
        Deprecated

        Returns platform and version info.

        Returns:
            dict: platform info

        """
        return self.platform_info

    def get_command_list(self):
        """
        Returns a list of public (no "_") methods.

        Returns:
            list: public methods

        """
        stuff = dir(self._obj_)
        methods = []
        for s in stuff:
            if s[0] != "_":
                if callable(getattr(self._obj_, s)):
                    methods.append(s)

        #manually remove some stuff that we dont' want people calling
        methods.remove("run_forever")
        methods.remove("set_whitelist")
        methods.remove("set_blacklist")

        return methods

    def get_attribute_list(self):
        """
        Returns a list of public (no "_") attributes.

        Returns:
            list: public attributes
        """
        stuff = dir(self._obj_)
        attributes = []
        for s in stuff:
            if s[0] != "_":
                if not callable(getattr(self._obj_, s)):
                    attributes.append(s)

        # manually remove some stuff that we can't make private
        attributes.remove("trait_names")

        return attributes

    def _getAttributeNames(self):
        """
        Required for ipython autocomlete to work.
        """
        return self.get_attribute_list()

    def flush(self):
        """
        Handles all pending requests.
        """
        self._stream.flush()

    def close(self):
        """
        Closes sockets, shuts down ZMQ and all streams, event loops, threads.
        """
        logging.info("Shutting down...")
        self._onclose()
        self._stream.stop_on_recv()
        self._stream.close()
        if self._auth:
            self._auth.stop()

        if self._update_timer:
            self._update_timer.stop()
        ioloop_instance.stop()
        ioloop_instance.close()
        logging.info("IO loop stopped.")
        sys.exit(0)  #why does this throw tornado error?


class BasePubRepDevice(RemoteObject):
    """
    Reply device that also publishes on a publishing socket.  Designed to be
        extended.

    Args:
        ip (str): IP address to broadcast on.
        pub_port (int): Port to PUB on.
        rep_port (int): Port to REP on.

    Example:
        >>> bprd = BasePubRepDevice("*", 5555, 5556)
        >>> bprd.publishing = True
        >>> bprd.run_forever()

    ##TODO: Get rid of ip arg.  Unecessary.

    """
    def __init__(self,
                 ip="*",
                 pub_port=None,
                 rep_port=None,
                 hwm=100,
                 pub_serialization='pickle',
                 ):

        self.pub_port = pub_port

        self._hwm = hwm  # how many messages to que up before dropping
        self._pub_serialization = pub_serialization.lower()

        self._pub_sock = None
        self.set_publish_ip(ip, pub_port)

        self.publishing = False

        super(BasePubRepDevice, self).__init__(ip, rep_port)

    def set_publish_ip(self, ip, port=None):
        """
        Sets up the publisher socket to the specified ip/port.
        """
        if self._pub_sock:
            self._pub_sock.close()

        addr_str = get_address(ip, port)

        self._pub_sock = self._context.socket(zmq.PUB)
        self._pub_sock.setsockopt(zmq.SNDHWM, self._hwm)

        if self._pub_serialization in ['pickle', 'pkl', 'p']:
            self.__pub_func = self._pub_sock.send_pyobj
        elif self._pub_serialization in ['json', 'j']:
            self.__pub_func = self._pub_sock.send_json
        else:
            raise ValueError("Invalid serialization type. Try 'pickle' or 'json'")

        if not addr_str.endswith(":None"):
            self._pub_sock.bind(addr_str)
            self.pub_port = addr_str.split(":")[-1]
            logging.info("Publish socket bound to {}".format(addr_str))
        elif addr_str.endswith(":None"):
            addr_str = addr_str[:-5]
            self.pub_port = self._pub_sock.bind_to_random_port(addr_str)
            logging.info("Publish socket bound randomly to {}:{}".format(addr_str,
                self.pub_port))
        else:
            raise RuntimeError("Invalid ip or port: {}".format(addr_str))

    def run_forever(self):
        """
        Continuously publishes and checks the reply socket.
        """
        logging.info("Publishing on tcp://{}:{}".format(self.ip, self.pub_port))
        super(BasePubRepDevice, self).run_forever()

    @property
    def hwm(self):
        """
        Returns the outgoing high water mark for the publish socket.

        Returns:
            int: the high water mark
        """
        return self._hwm

    @hwm.setter
    def hwm(self, hwm):
        """
        Sets the outgoing high water mark for the publish socket.

        Args:
            hwm (int): the high water mark
        """
        # have to unbind for some reason
        self._pub_sock.unbind("tcp://%s:%s" % (self.ip, self.pub_port))
        self._pub_sock.setsockopt(zmq.SNDHWM, hwm)
        self._pub_sock.bind("tcp://%s:%s" % (self.ip, self.pub_port))
        self._hwm = hwm

    def publish(self, to_publish=None):
        """
        Publishes the data passed in.  If no args, publishes whatever is
            returned by the device's _publish() method.

        Args:
            to_publish (optional[object]): python object to publish
        """
        if to_publish is not None:
            output = to_publish
        else:
            output = self._publish()
        if output is not None:
            self.__pub_func(output)
            #logging.debug("Published: {}".format(output))  #Useful?
        else:
            return

    def _publish(self):
        """
        Returns the python object to publish.  Overwrite in extending class.
        """
        return None

    def close(self):
        """
        Closes sockets, shuts down ZMQ.
        """
        self._pub_sock.close()
        super(BasePubRepDevice, self).close()


class BaseSubRepDevice(RemoteObject):
    """
    Repy device that also subscribes to publisher sockets.  Creates a new
        subscriber socket for each subscription.

    Why do we use multiple subscriber sockets instead of connecting one
        subscriber socket to many publishers?  So that we can know where each
        packet is coming from.

    Args:
        rep_port (Optional[int]): port to reply on.  If empty, one is chosen
            automatically.

    """
    def __init__(self, rep_port=None):

        self._subscriptions = OrderedDict()

        super(BaseSubRepDevice, self).__init__(rep_port=rep_port)

    def add_subscription(self, ip, pub_port, hwm=1):
        """
        Adds a subscription to a publisher at a specified ip and port.

        Args:
            ip (str): ip address of publisher
            port (int): port of publisher
            hwm (Optional[int]): high water mark of subscriber
        """
        connection_str = "tcp://{}:{}".format(ip, pub_port)
        socket = self._context.socket(zmq.SUB)
        socket.setsockopt(zmq.RCVHWM, hwm)
        socket.setsockopt(zmq.RCVTIMEO, 0)
        socket.setsockopt_string(zmq.SUBSCRIBE, "")
        socket.connect(connection_str)
        self._subscriptions[connection_str] = socket
        logging.info("Added subscriber on {}".format(connection_str))

    def remove_subscription(self, ip, port=None):
        """
        Removes any subscription that matches the specified ip and optional
            port.

        Args:
            ip (str): ip address of publisher
            port (Optional[int]): port of publisher

        """
        for con_str in self._subscriptions.keys():
            if ip in con_str:
                self._subscriptions[con_str].close()
                del self._subscriptions[con_str]
                logging.info("Removed subscription on {}".format(con_str))

    def remove_all_subscriptions(self):
        """
        Removes all subscriptions.
        """
        for socket in self._subscriptions.values():
            socket.close()
        self._subscriptions = OrderedDict()
        logging.info("Removed all subscriptions.")

    def get_subscriptions(self):
        """
        Returns a list of subscriptions.
        """
        return self._subscriptions.keys()

    def run_forever(self):
        """
        Continuously checks the reply and subscription sockets.

        ##TODO: Use ioloop like the other devices.

        """
        logging.info("Replying on tcp://%s:%s" % (self.ip, self.rep_port))
        try:
            while True:
                self._check_rep()
                self._check_sub()
                self._onupdate()
        except KeyboardInterrupt:
            self.close()
        except Exception as e:
            logging.exception("Error while handling socket data -> %s" % e)

    def _check_sub(self):
        """
        Checks the reply socket, and handles request if necessary.
        """
        for name, sock in self._subscriptions.items():
            try:
                data = self._decode_data(sock.recv())
                self.handle_data(name, data)
            except zmq.error.Again:
                # timout is 0 so we just pass
                pass

    def _decode_data(self, data):
        """ Gross.  Fix this.
        """
        try:
            pyobj = pickle.loads(data)
        except:
            try:
                pyobj = pickle.loads(data, encoding='latin-1')
            except:
                try:
                    pyobj = pickle.loads(data, encoding='bytes')
                except:
                    pyobj = json.loads(data)
        return pyobj


    def handle_data(self, from_str, data):
        """
        Function for handling any data from subscriber sockets.  Overwrite in
            extending class.
        """
        logging.info("Data from {}:{}".format(from_str, data))

    def close(self):
        """
        Closes sockets and terminates application.
        """
        self.remove_all_subscriptions()
        super(BaseSubRepDevice, self).close()


class BaseProducerRepDevice(RemoteObject):
    """
    Reply device that also pushes to a PUSH socket and optional sink device.
    """
    def __init__(self, rep_port=None):

        self.push_port = None
        self._push_sock = None
        self._sink = None

        super(BaseProducerRepDevice, self).__init__(rep_port=rep_port)

    def set_push_ip(self, ip="", port=None):
        """
        Sets up the push socket to the specified ip/port.
        """
        if self._push_sock:
            self._push_sock.close()

        addr_str = get_address(ip, port)
        self._push_sock = self._context.socket(zmq.PUSH)
        self._push_sock.bind(addr_str)

        if port:
            self.push_port = port
        else:
            self.push_port = addr_str.split(":")[-1]

    def set_sink(self, ip, rep_port):
        """
        Sets a sink device to allow for batch start/stop communication.
        """
        from proxy import DeviceProxy
        self._sink = DeviceProxy(ip, rep_port)

    def start_batch(self, name=""):
        """
        Tells the sink to start a new batch.
        """
        if self._sink:
            self._sink.start_batch(name)
        else:
            raise RuntimeError("No sink connected.")

    def end_batch(self):
        """
        Tells the sink to end the current batch.  Is this necessary?
        """
        if self._sink:
            self._sink.end_batch()
        else:
            raise RuntimeError("No sink connected.")

    def push(self, work, id_=None):
        """
        Pushes some work to the Consumers along with an optional identifier.
        """
        self._push_sock.send_pyobj({'work': work, 'id': id_})
        logging.info("Pushed work with id {}".format(id_))

    def close(self):
        """
        Closes sockets and terminates application.
        """
        self._push_sock.close()
        super(BaseProducerRepDevice, self).close()

    def run_forever(self):
        logging.info("Pushing on tcp://*:%s" % (self.push_port))
        super(BaseProducerRepDevice, self).run_forever()


class BaseConsumerRepDevice(RemoteObject):
    """
    Reply device that also pulls incoming work, processes it, then pushes the
        output to the sink.
    """
    def __init__(self, rep_port=None):
        self._pull_sock = None
        self._push_sock = None

        super(BaseConsumerRepDevice, self).__init__(rep_port=rep_port)

    def set_source(self, ip, port):
        self.pull_ip = ip
        self.pull_port = port
        if self._pull_sock:
            self._pull_sock.close()
        self._pull_sock = self._context.socket(zmq.PULL)
        self._pull_stream = ZMQStream(self._pull_sock)
        self._pull_stream.on_recv(self._incoming_data)
        #self._pull_sock.setsockopt(zmq.RCVTIMEO, 0)
        sock_str = "tcp://%s:%s" % (ip, port)
        self._pull_sock.connect(sock_str)
        logging.info("Collecting on {}".format(sock_str))

    def set_sink(self, ip, port):
        self.push_ip = ip
        self.push_port = port
        if self._push_sock:
            self._push_sock.close()
        self._push_sock = self._context.socket(zmq.PUSH)
        sock_str = "tcp://%s:%s" % (ip, port)
        self._push_sock.connect(sock_str)
        logging.info("Pushing on {}".format(sock_str))

    def run_forever(self):
        """
        Continuously checks the reply and pull sockets.
        """
        super(BaseConsumerRepDevice, self).run_forever()

    def _incoming_data(self, data):
        """
        Incoming data callback.

        Args:
            data (list): a list of pickled data packets

        """
        for packet in data:
            packet = pickle.loads(packet)
            work = packet['work']
            id_ = packet['id']
            self._handle_work(work, id_)

    def _handle_work(self, work, id_):
        """
        Processes new work and sends it to sink.
        """
        logging.info("New work arrived. ID: %s" % id_)
        output = self.process(work)
        logging.info("Processing on ID: %s finished." % id_)
        if self._push_sock:
            packet = {"data": output, "id": id_}
            self._push_sock.send_pyobj(packet)
            logging.info("Results for ID: %s transmitted." % id_)
        else:
            logging.warning("Data processed but no sink configured.")

    def process(self, data):
        """
        Processes some data.  This is to be implemented by extending class.
        """
        return data


class BaseSinkRepDevice(RemoteObject):
    """
    Reply device that accepts data from Consumers.
    """
    def __init__(self, rep_port=None):
        self.pull_port = None
        self._pull_sock = None

        #TODO: think of a better batch naming system
        self.batch = "0"

        super(BaseSinkRepDevice, self).__init__(rep_port=rep_port)

    def set_pull_ip(self, ip="", port=None):
        if self._pull_sock:
            self._pull_sock.close()

        addr_str = get_address(ip, port)

        self._pull_sock = self._context.socket(zmq.PULL)
        self._pull_stream = ZMQStream(self._pull_sock)
        self._pull_stream.on_recv(self._incoming_data)
        self._pull_sock.bind(addr_str)

        if port:
            self.pull_port = port
        else:
            self.pull_port = addr_str.split(":")[-1]

    def start_batch(self, name="0"):
        """
        Starts a new batch.

        What else should this do?
        """
        self.batch = name
        logging.info("Batch {} started.".format(self.batch))

    def end_batch(self):
        """
        ends a batch.

        What should this do?
        """
        logging.info("Batch {} ended.".format(self.batch))
        self.batch = "0"

    def run_forever(self):
        """
        Continuously checks the reply and pull sockets.
        """
        logging.info("Collecting on tcp://{}:{}".format(self.ip,
                                                        self.pull_port))
        super(BaseSinkRepDevice, self).run_forever()

    def _incoming_data(self, data):
        """
        Incoming data callback.

        Args:
            data (list): a list of pickled data packets

        """
        for packet in data:
            packet = pickle.loads(packet)
            work = packet['data']
            id_ = packet['id']
            self._handle_data(work, id_)

    def _handle_data(self, data, id_):
        """
        Creates a unique id for the data based on batch, timestamp, and
            identifier.  Then runs `handle_data`
        """
        t = datetime.datetime.now().strftime('%y%m%d%H%M%S%f')
        data_name = "{}_{}_{}".format(self.batch, id_, t)
        self.handle_data(data_name, data)
        logging.info("Data {} handled.".format(data_name))

    def handle_data(self, name, value):
        """
        Handles data.  To be overwritten by extending class.
        """
        pass


###############################################################################

class Publisher(BasePubRepDevice):
    """ Publisher device.
        TODO: remove pub port arg.  Should be set after instantiation using
            `set_publish_ip`
    """
    def __init__(self, rep_port=None, pub_port=None, hwm=10, pub_serialization='pickle'):
        super(Publisher, self).__init__(rep_port=rep_port, pub_port=pub_port, hwm=hwm, pub_serialization=pub_serialization)


class Subscriber(BaseSubRepDevice):
    """ Subscriber device. """
    def __init__(self, rep_port=None):
        super(Subscriber, self).__init__(rep_port=rep_port)


class Producer(BaseProducerRepDevice):
    """ Producer device. """
    def __init__(self, rep_port=None):
        super(Producer, self).__init__(rep_port=rep_port)


class Consumer(BaseConsumerRepDevice):
    """ Consumer device. """
    def __init__(self, rep_port=None):
        super(Consumer, self).__init__(rep_port=rep_port)


class Sink(BaseSinkRepDevice):
    """ Sink device. """
    def __init__(self, rep_port=None):
        super(Sink, self).__init__(rep_port=rep_port)

#############################################################################

class RemoteDummy(RemoteObject):
    """ Just a remote object that will let you throw whatever gets/sets/runs you want to
            throw at it and not really do anything.

        Works like a regular RemoteObject but will let you call whatever methods you like, even
            if they don't exist.  If they do exist, it will attempt to call them but will not throw
            exceptions if they fail.
    """
    def __init__(self, rep_port=None):
        super(RemoteDummy, self).__init__(rep_port=rep_port)

    def _set(self, name, value):
        """
        Sets a device attribute.
        """
        setattr(self, name, value)
        return "0"

    def _get(self, name):
        """
        Returns a device attribute.
        """
        if hasattr(self, name):
            val = getattr(self, name)
            if callable(val):
                return "callable"
            else:
                return val
        else:
            return "callable"

    def _run(self, name, args, kwargs):
        """
        Attempts to run a class method with args and kwargs.
        """
        if hasattr(self, name):
            to_call = getattr(self, name)
            if callable(to_call):
                try:
                    val = to_call(*args, **kwargs)
                except Exception as e:
                    val = None
                    logging.exception(e)
                return val
        return True

############################################################################

if __name__ == '__main__':
    pass
