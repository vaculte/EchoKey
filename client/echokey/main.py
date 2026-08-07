"""Entrypoint that ties together hotkey, indicator, audio, API, and tray."""

import os
import tempfile
import threading
from queue import Empty, Queue

from echokey.api import EchoKeyClient
from echokey.audio import AudioRecorder
from echokey.config import settings
from echokey.hotkey import HotkeyListener
from echokey.indicator import RecordingIndicator
from echokey.input import type_text
from echokey.tray import TrayIcon


class App:
    def __init__(self):
        self.queue: Queue = Queue()
        self.recorder = AudioRecorder()
        self.client = EchoKeyClient()
        self.indicator = RecordingIndicator()
        self.listener = HotkeyListener(self.queue)
        self.tray = TrayIcon()
        self.recording = False

    def _poll_queue(self):
        """Read events from the hotkey thread and update the UI."""
        try:
            while True:
                event = self.queue.get_nowait()
                if event == "start":
                    self._start_recording()
                elif event == "stop":
                    self._stop_recording()
        except Empty:
            pass
        self.indicator.root.after(50, self._poll_queue)

    def _start_recording(self):
        if self.recording:
            return
        self.recording = True
        self.recorder.start()
        self.indicator.show()

    def _stop_recording(self):
        if not self.recording:
            return
        self.recording = False
        self.recorder.stop()
        self.indicator.hide()

        fd, path = tempfile.mkstemp(suffix=".wav", prefix="echokey_")
        os.close(fd)
        self.recorder.save(path)

        threading.Thread(target=self._process, args=(path,), daemon=True).start()

    def _process(self, path: str):
        try:
            recording_id = self.client.upload(path)
            transcript = self.client.poll(recording_id)
            if transcript:
                type_text(transcript)
        except Exception as exc:
            print(f"EchoKey processing error: {exc}")
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def run(self):
        self.listener.start()
        self.tray.start()
        self.indicator.root.after(50, self._poll_queue)
        self.indicator.run()


def main():
    print(f"EchoKey client started. Hold {settings.HOTKEY} to record.")
    App().run()


if __name__ == "__main__":
    main()
