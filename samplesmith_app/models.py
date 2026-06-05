"""Core data models and note/mapping helpers for SampleSmith."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTE_ALIASES = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"}
A4_MIDI = 69
A4_HZ = 440.0
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_PAD_START_NOTE = 36  # C2

DEFAULT_SAMPLE_RATE = 44100
DEFAULT_PAD_START_NOTE = 36  # C2


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._ -]+", "", value.strip())
    value = re.sub(r"[\s-]+", "_", value)
    return value.strip("_") or "SampleSmithInstrument"


def midi_to_freq(midi_note: int) -> float:
    return A4_HZ * (2 ** ((midi_note - A4_MIDI) / 12))


def freq_to_midi(freq: float) -> int:
    return int(round(A4_MIDI + 12 * math.log2(freq / A4_HZ)))


def midi_to_name(midi_note: int) -> str:
    return f"{NOTE_NAMES_SHARP[midi_note % 12]}{(midi_note // 12) - 1}"


def name_to_midi(note_name: str) -> int:
    match = re.fullmatch(r"\s*([A-Ga-g])([#bB]?)(-?\d+)\s*", note_name)
    if not match:
        raise ValueError(f"Invalid note name: {note_name!r}")
    base, accidental, octave_text = match.groups()
    note = (base.upper() + accidental.upper()).replace("♯", "#").replace("♭", "B")
    note = NOTE_ALIASES.get(note, note)
    if note not in NOTE_NAMES_SHARP:
        raise ValueError(f"Invalid note name: {note_name!r}")
    return (int(octave_text) + 1) * 12 + NOTE_NAMES_SHARP.index(note)


def note_range(low: int, high: int, step: int) -> list[int]:
    if high < low:
        low, high = high, low
    return list(range(low, high + 1, max(1, step)))


def build_key_ranges(notes: list[int]) -> list[tuple[int, int, int]]:
    ranges: list[tuple[int, int, int]] = []
    for index, root in enumerate(notes):
        if len(notes) == 1:
            lo, hi = 0, 127
        else:
            lo = 0 if index == 0 else int(math.floor((notes[index - 1] + root) / 2)) + 1
            hi = 127 if index == len(notes) - 1 else int(math.floor((root + notes[index + 1]) / 2))
        ranges.append((root, lo, hi))
    return ranges


def build_overlapping_key_ranges(notes: list[int]) -> list[tuple[int, int, int]]:
    """Map recorded sample roots with overlap between neighbouring home notes.

    Example: roots C3/C4 become C3 -> MIDI 0-60 and C4 -> MIDI 48-127.
    The 48-60 overlap is a layered blend zone for now; true key-based crossfades
    can be added later if/when we add Decent Sampler fade parameters.
    """
    sorted_notes = sorted(notes)
    ranges: list[tuple[int, int, int]] = []
    for index, root in enumerate(sorted_notes):
        lo = 0 if index == 0 else sorted_notes[index - 1]
        hi = 127 if index == len(sorted_notes) - 1 else sorted_notes[index + 1]
        ranges.append((root, lo, hi))
    return ranges


def mapping_text(lo_note: int, hi_note: int) -> str:
    return f"MIDI {lo_note}–{hi_note} ({midi_to_name(lo_note)} to {midi_to_name(hi_note)})"


def exported_root_text(root_note: int, root_note_offset: int) -> str:
    exported = clamp_midi_note(root_note + root_note_offset)
    return f"MIDI {exported} ({midi_to_name(exported)})"


@dataclass
class SampleInfo:
    path: Path
    root_note: int
    lo_note: int
    hi_note: int
    label: str
    mode: str = "pitched"
    loop_enabled: bool | None = None
    loop_start: int | None = None
    loop_end: int | None = None
    loop_crossfade: float | None = None
    loop_crossfade_mode: str | None = None
    generated: bool = False
    provisional: bool = False
    source_roots: list[int] | None = None
    source_paths: list[Path] | None = None

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "path": str(self.path),
            "root_note": self.root_note,
            "lo_note": self.lo_note,
            "hi_note": self.hi_note,
            "label": self.label,
            "mode": self.mode,
        }
        if self.loop_enabled is not None:
            data["loop_enabled"] = self.loop_enabled
        if self.loop_start is not None:
            data["loop_start"] = self.loop_start
        if self.loop_end is not None:
            data["loop_end"] = self.loop_end
        if self.loop_crossfade is not None:
            data["loop_crossfade"] = self.loop_crossfade
        if self.loop_crossfade_mode is not None:
            data["loop_crossfade_mode"] = self.loop_crossfade_mode
        if self.generated:
            data["generated"] = True
        if self.provisional:
            data["provisional"] = True
        if self.source_roots:
            data["source_roots"] = self.source_roots
        if self.source_paths:
            data["source_paths"] = [str(path) for path in self.source_paths]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SampleInfo":
        loop_crossfade = None
        if data.get("loop_crossfade") is not None:
            try:
                loop_crossfade = clamp_float(float(data.get("loop_crossfade", 0.0)), 0.0, 60000.0)
            except (TypeError, ValueError):
                loop_crossfade = None
        return cls(
            path=Path(str(data["path"])),
            root_note=int(data["root_note"]),
            lo_note=int(data["lo_note"]),
            hi_note=int(data["hi_note"]),
            label=str(data.get("label", "")),
            mode=str(data.get("mode", "pitched")),
            loop_enabled=None if data.get("loop_enabled") is None else bool(data.get("loop_enabled")),
            loop_start=optional_non_negative_int(data.get("loop_start")),
            loop_end=optional_non_negative_int(data.get("loop_end")),
            loop_crossfade=loop_crossfade,
            loop_crossfade_mode=None if data.get("loop_crossfade_mode") is None else str(data.get("loop_crossfade_mode")),
            generated=bool(data.get("generated", False)),
            provisional=bool(data.get("provisional", False)),
            source_roots=[int(root) for root in data.get("source_roots", [])] if data.get("source_roots") else None,
            source_paths=[Path(str(path)) for path in data.get("source_paths", [])] if data.get("source_paths") else None,
        )

def clamp_midi_note(midi_note: int) -> int:
    return max(0, min(127, midi_note))


def clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def optional_non_negative_int(value: int | float | str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def valid_loop_points(loop_start: int | None, loop_end: int | None) -> tuple[int | None, int | None]:
    if loop_start is None or loop_end is None or loop_end <= loop_start:
        return None, None
    return loop_start, loop_end
