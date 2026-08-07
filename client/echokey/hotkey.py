"""Global hotkey listener that sends start/stop events to a queue."""

from queue import Queue

from pynput import keyboard

from echokey.config import settings


class HotkeyListener:
    """Listen for a global hotkey.

    Single key (e.g. ``f12``): press starts recording, release stops it.
    Modifier combo (e.g. ``<cmd>+z`` for Super+Z): each press toggles recording.
    """

    def __init__(self, event_queue: Queue):
        self.event_queue = event_queue
        self.hotkey = settings.HOTKEY.strip().lower()
        self._is_combo = "+" in self.hotkey or "<" in self.hotkey
        self._recording = False
        self._listener: keyboard.Listener | keyboard.GlobalHotKeys | None = None
        self._single_key: keyboard.Key | keyboard.KeyCode | None = None

    def _single_press(self, key):
        if key == self._single_key:
            self.event_queue.put("start")

    def _single_release(self, key):
        if key == self._single_key:
            self.event_queue.put("stop")

    def _toggle(self):
        if self._recording:
            self.event_queue.put("stop")
        else:
            self.event_queue.put("start")
        self._recording = not self._recording

    def _resolve_single_key(self):
        key_name = self.hotkey.lower()
        if hasattr(keyboard.Key, key_name):
            return getattr(keyboard.Key, key_name)
        return keyboard.KeyCode.from_char(key_name)

    def start(self) -> None:
        if self._is_combo:
            hotkeys = {settings.HOTKEY: self._toggle}
            self._listener = keyboard.GlobalHotKeys(hotkeys)
            self._listener.start()
        else:
            self._single_key = self._resolve_single_key()
            self._listener = keyboard.Listener(
                on_press=self._single_press,
                on_release=self._single_release,
            )
            self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
