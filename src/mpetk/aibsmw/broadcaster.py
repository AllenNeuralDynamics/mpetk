# Send UDP broadcast packets

MYPORT = 8793
import sys, time
from socket import *

s = socket(AF_INET, SOCK_DGRAM)
s.bind(('', 8793))
s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

while 1:
    print('.', end='', flush=True)
    data = repr(time.time()) + '\n'
    s.sendto(data.encode(), ('<broadcast>', MYPORT))
    time.sleep(2)
