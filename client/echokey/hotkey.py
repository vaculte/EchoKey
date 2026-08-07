"""Global hotkey listener that sends start/stop events to a queue."""

from queue import Queue

from pynput import keyboard

from echokey.config import settings


class HotkeyListener:
    """Listen for a single global key: press starts, release stops recording."""

    def __init__(self, event_queue: Queue):
        self.event_queue = event_queue
        self.listener: keyboard.Listener | None = None
        self._key = getattr(keyboard.Key, settings.HOTKEY.lower(), keyboard.Key.f12)

    def _on_press(self, key):
        if key == self._key:
            self.event_queue.put("start")

    def _on_release(self, key):
        if key == self._key:
            self.event_queue.put("stop")

    def start(self) -> None:
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self.listener.start()

    def stop(self) -> None:
        if self.listener is not None:
            self.listener.stop()
