"""Audio recording, playback, and WAV writing helpers for SampleSmith."""

from __future__ import annotations

import wave
from pathlib import Path

from .models import DEFAULT_SAMPLE_RATE, midi_to_freq

class AudioEngine:
    def __init__(self, sample_rate: int, trim_threshold_db: float, pre_roll_ms: float, post_roll_ms: float, normalise: bool) -> None:
        self.sample_rate = sample_rate
        self.trim_threshold_db = trim_threshold_db
        self.pre_roll_ms = pre_roll_ms
        self.post_roll_ms = post_roll_ms
        self.normalise = normalise

    def _deps(self):
        try:
            import numpy as np
            import sounddevice as sd
            import soundfile as sf
        except ImportError as exc:
            raise RuntimeError(
                "Missing audio dependencies. Install with: python -m pip install sounddevice soundfile numpy"
            ) from exc
        return np, sd, sf

    def play_tone(self, midi_note: int, seconds: float = 1.2) -> None:
        np, sd, _ = self._deps()
        freq = midi_to_freq(midi_note)
        t = np.linspace(0, seconds, int(self.sample_rate * seconds), endpoint=False)
        envelope = np.ones_like(t)
        fade_len = min(len(envelope) // 10, int(self.sample_rate * 0.05))
        if fade_len > 0:
            fade = np.linspace(0, 1, fade_len)
            envelope[:fade_len] *= fade
            envelope[-fade_len:] *= fade[::-1]
        audio = 0.18 * np.sin(2 * np.pi * freq * t) * envelope
        sd.play(audio, self.sample_rate)
        sd.wait()

    def record(self, seconds: float):
        np, sd, _ = self._deps()
        audio = sd.rec(int(seconds * self.sample_rate), samplerate=self.sample_rate, channels=1, dtype="float32")
        sd.wait()
        return np.asarray(audio[:, 0], dtype=np.float32)

    def trim(self, audio):
        np, _, _ = self._deps()
        if audio.size == 0:
            return audio
        peak = float(np.max(np.abs(audio)))
        if peak <= 0:
            return audio
        threshold = peak * (10 ** (self.trim_threshold_db / 20.0))
        active = np.flatnonzero(np.abs(audio) >= threshold)
        if active.size == 0:
            return audio
        pre = int(self.sample_rate * self.pre_roll_ms / 1000.0)
        post = int(self.sample_rate * self.post_roll_ms / 1000.0)
        start = max(0, int(active[0]) - pre)
        end = min(audio.size, int(active[-1]) + post)
        trimmed = audio[start:end]
        fade_len = min(int(self.sample_rate * 0.005), trimmed.size // 4)
        if fade_len > 0:
            fade = np.linspace(0, 1, fade_len)
            trimmed[:fade_len] *= fade
            trimmed[-fade_len:] *= fade[::-1]
        if self.normalise:
            peak = float(np.max(np.abs(trimmed))) if trimmed.size else 0.0
            if peak > 0:
                trimmed = (trimmed / peak * 0.9).astype(np.float32)
        return trimmed

    def write_wav(self, path: Path, audio) -> None:
        _, _, sf = self._deps()
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(path, audio, self.sample_rate, subtype="PCM_24")

    def detect_pitch(self, audio) -> float | None:
        np, _, _ = self._deps()
        try:
            import librosa  # type: ignore

            pitches, voiced_flags, _ = librosa.pyin(
                audio.astype(float),
                fmin=librosa.note_to_hz("C2"),
                fmax=librosa.note_to_hz("C7"),
                sr=self.sample_rate,
            )
            voiced = pitches[voiced_flags]
            if len(voiced):
                return float(np.nanmedian(voiced))
        except Exception:
            pass

        audio = audio.astype(float)
        audio = audio - np.mean(audio)
        peak = np.max(np.abs(audio)) if audio.size else 0
        if peak < 0.005:
            return None
        audio = audio / peak
        min_lag = int(self.sample_rate / 1200.0)
        max_lag = int(self.sample_rate / 60.0)
        corr = np.correlate(audio, audio, mode="full")[audio.size - 1 :]
        max_lag = min(max_lag, corr.size - 1)
        if max_lag <= min_lag:
            return None
        lag = int(np.argmax(corr[min_lag:max_lag])) + min_lag
        return self.sample_rate / lag if lag > 0 else None


def write_silent_wav(path: Path, sample_rate: int = DEFAULT_SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * int(sample_rate * 0.1))
