"""Type the transcribed text into the currently focused input field."""

import logging
import os
import shutil
import subprocess
import time

try:
    import pyperclip
except Exception:  # pragma: no cover - optional fallback
    pyperclip = None

logger = logging.getLogger(__name__)
_controller = None


def _wayland_available() -> bool:
    return os.environ.get("WAYLAND_DISPLAY") is not None


def _wtype_available() -> bool:
    return shutil.which("wtype") is not None


def _wl_clipboard_available() -> bool:
    return shutil.which("wl-copy") is not None


def _type_with_wtype(text: str) -> None:
    """Use wtype to inject text under Wayland."""
    subprocess.run(["wtype", text], check=True, timeout=30)


def _type_with_wtype_clipboard(text: str) -> None:
    """Use wl-copy + wtype Ctrl+V to paste Unicode text reliably on Wayland.

    This bypasses keycode layout issues that can make ``wtype <text>`` produce
    the wrong characters in some applications. We intentionally do NOT restore
    the previous clipboard content, because doing so creates a second clipboard
    event and makes the new message appear one entry back in clipboard-manager
    history.
    """
    subprocess.run(["wl-copy", text], check=True, timeout=5)
    time.sleep(0.1)
    # Explicit key press/release so the compositor sees a real Ctrl+V combo.
    subprocess.run(
        ["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"],
        check=True,
        timeout=5,
    )
    time.sleep(0.2)


def _type_with_pynput(text: str) -> None:
    """Use the clipboard + Ctrl+V to preserve Unicode characters."""
    global _controller
    if _controller is None:
        from pynput.keyboard import Controller

        _controller = Controller()

    if pyperclip is None:
        _controller.type(text)
        return

    try:
        from pynput.keyboard import Key

        pyperclip.copy(text)
        time.sleep(0.05)
        with _controller.pressed(Key.ctrl):
            _controller.press("v")
            _controller.release("v")
        time.sleep(0.05)
    except Exception as exc:
        logger.warning("Clipboard paste failed: %s", exc)
        _controller.type(text)


def type_text(text: str) -> None:
    """Type the given text as if from a keyboard.

    On Wayland, prefer ``wl-copy`` + ``wtype Ctrl+V`` so Unicode text is
    pasted correctly even when the active keyboard layout differs. Fall back
    to direct ``wtype <text>`` and then to the X11 ``pyperclip`` + ``Ctrl+V``
    path when the Wayland tools are unavailable.
    """
    if _wayland_available() and _wtype_available():
        if _wl_clipboard_available():
            logger.info("Typing via Wayland clipboard paste")
            try:
                _type_with_wtype_clipboard(text)
                return
            except Exception as exc:
                logger.warning(
                    "Wayland clipboard paste failed: %s; trying direct wtype", exc
                )
        logger.info("Typing via direct wtype")
        try:
            _type_with_wtype(text)
            return
        except Exception as exc:
            logger.warning("wtype failed: %s; falling back to pynput", exc)
    logger.info("Typing via pynput fallback")
    _type_with_pynput(text)
