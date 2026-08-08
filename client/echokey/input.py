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


def _wl_clipboard_available() -> bool:
    return shutil.which("wl-copy") is not None and shutil.which("wl-paste") is not None


def _type_with_wtype(text: str) -> None:
    """Use wtype to inject text under Wayland."""
    subprocess.run(["wtype", text], check=True, timeout=30)


def _type_with_wtype_clipboard(text: str) -> None:
    """Use wl-copy + wtype Ctrl+V to paste Unicode text reliably on Wayland.

    This bypasses keycode layout issues that can make ``wtype <text>`` produce
    the wrong characters in some applications.
    """
    old_clip = ""
    try:
        result = subprocess.run(
            ["wl-paste", "--no-newline"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            old_clip = result.stdout
    except Exception as exc:
        logger.warning("Could not read Wayland clipboard: %s", exc)

    try:
        subprocess.run(["wl-copy", text], check=True, timeout=5)
        time.sleep(0.05)
        subprocess.run(["wtype", "-M", "ctrl", "v"], check=True, timeout=5)
        time.sleep(0.05)
    finally:
        try:
            if old_clip:
                subprocess.run(["wl-copy", old_clip], check=True, timeout=5)
        except Exception as exc:
            logger.warning("Could not restore Wayland clipboard: %s", exc)


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

    On Wayland, prefer ``wl-copy`` + ``wtype Ctrl+V`` so Unicode text is
    pasted correctly even when the active keyboard layout differs. Fall back
    to direct ``wtype <text>`` and then to the X11 ``pyperclip`` + ``Ctrl+V``
    path when the Wayland tools are unavailable.
    """
    if _wayland_available() and _wtype_available():
        if _wl_clipboard_available():
            try:
                _type_with_wtype_clipboard(text)
                return
            except Exception as exc:
                logger.warning("Wayland clipboard paste failed: %s; trying direct wtype", exc)
        try:
            _type_with_wtype(text)
            return
        except Exception as exc:
            logger.warning("wtype failed: %s; falling back to pynput", exc)
    _type_with_pynput(text)
