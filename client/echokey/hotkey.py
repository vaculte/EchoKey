"""Global hotkey listener that sends start/stop events to a queue."""

import logging
from queue import Queue

from pynput import keyboard

from echokey.config import settings

logger = logging.getLogger(__name__)


class HotkeyListener:
    """Listen for a global hotkey and send start/stop events.

    Supports both single keys (e.g. ``f12``) and combos (e.g. ``super+z`` or ``<cmd>+z``).
    For a single key, press starts recording and release stops it.
    For a combo, hold the combo while speaking; releasing any key stops recording.
    """

    def __init__(self, event_queue: Queue):
        self.event_queue = event_queue
        self.hotkey = settings.HOTKEY.strip().lower()
        self._modifiers, self._target = self._parse_hotkey(self.hotkey)
        self._pressed: set[str] = set()
        self._recording = False
        self._listener: keyboard.Listener | None = None

    @staticmethod
    def _normalise_modifier(name: str) -> str | None:
        """Map left/right/super/win modifier names to a canonical form."""
        if name in ("ctrl", "ctrl_l", "ctrl_r"):
            return "ctrl"
        if name in ("alt", "alt_l", "alt_r"):
            return "alt"
        if name in ("shift", "shift_l", "shift_r"):
            return "shift"
        if name in ("cmd", "cmd_l", "cmd_r", "super", "win"):
            return "cmd"
        return None

    def _parse_hotkey(self, hotkey: str) -> tuple[set[str], str | None]:
        parts = [part.strip().strip("<>") for part in hotkey.split("+")]
        modifiers: set[str] = set()
        target: str | None = None
        for part in parts:
            norm = self._normalise_modifier(part)
            if norm:
                modifiers.add(norm)
            else:
                target = part
        if not target:
            logger.warning("No target key found in hotkey '%s'", hotkey)
        logger.info("Listening for hotkey: modifiers=%s target=%s", modifiers, target)
        return modifiers, target

    def _key_name(self, key: keyboard.Key | keyboard.KeyCode) -> str | None:
        if isinstance(key, keyboard.Key):
            name = key.name
            if name in ("ctrl_l", "ctrl_r"):
                return "ctrl"
            if name in ("alt_l", "alt_r"):
                return "alt"
            if name in ("shift_l", "shift_r"):
                return "shift"
            if name in ("cmd_l", "cmd_r"):
                return "cmd"
            return name
        if isinstance(key, keyboard.KeyCode):
            return (key.char or "").lower()
        return None

    def _on_press(self, key):
        name = self._key_name(key)
        if name is None:
            return
        self._pressed.add(name)
        if (
            not self._recording
            and self._modifiers.issubset(self._pressed)
            and self._target in self._pressed
        ):
            self._recording = True
            self.event_queue.put("start")
            logger.info("Hotkey pressed: starting recording")

    def _on_release(self, key):
        name = self._key_name(key)
        if name in self._pressed:
            self._pressed.remove(name)
        if self._recording and (
            self._target not in self._pressed
            or not self._modifiers.issubset(self._pressed)
        ):
            self._recording = False
            self.event_queue.put("stop")
            logger.info("Hotkey released: stopping recording")

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
