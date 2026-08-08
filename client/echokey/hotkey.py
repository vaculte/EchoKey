"""Global hotkey listener with pynput fallback and native Wayland evdev support."""

import abc
import logging
import os
import select
import threading
from queue import Queue

from echokey.config import settings

logger = logging.getLogger(__name__)


def _normalise_modifier(name: str) -> str | None:
    """Map left/right/super/win modifier names to a canonical form."""
    name = name.lower()
    if name in ("ctrl", "ctrl_l", "ctrl_r"):
        return "ctrl"
    if name in ("alt", "alt_l", "alt_r"):
        return "alt"
    if name in ("shift", "shift_l", "shift_r"):
        return "shift"
    if name in ("cmd", "cmd_l", "cmd_r", "super", "win"):
        return "cmd"
    return None


def _parse_hotkey(hotkey: str) -> tuple[set[str], str | None]:
    """Split a hotkey string like ``f12`` or ``<cmd>+z`` into modifiers and target."""
    parts = [part.strip().strip("<>") for part in hotkey.split("+")]
    modifiers: set[str] = set()
    target: str | None = None
    for part in parts:
        norm = _normalise_modifier(part)
        if norm:
            modifiers.add(norm)
        else:
            target = part
    if not target:
        logger.warning("No target key found in hotkey '%s'", hotkey)
    logger.info("Listening for hotkey: modifiers=%s target=%s", modifiers, target)
    return modifiers, target


class BaseHotkeyListener(abc.ABC):
    """Abstract interface for global hotkey listeners."""

    def __init__(self, event_queue: Queue):
        self.event_queue = event_queue
        self.hotkey = settings.HOTKEY.strip().lower()
        self._modifiers, self._target = _parse_hotkey(self.hotkey)

    @abc.abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self) -> None:
        raise NotImplementedError


class PynputHotkeyListener(BaseHotkeyListener):
    """pynput-based listener. Works on X11 and inside XWayland windows."""

    def __init__(self, event_queue: Queue):
        super().__init__(event_queue)
        from pynput import keyboard

        self._keyboard = keyboard
        self._pressed: set[str] = set()
        self._recording = False
        self._listener = None

    def _key_name(self, key):
        if isinstance(key, self._keyboard.Key):
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
        if isinstance(key, self._keyboard.KeyCode):
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
            logger.info("Hotkey PRESSED: %s (pressed set: %s)", name, self._pressed)

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
            logger.info("Hotkey RELEASED: %s (pressed set: %s)", name, self._pressed)
        if settings.DEBUG and name is not None:
            logger.debug("[hotkey debug] release: %s", name)

    def start(self) -> None:
        self._listener = self._keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()


class EvdevHotkeyListener(BaseHotkeyListener):
    """Native Linux evdev listener for global hotkeys on Wayland."""

    def __init__(self, event_queue: Queue):
        super().__init__(event_queue)
        from evdev import ecodes

        self._ecodes = ecodes
        self._pressed: set[str] = set()
        self._recording = False
        self._devices: list = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @staticmethod
    def _is_keyboard(device) -> bool:
        """Heuristic: device has EV_KEY capability."""
        caps = device.capabilities()
        return caps is not None and 1 in caps  # EV_KEY == 1

    def _find_devices(self):
        """Find keyboard input devices."""
        try:
            import evdev
        except Exception as exc:
            logger.warning("Could not import evdev: %s", exc)
            return []
        devices = []
        for path in evdev.list_devices():
            try:
                device = evdev.InputDevice(path)
                if self._is_keyboard(device):
                    devices.append(device)
            except Exception as exc:
                logger.debug("Skipping input device %s: %s", path, exc)
        return devices

    def _key_name(self, code: int) -> str | None:
        """Map evdev KEY_* code to a canonical key name."""
        names = self._ecodes.KEY.get(code)
        if names is None:
            return None
        if isinstance(names, list):
            names = names[0]
        raw = names.lower().replace("key_", "")
        if raw in ("leftctrl", "rightctrl"):
            return "ctrl"
        if raw in ("leftalt", "rightalt"):
            return "alt"
        if raw in ("leftshift", "rightshift"):
            return "shift"
        if raw in ("leftmeta", "rightmeta", "compose"):
            return "cmd"
        return raw

    def _on_press(self, name: str):
        self._pressed.add(name)
        if (
            not self._recording
            and self._modifiers.issubset(self._pressed)
            and self._target in self._pressed
        ):
            self._recording = True
            self.event_queue.put("start")
            logger.info("Hotkey PRESSED: %s (pressed set: %s)", name, self._pressed)

    def _on_release(self, name: str):
        if name in self._pressed:
            self._pressed.remove(name)
        if self._recording and (
            self._target not in self._pressed
            or not self._modifiers.issubset(self._pressed)
        ):
            self._recording = False
            self.event_queue.put("stop")
            logger.info("Hotkey RELEASED: %s (pressed set: %s)", name, self._pressed)

    def _read_loop(self):
        """Poll evdev devices and translate key events into start/stop."""
        import evdev

        self._devices = self._find_devices()
        if not self._devices:
            logger.warning("No evdev keyboard devices found; hotkey will not work")
            return
        logger.info("Monitoring %d evdev keyboard device(s)", len(self._devices))
        while not self._stop_event.is_set():
            try:
                r, _, _ = select.select(self._devices, [], [], 0.1)
            except ValueError:
                # A device was closed or removed; drop stale references.
                self._devices = [d for d in self._devices if d.fd is not None]
                continue
            except OSError as exc:
                logger.debug("select error: %s", exc)
                continue
            for device in r:
                try:
                    for event in device.read():
                        if event.type != self._ecodes.EV_KEY:
                            continue
                        name = self._key_name(event.code)
                        if name is None:
                            continue
                        if event.value == 1:  # key press
                            self._on_press(name)
                        elif event.value == 0:  # key release
                            self._on_release(name)
                except Exception as exc:
                    logger.debug("Error reading %s: %s", device.path, exc)

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        for device in self._devices:
            try:
                device.close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=1.0)


def _wayland_available() -> bool:
    return os.environ.get("WAYLAND_DISPLAY") is not None


def _evdev_available() -> bool:
    """Check whether evdev can read at least one keyboard device."""
    try:
        import evdev
    except Exception as exc:
        logger.warning("evdev not importable: %s", exc)
        return False
    try:
        paths = evdev.list_devices()
    except Exception as exc:
        logger.warning("evdev.list_devices failed: %s", exc)
        return False
    if not paths:
        logger.warning("No /dev/input/event* devices found")
        return False
    for path in paths:
        try:
            device = evdev.InputDevice(path)
            caps = device.capabilities()
            if caps and 1 in caps:
                device.close()
                return True
        except PermissionError as exc:
            logger.warning(
                "Cannot open %s (are you in the 'input' group?): %s", path, exc
            )
        except Exception as exc:
            logger.debug("Cannot open evdev device %s: %s", path, exc)
    return False


def create_listener(event_queue: Queue) -> BaseHotkeyListener:
    """Create the best available hotkey listener for the current session.

    On Wayland, prefer evdev so the hotkey works in every window, including
    native Wayland applications. Fall back to pynput on X11 or when evdev is
    unavailable.
    """
    if _wayland_available() and _evdev_available():
        logger.info("Using evdev hotkey listener for Wayland")
        return EvdevHotkeyListener(event_queue)
    logger.info("Using pynput hotkey listener")
    return PynputHotkeyListener(event_queue)
