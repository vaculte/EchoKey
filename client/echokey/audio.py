"""Record audio from the microphone into a WAV file."""

import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # int16


class AudioRecorder:
    """Callback-based recorder that produces 16 kHz mono 16-bit WAV."""

    def __init__(self):
        self.frames: list[np.ndarray] = []
        self.stream: sd.RawInputStream | None = None

    def _callback(self, indata, frames, time, status):
        if status:
            print(f"audio status: {status}")
        self.frames.append(indata.copy())

    def start(self) -> None:
        self.frames = []
        self.stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=1024,
            callback=self._callback,
        )
        self.stream.start()

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
            data = np.concatenate(self.frames, axis=0)

        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(data.tobytes())
