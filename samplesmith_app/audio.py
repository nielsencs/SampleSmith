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

    def play_audio(self, audio, sample_rate: int | None = None) -> None:
        _, sd, _ = self._deps()
        sd.play(audio, sample_rate or self.sample_rate)
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

    def write_audio(self, path: Path, audio, sample_rate: int | None = None) -> None:
        _, _, sf = self._deps()
        path.parent.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.lower()
        subtype = "PCM_24" if suffix in {".wav", ".flac"} else None
        sf.write(path, audio, sample_rate or self.sample_rate, subtype=subtype)

    def write_wav(self, path: Path, audio, sample_rate: int | None = None) -> None:
        self.write_audio(path, audio, sample_rate=sample_rate)

    def read_audio(self, path: Path):
        _, _, sf = self._deps()
        audio, sample_rate = sf.read(path, always_2d=False, dtype="float32")
        return audio, int(sample_rate)

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


def _load_audio_for_bridge(path: Path):
    try:
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Bridge WAV generation needs soundfile and numpy installed.") from exc

    audio, sample_rate = sf.read(path, always_2d=True, dtype="float32")
    if audio.size == 0:
        raise RuntimeError(f"Cannot generate bridge sample from empty WAV: {path}")
    return audio, sample_rate


def _pitch_shift_audio(audio, semitones: int):
    import numpy as np

    factor = 2 ** (semitones / 12.0)
    source_positions = np.arange(audio.shape[0], dtype=np.float64) * factor
    source_positions = source_positions[source_positions < audio.shape[0] - 1]
    if source_positions.size < 2:
        source_positions = np.array([0.0, max(0.0, float(audio.shape[0] - 1))])

    source_index = np.arange(audio.shape[0], dtype=np.float64)
    shifted_channels = [np.interp(source_positions, source_index, audio[:, channel]) for channel in range(audio.shape[1])]
    return np.stack(shifted_channels, axis=1).astype("float32")


def _match_channels(audio, channels: int):
    import numpy as np

    if audio.shape[1] == channels:
        return audio
    if audio.shape[1] == 1:
        return np.repeat(audio, channels, axis=1)
    return audio[:, :channels]


def _fade_edges(audio, sample_rate: int):
    import numpy as np

    fade_len = min(int(sample_rate * 0.005), audio.shape[0] // 4)
    if fade_len > 0:
        fade = np.linspace(0.0, 1.0, fade_len, dtype="float32")
        audio[:fade_len, :] *= fade[:, None]
        audio[-fade_len:, :] *= fade[::-1, None]
    return audio


def render_bridge_wav(
    low_source_path: Path,
    high_source_path: Path,
    target_path: Path,
    low_root_note: int,
    target_note: int,
    high_root_note: int,
) -> None:
    """Write a provisional bridge WAV blended from the two neighbouring samples.

    Both neighbours are pitch-shifted to the missing target note, then mixed by
    distance: notes nearer the lower recording contain more of the lower source,
    and notes nearer the higher recording contain more of the higher source.
    These files are explicitly provisional replacements for real recordings.
    """
    try:
        import numpy as np
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Bridge WAV generation needs soundfile and numpy installed.") from exc

    low_audio, low_rate = _load_audio_for_bridge(low_source_path)
    high_audio, high_rate = _load_audio_for_bridge(high_source_path)
    if low_rate != high_rate:
        raise RuntimeError(
            "Cannot blend bridge sample from WAVs with different sample rates: "
            f"{low_source_path.name} is {low_rate} Hz, {high_source_path.name} is {high_rate} Hz."
        )
    if not (low_root_note < target_note < high_root_note):
        raise RuntimeError("Bridge target note must sit between the two source root notes.")

    low_shifted = _pitch_shift_audio(low_audio, target_note - low_root_note)
    high_shifted = _pitch_shift_audio(high_audio, target_note - high_root_note)

    channels = max(low_shifted.shape[1], high_shifted.shape[1])
    low_shifted = _match_channels(low_shifted, channels)
    high_shifted = _match_channels(high_shifted, channels)

    length = max(low_shifted.shape[0], high_shifted.shape[0])
    low_padded = np.zeros((length, channels), dtype="float32")
    high_padded = np.zeros((length, channels), dtype="float32")
    low_padded[: low_shifted.shape[0], :] = low_shifted
    high_padded[: high_shifted.shape[0], :] = high_shifted

    high_weight = (target_note - low_root_note) / (high_root_note - low_root_note)
    low_weight = 1.0 - high_weight
    blended = (low_padded * low_weight + high_padded * high_weight).astype("float32")
    peak = float(np.max(np.abs(blended))) if blended.size else 0.0
    if peak > 0.98:
        blended *= 0.98 / peak
    blended = _fade_edges(blended, low_rate)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(target_path, blended, low_rate, subtype="PCM_24")


def render_retuned_bridge_wav(
    source_path: Path,
    target_path: Path,
    source_root_note: int,
    target_note: int,
) -> None:
    """Write a provisional bridge WAV from one neighbouring source recording.

    This covers one-sided or "imaginary" gaps where there is no recorded sample
    on both sides of the target note. The result is still deliberately marked as
    a provisional bridge so it is easy to replace with a real recording later.
    """
    try:
        import numpy as np
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Bridge WAV generation needs soundfile and numpy installed.") from exc

    audio, sample_rate = _load_audio_for_bridge(source_path)
    retuned = _pitch_shift_audio(audio, target_note - source_root_note)
    peak = float(np.max(np.abs(retuned))) if retuned.size else 0.0
    if peak > 0.98:
        retuned *= 0.98 / peak
    retuned = _fade_edges(retuned, sample_rate)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(target_path, retuned, sample_rate, subtype="PCM_24")
