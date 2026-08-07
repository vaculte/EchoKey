"""System tray icon."""

import threading

import pystray
from PIL import Image, ImageDraw


def create_icon() -> Image.Image:
    """Build a simple colored circle icon."""
    image = Image.new("RGB", (64, 64), color="white")
    draw = ImageDraw.Draw(image)
    draw.ellipse([8, 8, 56, 56], fill="#ff4444")
    return image


class TrayIcon:
    """Minimal tray icon with an Exit menu item."""

    def __init__(self):
        self.icon = pystray.Icon(
            "EchoKey",
            create_icon(),
            "EchoKey",
            menu=pystray.Menu(pystray.MenuItem("Exit", self._exit)),
        )

    def _exit(self):
        self.icon.stop()

    def start(self) -> None:
        def _run():
            try:
                self.icon.run()
            except Exception as exc:
                print(f"Warning: system tray not available ({exc}). Continuing without tray.")

        threading.Thread(target=_run, daemon=True).start()
