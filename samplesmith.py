#!/usr/bin/env python3
"""Backward-compatible launcher for SampleSmith.

The application implementation lives in :mod:`samplesmith_app`.
"""

from samplesmith_app.app import SampleSmithApp, main
from samplesmith_app.audio import AudioEngine
from samplesmith_app.dspreset import generate_dspreset
from samplesmith_app.looping import read_wav_smpl_loop_points
from samplesmith_app.models import (
    A4_HZ,
    A4_MIDI,
    DEFAULT_SAMPLE_RATE,
    NOTE_ALIASES,
    NOTE_NAMES_SHARP,
    SampleInfo,
    build_key_ranges,
    build_overlapping_key_ranges,
    clamp_float,
    clamp_midi_note,
    exported_root_text,
    freq_to_midi,
    mapping_text,
    midi_to_freq,
    midi_to_name,
    name_to_midi,
    note_range,
    optional_non_negative_int,
    slugify,
    valid_loop_points,
)

__all__ = [
    "A4_HZ",
    "A4_MIDI",
    "AudioEngine",
    "DEFAULT_SAMPLE_RATE",
    "NOTE_ALIASES",
    "NOTE_NAMES_SHARP",
    "SampleInfo",
    "SampleSmithApp",
    "build_key_ranges",
    "build_overlapping_key_ranges",
    "clamp_float",
    "clamp_midi_note",
    "exported_root_text",
    "freq_to_midi",
    "generate_dspreset",
    "main",
    "mapping_text",
    "midi_to_freq",
    "midi_to_name",
    "name_to_midi",
    "note_range",
    "optional_non_negative_int",
    "read_wav_smpl_loop_points",
    "slugify",
    "valid_loop_points",
]


if __name__ == "__main__":
    main()
