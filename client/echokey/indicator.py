"""Animated recording overlay using tkinter."""

import tkinter as tk


class RecordingIndicator:
    """Small pulsing circle shown while recording."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.9)

        self.canvas = tk.Canvas(
            self.root,
            width=80,
            height=80,
            highlightthickness=0,
            bg="",
        )
        self.canvas.pack()
        self.circle = self.canvas.create_oval(
            10, 10, 70, 70, fill="#ff4444", outline=""
        )
        self._pulse()

    def show(self) -> None:
        self.root.deiconify()

    def hide(self) -> None:
        self.root.withdraw()

    def _pulse(self) -> None:
        current = self.canvas.itemcget(self.circle, "fill")
        next_color = "#ff8888" if current == "#ff4444" else "#ff4444"
        self.canvas.itemconfig(self.circle, fill=next_color)
        self.root.after(300, self._pulse)

    def run(self) -> None:
        self.root.mainloop()
