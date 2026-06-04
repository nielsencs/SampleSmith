#!/usr/bin/env python3
"""
sampler_capture.py - guided sample capture for Decent Sampler instruments.

MVP goals:
- Pitched mode: detect lowest/highest played notes, guide note-by-note recording,
  trim/normalise WAVs, and generate a Decent Sampler .dspreset.
- Unpitched/pad mode: record labelled sounds onto consecutive MIDI pads and generate
  a Decent Sampler .dspreset.

Audio dependencies are deliberately small and installable with pip:
  python -m pip install sounddevice soundfile numpy
Optional pitch detection:
  python -m pip install librosa

If librosa is unavailable, pitch detection falls back to a simple autocorrelation detector.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import time
import wave
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - dependency check
    raise SystemExit("Missing dependency: numpy. Install with: python -m pip install numpy") from exc

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - runtime dependency
    sd = None

try:
    import soundfile as sf
except ImportError:  # pragma: no cover - runtime dependency
    sf = None

NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTE_ALIASES = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"}
A4_MIDI = 69
A4_HZ = 440.0
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_REFERENCE_SECONDS = 1.2
DEFAULT_RECORD_SECONDS = 4.0
DEFAULT_PAD_START_NOTE = 36  # C2 in MIDI, common-ish drum/pad area


@dataclass(frozen=True)
class CaptureConfig:
    instrument_name: str
    output_dir: Path
    sample_rate: int
    record_seconds: float
    trim_threshold_db: float
    pre_roll_ms: float
    post_roll_ms: float
    normalise: bool
    dry_run: bool


@dataclass(frozen=True)
class SampleInfo:
    path: Path
    root_note: int
    lo_note: int
    hi_note: int
    label: str


def slugify(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^A-Za-z0-9._ -]+", "", value)
    value = re.sub(r"[\s-]+", "_", value)
    return value.strip("_") or "Instrument"


def midi_to_freq(midi_note: int) -> float:
    return A4_HZ * (2 ** ((midi_note - A4_MIDI) / 12))


def freq_to_midi(freq: float) -> int:
    return int(round(A4_MIDI + 12 * math.log2(freq / A4_HZ)))


def midi_to_name(midi_note: int) -> str:
    name = NOTE_NAMES_SHARP[midi_note % 12]
    octave = (midi_note // 12) - 1
    return f"{name}{octave}"


def name_to_midi(note_name: str) -> int:
    match = re.fullmatch(r"\s*([A-Ga-g])([#bB]?)(-?\d+)\s*", note_name)
    if not match:
        raise ValueError(f"Invalid note name: {note_name!r}")
    base, accidental, octave_text = match.groups()
    note = (base.upper() + accidental.upper()).replace("♯", "#").replace("♭", "B")
    note = NOTE_ALIASES.get(note, note)
    if note not in NOTE_NAMES_SHARP:
        raise ValueError(f"Invalid note name: {note_name!r}")
    octave = int(octave_text)
    return (octave + 1) * 12 + NOTE_NAMES_SHARP.index(note)


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer if answer else (default or "")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    default_text = "Y/n" if default else "y/N"
    while True:
        answer = input(f"{prompt} [{default_text}]: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer y or n.")


def ask_float(prompt: str, default: float) -> float:
    while True:
        answer = ask(prompt, str(default))
        try:
            return float(answer)
        except ValueError:
            print("Please enter a number.")


def require_audio(config: CaptureConfig) -> None:
    if config.dry_run:
        return
    missing = []
    if sd is None:
        missing.append("sounddevice")
    if sf is None:
        missing.append("soundfile")
    if missing:
        raise SystemExit(
            "Missing audio dependencies: "
            + ", ".join(missing)
            + ". Install with: python -m pip install sounddevice soundfile numpy"
        )


def play_tone(midi_note: int, sample_rate: int, seconds: float = DEFAULT_REFERENCE_SECONDS, dry_run: bool = False) -> None:
    note_name = midi_to_name(midi_note)
    freq = midi_to_freq(midi_note)
    print(f"Reference: {note_name} ({freq:.1f} Hz)")
    if dry_run:
        return
    assert sd is not None
    t = np.linspace(0, seconds, int(sample_rate * seconds), endpoint=False)
    envelope = np.ones_like(t)
    fade_len = min(len(envelope) // 10, int(sample_rate * 0.05))
    if fade_len > 0:
        fade = np.linspace(0, 1, fade_len)
        envelope[:fade_len] *= fade
        envelope[-fade_len:] *= fade[::-1]
    audio = 0.18 * np.sin(2 * np.pi * freq * t) * envelope
    sd.play(audio, sample_rate)
    sd.wait()


def countdown(seconds: int = 3) -> None:
    for value in range(seconds, 0, -1):
        print(value)
        time.sleep(1)


def record_audio(seconds: float, sample_rate: int, dry_run: bool = False) -> np.ndarray:
    if dry_run:
        length = int(seconds * sample_rate)
        return np.zeros(length, dtype=np.float32)
    assert sd is not None
    print(f"Recording for {seconds:.1f}s...")
    audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
    sd.wait()
    return np.asarray(audio[:, 0], dtype=np.float32)


def audio_to_db_threshold(audio: np.ndarray, threshold_db: float) -> float:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak <= 0:
        return 0.0
    return peak * (10 ** (threshold_db / 20.0))


def trim_audio(
    audio: np.ndarray,
    sample_rate: int,
    threshold_db: float,
    pre_roll_ms: float,
    post_roll_ms: float,
) -> np.ndarray:
    if audio.size == 0:
        return audio
    threshold = audio_to_db_threshold(audio, threshold_db)
    if threshold <= 0:
        return audio
    active = np.flatnonzero(np.abs(audio) >= threshold)
    if active.size == 0:
        return audio
    pre = int(sample_rate * pre_roll_ms / 1000.0)
    post = int(sample_rate * post_roll_ms / 1000.0)
    start = max(0, int(active[0]) - pre)
    end = min(audio.size, int(active[-1]) + post)
    trimmed = audio[start:end]
    fade_len = min(int(sample_rate * 0.005), trimmed.size // 4)
    if fade_len > 0:
        fade = np.linspace(0, 1, fade_len)
        trimmed[:fade_len] *= fade
        trimmed[-fade_len:] *= fade[::-1]
    return trimmed


def normalise_audio(audio: np.ndarray, target_peak: float = 0.9) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak <= 0:
        return audio
    return (audio / peak * target_peak).astype(np.float32)


def write_wav(path: Path, audio: np.ndarray, sample_rate: int, dry_run: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        # Write a tiny valid silent file, so preset generation can still be inspected.
        audio = np.zeros(int(sample_rate * 0.1), dtype=np.float32)
    if sf is not None:
        sf.write(path, audio, sample_rate, subtype="PCM_24")
        return
    # Fallback writer for dry-run or environments without soundfile.
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def detect_pitch_autocorrelation(audio: np.ndarray, sample_rate: int) -> float | None:
    if audio.size == 0:
        return None
    audio = audio.astype(np.float64)
    audio = audio - np.mean(audio)
    peak = np.max(np.abs(audio))
    if peak < 0.005:
        return None
    audio = audio / peak
    min_freq = 60.0
    max_freq = 1200.0
    min_lag = int(sample_rate / max_freq)
    max_lag = int(sample_rate / min_freq)
    corr = np.correlate(audio, audio, mode="full")[audio.size - 1 :]
    if max_lag >= corr.size:
        max_lag = corr.size - 1
    if max_lag <= min_lag:
        return None
    window = corr[min_lag:max_lag]
    lag = int(np.argmax(window)) + min_lag
    if lag <= 0:
        return None
    return sample_rate / lag


def detect_pitch(audio: np.ndarray, sample_rate: int) -> float | None:
    try:
        import librosa  # type: ignore

        pitches, voiced_flags, _ = librosa.pyin(
            audio.astype(float),
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sample_rate,
        )
        voiced = pitches[voiced_flags]
        if len(voiced):
            return float(np.nanmedian(voiced))
    except Exception:
        pass
    return detect_pitch_autocorrelation(audio, sample_rate)


def confirm_detected_note(label: str, config: CaptureConfig) -> int:
    require_audio(config)
    while True:
        print(f"\nPlay/sing your {label} usable note after the countdown.")
        input("Press Enter when ready...")
        countdown()
        audio = record_audio(2.5, config.sample_rate, config.dry_run)
        freq = detect_pitch(audio, config.sample_rate)
        if freq is None:
            print("I could not detect a clear pitch.")
            manual = ask("Type note manually, or press Enter to retry")
            if manual:
                return name_to_midi(manual)
            continue
        midi = freq_to_midi(freq)
        note_name = midi_to_name(midi)
        print(f"I think that was {note_name} ({freq:.1f} Hz).")
        if ask_yes_no("Accept this note?", True):
            return midi
        manual = ask("Type corrected note, or press Enter to retry")
        if manual:
            return name_to_midi(manual)


def note_range(low: int, high: int, step: int) -> list[int]:
    if high < low:
        low, high = high, low
    return list(range(low, high + 1, step))


def capture_sample(path: Path, config: CaptureConfig, reference_note: int | None = None) -> None:
    require_audio(config)
    if reference_note is not None:
        play_tone(reference_note, config.sample_rate, dry_run=config.dry_run)
    input("Press Enter when ready to record...")
    countdown()
    audio = record_audio(config.record_seconds, config.sample_rate, config.dry_run)
    audio = trim_audio(audio, config.sample_rate, config.trim_threshold_db, config.pre_roll_ms, config.post_roll_ms)
    if config.normalise:
        audio = normalise_audio(audio)
    write_wav(path, audio, config.sample_rate, config.dry_run)
    print(f"Saved {path}")


def sample_path(config: CaptureConfig, label: str) -> Path:
    return config.output_dir / "Samples" / f"{slugify(config.instrument_name)}_{label}.wav"


def build_key_ranges(notes: list[int]) -> list[tuple[int, int, int]]:
    ranges: list[tuple[int, int, int]] = []
    for index, root in enumerate(notes):
        if len(notes) == 1:
            lo, hi = 0, 127
        else:
            if index == 0:
                lo = 0
            else:
                lo = int(math.floor((notes[index - 1] + root) / 2)) + 1
            if index == len(notes) - 1:
                hi = 127
            else:
                hi = int(math.floor((root + notes[index + 1]) / 2))
        ranges.append((root, lo, hi))
    return ranges


def generate_dspreset(config: CaptureConfig, samples: Iterable[SampleInfo]) -> Path:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    root = ET.Element("DecentSampler")
    groups = ET.SubElement(root, "groups")
    group = ET.SubElement(groups, "group", {"attack": "0.01", "release": "0.8"})
    for sample in samples:
        rel_path = sample.path.relative_to(config.output_dir).as_posix()
        ET.SubElement(
            group,
            "sample",
            {
                "path": rel_path,
                "rootNote": str(sample.root_note),
                "loNote": str(sample.lo_note),
                "hiNote": str(sample.hi_note),
                "loVel": "1",
                "hiVel": "127",
            },
        )
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    preset_path = config.output_dir / f"{slugify(config.instrument_name)}.dspreset"
    tree.write(preset_path, encoding="utf-8", xml_declaration=True)
    print(f"Wrote {preset_path}")
    return preset_path


def pitched_mode(config: CaptureConfig) -> None:
    low = confirm_detected_note("lowest", config)
    high = confirm_detected_note("highest", config)
    step_answer = ask("Capture every how many semitones?", "1")
    step = max(1, int(step_answer))
    notes = note_range(low, high, step)
    print("\nCapture notes:", ", ".join(midi_to_name(note) for note in notes))
    if not ask_yes_no("Continue?", True):
        return
    root_ranges = build_key_ranges(notes)
    samples: list[SampleInfo] = []
    for root, lo, hi in root_ranges:
        note_name = midi_to_name(root)
        path = sample_path(config, note_name.replace("#", "sharp"))
        print(f"\n=== {note_name} ===")
        capture_sample(path, config, reference_note=root)
        samples.append(SampleInfo(path=path, root_note=root, lo_note=lo, hi_note=hi, label=note_name))
    generate_dspreset(config, samples)


def unpitched_mode(config: CaptureConfig) -> None:
    start_text = ask("Starting MIDI note for pads", midi_to_name(DEFAULT_PAD_START_NOTE))
    try:
        start_note = int(start_text)
    except ValueError:
        start_note = name_to_midi(start_text)
    samples: list[SampleInfo] = []
    index = 0
    while True:
        label = ask("Pad label (blank to finish)")
        if not label:
            break
        takes = int(ask("How many takes for this pad?", "1"))
        for take in range(1, takes + 1):
            midi_note = start_note + index
            take_label = f"{slugify(label)}_{take:02d}" if takes > 1 else slugify(label)
            path = sample_path(config, f"pad_{midi_to_name(midi_note).replace('#', 'sharp')}_{take_label}")
            print(f"\n=== Pad {midi_to_name(midi_note)}: {label} take {take} ===")
            capture_sample(path, config, reference_note=None)
            samples.append(SampleInfo(path=path, root_note=midi_note, lo_note=midi_note, hi_note=midi_note, label=label))
            index += 1
        if not ask_yes_no("Record another pad/sound?", True):
            break
    if samples:
        generate_dspreset(config, samples)
    else:
        print("No samples recorded.")


def build_config(args: argparse.Namespace) -> CaptureConfig:
    instrument_name = args.name or ask("Instrument/kit name", "SampleInstrument")
    output_base = Path(args.output or "captured-samplers")
    output_dir = output_base / slugify(instrument_name)
    return CaptureConfig(
        instrument_name=instrument_name,
        output_dir=output_dir,
        sample_rate=args.sample_rate,
        record_seconds=args.record_seconds,
        trim_threshold_db=args.trim_threshold_db,
        pre_roll_ms=args.pre_roll_ms,
        post_roll_ms=args.post_roll_ms,
        normalise=not args.no_normalise,
        dry_run=args.dry_run,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guided Decent Sampler capture helper")
    parser.add_argument("--mode", choices=["pitched", "pads"], help="Capture mode. If omitted, ask interactively.")
    parser.add_argument("--name", help="Instrument/kit name")
    parser.add_argument("--output", help="Output folder", default="captured-samplers")
    parser.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE)
    parser.add_argument("--record-seconds", type=float, default=DEFAULT_RECORD_SECONDS)
    parser.add_argument("--trim-threshold-db", type=float, default=-45.0, help="Trim below this many dB relative to peak")
    parser.add_argument("--pre-roll-ms", type=float, default=40.0)
    parser.add_argument("--post-roll-ms", type=float, default=180.0)
    parser.add_argument("--no-normalise", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Create silent files without audio hardware, for testing")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    config = build_config(args)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    mode = args.mode
    if mode is None:
        print("Modes:")
        print("  1. pitched - sing/play lowest and highest notes, then capture note range")
        print("  2. pads    - unpitched sounds mapped to pads")
        choice = ask("Choose mode", "pitched").lower()
        mode = "pads" if choice in {"2", "pad", "pads", "unpitched"} else "pitched"
    if mode == "pitched":
        pitched_mode(config)
    else:
        unpitched_mode(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
