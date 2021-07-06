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
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)

        if callback and directory:
            global observer

            if observer:
                observer.stop()
            else:
                observer = Observer()

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
