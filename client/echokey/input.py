"""Type the transcribed text into the currently focused input field."""

from pynput.keyboard import Controller


_controller = Controller()


def type_text(text: str) -> None:
    """Type the given text as if from a keyboard."""
    _controller.type(text)
