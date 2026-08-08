"""Entrypoint that ties together hotkey, indicator, audio, API, and tray."""

import logging
import logging.handlers
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from queue import Empty, Queue

from echokey.api import EchoKeyClient
from echokey.audio import AudioRecorder
from echokey.config import settings
from echokey.hotkey import create_listener
from echokey.indicator import RecordingIndicator
from echokey.input import type_text
from echokey.tray import TrayIcon


def _setup_logging() -> None:
    log_dir = Path.home() / ".local" / "share" / "echokey"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "client.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=3
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("%(levelname)s %(name)s %(message)s")
    )

    logging.basicConfig(
        level=logging.INFO,
        handlers=[console_handler, file_handler],
        force=True,
    )
    logging.getLogger("pynput").setLevel(logging.WARNING)
    logging.getLogger("sounddevice").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


class App:
    def __init__(self):
        self.queue: Queue = Queue()
        self.recorder = AudioRecorder()
        self.client = EchoKeyClient()
        self.indicator = RecordingIndicator()
        self.listener = create_listener(self.queue)
        self.tray = TrayIcon()
        self.recording = False
        self._stop_after_id = None

    def _poll_queue(self):
        """Read events from the hotkey thread and update the UI."""
        try:
            while True:
                event = self.queue.get_nowait()
                if event == "start":
                    if self._stop_after_id is not None:
                        self.indicator.root.after_cancel(self._stop_after_id)
                        self._stop_after_id = None
                        logger.info("Hotkey bounce cancelled scheduled stop")
                    if not self.recording:
                        self._start_recording()
                elif event == "stop":
                    if self.recording and self._stop_after_id is None:
                        self._stop_after_id = self.indicator.root.after(
                            200, self._stop_recording
                        )
                        logger.info("Release scheduled stop in 200ms")
        except Empty:
            pass
        self.indicator.root.after(50, self._poll_queue)

    def _start_recording(self):
        if self.recording:
            return
        self.recording = True
        self._record_start_ts = time.perf_counter()
        logger.info("Recording started")
        self.recorder.start()
        self.indicator.show()

    def _stop_recording(self):
        self._stop_after_id = None
        if not self.recording:
            return
        self.recording = False
        duration = time.perf_counter() - getattr(self, "_record_start_ts", 0)
        logger.info("Recording stopped (hotkey held for %.3fs)", duration)
        self.recorder.stop()
        self.indicator.hide()

        fd, path = tempfile.mkstemp(suffix=".wav", prefix="echokey_")
        os.close(fd)
        self.recorder.save(path)

        threading.Thread(target=self._process, args=(path,), daemon=True).start()

    def _process(self, path: str):
        try:
            logger.info("Uploading audio for transcription")
            recording_id = self.client.upload(path)
            logger.info("Polling transcription result")
            transcript = self.client.poll(recording_id)
            if transcript:
                logger.info("Typing transcript: %s", transcript)
                type_text(transcript)
            else:
                logger.warning("No transcript returned")
        except Exception as exc:
            logger.error("EchoKey processing error: %s", exc)
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
    _setup_logging()
    logger.info("EchoKey client started. Press %s to record.", settings.HOTKEY)
    App().run()


if __name__ == "__main__":
    main()
