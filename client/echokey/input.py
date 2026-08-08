"""Type the transcribed text into the currently focused input field."""

import logging
import os
import shutil
import subprocess
import time

from pynput.keyboard import Controller, Key

try:
    import pyperclip
except Exception:  # pragma: no cover - optional fallback
    pyperclip = None

logger = logging.getLogger(__name__)
_controller = Controller()


def _wayland_available() -> bool:
    return os.environ.get("WAYLAND_DISPLAY") is not None


def _wtype_available() -> bool:
    return shutil.which("wtype") is not None


def _type_with_wtype(text: str) -> None:
    """Use wtype to inject text under Wayland."""
    subprocess.run(["wtype", text], check=True, timeout=30)


def _type_with_pynput(text: str) -> None:
    """Use the clipboard + Ctrl+V to preserve Unicode characters."""
    if pyperclip is None:
        _controller.type(text)
        return

    try:
        old_clip = pyperclip.paste()
    except Exception as exc:
        logger.warning("Could not read clipboard: %s", exc)
        old_clip = ""

    try:
        pyperclip.copy(text)
        time.sleep(0.05)
        with _controller.pressed(Key.ctrl):
            _controller.press("v")
            _controller.release("v")
        time.sleep(0.05)
    except Exception as exc:
        logger.warning("Clipboard paste failed: %s", exc)
        _controller.type(text)
    finally:
        try:
            pyperclip.copy(old_clip)
        except Exception as exc:
            logger.warning("Could not restore clipboard: %s", exc)


def type_text(text: str) -> None:
    """Type the given text as if from a keyboard.

    On Wayland, prefer wtype so text is injected into native Wayland
    windows. On X11 or when wtype is unavailable, fall back to the clipboard
    + Ctrl+V path.
    """
    if _wayland_available() and _wtype_available():
        try:
            _type_with_wtype(text)
            return
        except Exception as exc:
            logger.warning("wtype failed: %s; falling back to pynput", exc)
    _type_with_pynput(text)
