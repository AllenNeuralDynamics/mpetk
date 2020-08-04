"""
misc.py

Miscellaneous functions.

"""
import socket

def get_address(ip="", port=None):
    """
    Trys to get a properly formatted address given a port and ip.

    ZMQ likes address to be in this format:

        {protocol}://{ip}:{port}

    Args:
        ip (Optional[str]): ip address with some semblance of correct formatting
        port (Optional[int]): port to use in the event that the port is not
            included in the IP

    Returns:
        str: a properly formatted ip str.

    """
    if not ip and not port:
        raise ValueError("Need a port or IP.")
    elif not ip and port:
        return "tcp://*:{}".format(port)
    else:
        if ip[:6] != "tcp://":
            ip = "tcp://"+ip
        if len(ip.split(":")) == 2:
            return "{}:{}".format(ip, port)
        else:
            return ip

def is_valid_ipv4_address(address):
    try:
        socket.inet_pton(socket.AF_INET, address)
    except AttributeError:  # no inet_pton here, sorry
        try:
            socket.inet_aton(address)
        except socket.error:
            return False
        return address.count('.') == 3
    except socket.error:  # not a valid address
        return False
    return True

def serve(obj, port=None):
    """ Serve an object on the specified port.
    """
    from zro import RemoteObject
    ro = RemoteObject(rep_port=port)
    ro._obj_ = obj
    ro.run_forever()
