"""Record audio from the microphone into a WAV file."""

import logging
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from echokey.config import settings

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # int16

logger = logging.getLogger(__name__)


def _resolve_device():
    """Resolve the configured input device to a sounddevice device id."""
    if not settings.INPUT_DEVICE:
        return None
    candidate = settings.INPUT_DEVICE.strip()
    # Try integer index first.
    try:
        return int(candidate)
    except ValueError:
        pass
    # Try matching by name substring.
    devices = sd.query_devices()
    for idx, device in enumerate(devices):
        if device.get("max_input_channels", 0) > 0 and candidate.lower() in device.get("name", "").lower():
            logger.info("Selected input device %s: %s", idx, device["name"])
            return idx
    logger.warning("INPUT_DEVICE '%s' not found; using default", candidate)
    return None


class AudioRecorder:
    """Callback-based recorder that produces 16 kHz mono 16-bit WAV."""

    def __init__(self):
        self.frames: list[np.ndarray] = []
        self.stream: sd.InputStream | None = None

    def _callback(self, indata, frames, time, status):
        if status:
            logger.warning("audio status: %s", status)
        # sd.InputStream already delivers a numpy int16 array.
        self.frames.append(indata.copy())

    def start(self) -> None:
        self.frames = []
        device = _resolve_device()
        self.stream = sd.InputStream(
            device=device,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=1024,
            callback=self._callback,
        )
        self.stream.start()
        logger.info("Audio stream started on device: %s", self.stream.device)

    def stop(self) -> None:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not self.frames:
            data = np.array([], dtype=np.int16)
        else:
            data = np.concatenate(self.frames, axis=0).flatten()

        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(data.tobytes())
