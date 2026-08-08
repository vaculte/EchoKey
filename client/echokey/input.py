"""Type the transcribed text into the currently focused input field."""

import logging
import time

from pynput.keyboard import Controller, Key

try:
    import pyperclip
except Exception:  # pragma: no cover - optional fallback
    pyperclip = None

logger = logging.getLogger(__name__)
_controller = Controller()


def type_text(text: str) -> None:
    """Type the given text as if from a keyboard.

    Uses the clipboard + Ctrl+V to preserve Unicode characters and avoid
    keyboard layout issues. Falls back to pynput.Controller.type if the
    clipboard path is unavailable.
    """
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
