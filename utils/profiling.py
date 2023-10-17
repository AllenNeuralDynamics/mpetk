import inspect
import logging
import os
import time

import crayons


def time_prof(ns: bool = False):
    def decorator(function):
        units = 'ns' if ns else "s"
        timer = time.perf_counter_ns if ns else time.perf_counter

        def inner_function(*args, **kwargs):
            start_time = timer()
            function(*args, **kwargs)
            end_time = timer()
            print(f'{function.__name__}: {round((end_time - start_time), 3)} {units}')

        return inner_function

    return decorator


class StopWatch:
    def __init__(self, banner="", start_now=True):

        stack = inspect.stack()
        filename = crayons.blue(os.path.basename(stack[1].filename))
        func = crayons.blue(stack[1].function)
        line_no = stack[1].lineno
        self.banner = f"{filename}: {func}(), line {line_no}"
        self.deltas = []

        self.is_running = start_now
        if self.is_running:
            self.start_time = time.perf_counter()

    def reset(self):
        self.is_running = False
        self.deltas = []
        self.start_time = time.perf_counter()

    def start(self):
        if self.is_running:
            logging.warning("StopWatch is already running")
            return
        self.is_running = True
        self.start_time = time.perf_counter()

    def stop(self):
        self.deltas.append(round(self.start_time - time.perf_counter(), 3))
        self.is_running = False

    @property
    def elapsed_time(self):
        if not self.deltas:
            return 0
        return round(sum(self.deltas) / len(self.deltas), 3)

    def __del__(self):
        if self.is_running:
            self.stop()
        end_time = time.perf_counter()
        delta = crayons.yellow(self.elapsed_time)
        print(f"{self.banner}: [{delta}] s")


def x():
    s = StopWatch()

    s.stop()
    s.start()
    s.stop()
    s.start()

x()
