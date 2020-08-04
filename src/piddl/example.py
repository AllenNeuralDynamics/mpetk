from piddl import one_instance, InstanceLocks
import time


@one_instance(mode = InstanceLocks.DAEMON_LOCK)
def main():
    while True:
        time.sleep(3)


if __name__ == '__main__':
    main()
