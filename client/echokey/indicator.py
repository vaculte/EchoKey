"""Animated recording overlay using tkinter."""

import logging
import tkinter as tk

logger = logging.getLogger(__name__)


class RecordingIndicator:
    """Small pulsing circle shown while recording."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.9)
        # Place the indicator near the top-left of the primary screen so it is visible.
        self.root.geometry("+100+100")

        self.canvas = tk.Canvas(
            self.root,
            width=80,
            height=80,
            highlightthickness=0,
            bg="#000000",
        )
        self.canvas.pack()
        self.circle = self.canvas.create_oval(
            10, 10, 70, 70, fill="#ff4444", outline=""
        )
        self._pulse()

    def show(self) -> None:
        logger.info("Showing recording indicator")
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.update_idletasks()

    def hide(self) -> None:
        logger.info("Hiding recording indicator")
        self.root.withdraw()

    def _pulse(self) -> None:
        current = self.canvas.itemcget(self.circle, "fill")
        next_color = "#ff8888" if current == "#ff4444" else "#ff4444"
        self.canvas.itemconfig(self.circle, fill=next_color)
        self.root.after(300, self._pulse)

    def run(self) -> None:
        self.root.mainloop()
