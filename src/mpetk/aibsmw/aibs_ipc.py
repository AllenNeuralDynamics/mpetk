import atexit
from pathlib import Path
from typing import List, Union

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler, FileCreatedEvent, EVENT_TYPE_CREATED

observer: Observer = None


class CallbackCreationException(Exception):
    pass


class InstructFilePmeh(PatternMatchingEventHandler):
    def __init__(self, instruct_cb=None, patterns=None, ignore_patterns=None, ignore_directories=False, case_sensitive=False):
        super().__init__(patterns, ignore_patterns, ignore_directories, case_sensitive)
        self._instruct_cb = instruct_cb

    def on_created(self, event):
        if event.event_type == EVENT_TYPE_CREATED:
            # execute cb
            event_file = Path(event.src_path)

            contents = None
            with open(event_file, 'r') as f:
                contents = f.read()
            
            self._instruct_cb(event_file.absolute(), contents)

            event_file.unlink()


def register_instruct_callback(callback: callable = None, directory: str = None, extra_patterns: List[str] = []):
    """
    Associates a callback to a file create event and passes back the contents of the file that triggered the event.
    Note: File removed automatically once read.

    -Callback Anatomy-
    The callback should take two arguments:
    ** Argument 1 (str): The absolute file path for the file which triggered this event.
    ** Argument 2 (str): The contents of said file.  

    :param callback: A callable with signature as described above (str, str)
    :param directory: The directory to monitor
    :extra_patterns: An optional list of additional patterns to search for. Defaults to '*.event'.
    """
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)

        if callback and directory:
            global observer

            if observer:
                observer.stop()
            else:
                observer = Observer()
                atexit.register(atexit_handler)

            instruction_filter = InstructFilePmeh(instruct_cb=callback, patterns=["*.event"] + extra_patterns)
            observer.schedule(instruction_filter, directory)
            observer.start()

    except Exception as e:
        if type(e) is OSError:
            # directory invalid
            raise CallbackCreationException("Directory cannot be created", e)
        else:
            raise CallbackCreationException("Callback cannot be assigned", e)
        # print(f"type: {type(e)}, str: {e}")

def atexit_handler():
    global observer
    if observer:
        observer.stop()
