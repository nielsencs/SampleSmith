#!/usr/bin/env python3
"""Build a local DecentSampler effects listening test pack for SampleSmith.

The generated pack is intentionally not committed. It creates one shared
Samples/ folder plus one deliberately exaggerated preset per supported Decent
Sampler effect/filter so a human can open them locally and listen for whether
each exported effect behaves as expected inside DecentSampler.
"""

from __future__ import annotations

import argparse
import math
import shutil
import struct
import sys
import wave
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samplesmith_app.dspreset import generate_dspreset
from samplesmith_app.models import SampleInfo

SAMPLE_RATE = 44_100
ROOT_NOTE = 72  # DecentSampler C4 / middle C.


def _write_pcm16_wav(path: Path, frames: list[float], sample_rate: int = SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        payload = bytearray()
        for value in frames:
            clipped = max(-1.0, min(1.0, value))
            payload.extend(struct.pack("<h", int(clipped * 32767)))
        handle.writeframes(bytes(payload))


def _make_source_sample(path: Path) -> None:
    """Write a bright sustained sample that makes most effects easy to hear."""
    seconds = 3.2
    total = int(SAMPLE_RATE * seconds)
    frames: list[float] = []
    for index in range(total):
        t = index / SAMPLE_RATE
        # A harmonically rich but stable test tone: fundamental plus upper partials
        # and a tiny slow tremolo so time/modulation effects are obvious.
        tremolo = 0.88 + 0.12 * math.sin(2 * math.pi * 2.0 * t)
        value = (
            0.46 * math.sin(2 * math.pi * 261.6256 * t)
            + 0.24 * math.sin(2 * math.pi * 523.2511 * t)
            + 0.14 * math.sin(2 * math.pi * 784.0 * t)
            + 0.09 * math.sin(2 * math.pi * 1318.51 * t)
            + 0.04 * math.sin(2 * math.pi * 3135.96 * t)
        ) * tremolo
        attack = min(1.0, index / (SAMPLE_RATE * 0.025))
        release_start = int(total - SAMPLE_RATE * 0.25)
        if index > release_start:
            release = max(0.0, (total - index) / (total - release_start))
        else:
            release = 1.0
        frames.append(value * attack * release * 0.75)
    _write_pcm16_wav(path, frames)


def _make_ir_sample(path: Path) -> None:
    """Write a tiny impulse response for convolution tests."""
    total = int(SAMPLE_RATE * 0.65)
    frames = [0.0 for _ in range(total)]
    taps = [
        (0, 0.9),
        (int(SAMPLE_RATE * 0.035), 0.45),
        (int(SAMPLE_RATE * 0.083), -0.35),
        (int(SAMPLE_RATE * 0.145), 0.24),
        (int(SAMPLE_RATE * 0.260), -0.16),
        (int(SAMPLE_RATE * 0.410), 0.09),
    ]
    for frame, value in taps:
        if frame < total:
            frames[frame] = value
    _write_pcm16_wav(path, frames)


def _sample_for(output_dir: Path) -> SampleInfo:
    sample_path = output_dir / "Samples" / "effects_test_C4.wav"
    if not sample_path.exists():
        _make_source_sample(sample_path)
    return SampleInfo(path=sample_path, root_note=ROOT_NOTE, lo_note=0, hi_note=127, label="C4")


def _write_notes(path: Path, rows: list[tuple[str, str, str]]) -> None:
    lines = [
        "# SampleSmith DecentSampler effects listening test pack",
        "",
        "Open each `.dspreset` in this folder in DecentSampler and play around the on-screen C4 key.",
        "All presets share `Samples/effects_test_C4.wav`. The presets are deliberately exaggerated; the goal is not taste, but to hear whether DecentSampler applies the exported effect at all.",
        "",
        "If the dry control works but an effect preset sounds unchanged, note the DecentSampler version and the preset name.",
        "",
        "| Preset | Effect under test | What to listen for |",
        "| --- | --- | --- |",
    ]
    for preset, effect, expected in rows:
        lines.append(f"| `{preset}` | {effect} | {expected} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_pack(output_root: Path) -> None:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    tests: list[dict[str, Any]] = [
        {"name": "00_Dry_Control", "effect": "none", "expected": "Plain bright sustained tone; use this as the comparison."},
        {"name": "01_Filter_Lowpass", "effect": "lowpass", "expected": "Much darker tone; upper harmonics reduced.", "kwargs": {"lowpass_enabled": True, "filter_type": "lowpass", "lowpass_frequency": 900.0, "filter_resonance": 1.2, "ds_knob_tone": True, "ds_knob_filter_resonance": True}},
        {"name": "02_Filter_Lowpass_1pl", "effect": "lowpass_1pl", "expected": "Gentler darkening than the resonant lowpass.", "kwargs": {"lowpass_enabled": True, "filter_type": "lowpass_1pl", "lowpass_frequency": 900.0, "ds_knob_tone": True}},
        {"name": "03_Filter_Lowpass_4pl", "effect": "lowpass_4pl", "expected": "Legacy lowpass; dark/resonant like lowpass.", "kwargs": {"lowpass_enabled": True, "filter_type": "lowpass_4pl", "lowpass_frequency": 900.0, "filter_resonance": 1.2, "ds_knob_tone": True, "ds_knob_filter_resonance": True}},
        {"name": "04_Filter_Bandpass", "effect": "bandpass", "expected": "Narrower, telephone/radio-like band of tone.", "kwargs": {"lowpass_enabled": True, "filter_type": "bandpass", "lowpass_frequency": 1300.0, "filter_resonance": 2.5, "ds_knob_tone": True, "ds_knob_filter_resonance": True}},
        {"name": "05_Filter_Highpass", "effect": "highpass", "expected": "Thinner tone; low body removed.", "kwargs": {"lowpass_enabled": True, "filter_type": "highpass", "lowpass_frequency": 900.0, "filter_resonance": 0.9, "ds_knob_tone": True, "ds_knob_filter_resonance": True}},
        {"name": "06_Notch", "effect": "notch", "expected": "A scooped/hollow colour around the notch frequency.", "kwargs": {"notch_enabled": True, "notch_frequency": 780.0, "notch_q": 8.0, "ds_knob_notch_frequency": True, "ds_knob_notch_q": True}},
        {"name": "07_Peak", "effect": "peak", "expected": "A strong focused tonal emphasis.", "kwargs": {"peak_enabled": True, "peak_frequency": 1000.0, "peak_q": 4.0, "peak_gain": 4.0, "ds_knob_peak_frequency": True, "ds_knob_peak_q": True, "ds_knob_peak_gain": True}},
        {"name": "08_Gain", "effect": "gain", "expected": "Obviously quieter than the dry control.", "kwargs": {"gain_enabled": True, "gain_level": -18.0, "ds_knob_gain_level": True}},
        {"name": "09_Reverb", "effect": "reverb", "expected": "Wet room/reverb tail.", "kwargs": {"reverb_enabled": True, "reverb_room_size": 0.95, "reverb_damping": 0.15, "reverb_wet_level": 0.8, "ds_knob_reverb_wet": True, "ds_knob_reverb_room": True, "ds_knob_reverb_damping": True}},
        {"name": "10_Delay", "effect": "delay", "expected": "Clear repeating echoes.", "kwargs": {"delay_enabled": True, "delay_time": 0.28, "delay_stereo_offset": 0.2, "delay_feedback": 0.65, "delay_wet_level": 0.75, "ds_knob_delay_wet": True, "ds_knob_delay_time": True, "ds_knob_delay_stereo_offset": True, "ds_knob_delay_feedback": True}},
        {"name": "11_Chorus", "effect": "chorus", "expected": "Wider/modulated shimmer or doubling.", "kwargs": {"chorus_enabled": True, "chorus_mix": 0.9, "chorus_mod_depth": 0.8, "chorus_mod_rate": 1.8, "ds_knob_chorus_mix": True, "ds_knob_chorus_depth": True, "ds_knob_chorus_rate": True}},
        {"name": "12_Phaser", "effect": "phaser", "expected": "Sweeping phase/comb-filter movement.", "kwargs": {"phaser_enabled": True, "phaser_mix": 0.9, "phaser_mod_depth": 0.9, "phaser_mod_rate": 0.8, "phaser_center_frequency": 900.0, "phaser_feedback": 0.85, "ds_knob_phaser_mix": True, "ds_knob_phaser_depth": True, "ds_knob_phaser_rate": True, "ds_knob_phaser_frequency": True, "ds_knob_phaser_feedback": True}},
        {"name": "13_Convolution", "effect": "convolution", "expected": "Coloured slap/space from the generated IR file.", "kwargs": {"convolution_enabled": True, "reverb_ir_file": "Samples/test_ir.wav", "reverb_mix": 0.8, "ds_knob_convolution_mix": True}, "needs_ir": True},
        {"name": "14_Pitch_Shift", "effect": "pitch_shift", "expected": "A shifted harmony above the dry pitch.", "kwargs": {"pitch_shift_enabled": True, "pitch_shift": 7.0, "pitch_shift_mix": 0.85, "ds_knob_pitch_shift": True, "ds_knob_pitch_shift_mix": True}},
        {"name": "15_Wave_Folder", "effect": "wave_folder", "expected": "Folded/distorted added harmonics.", "kwargs": {"wave_folder_enabled": True, "wave_folder_drive": 8.0, "wave_folder_threshold": 0.12, "ds_knob_wave_folder_drive": True, "ds_knob_wave_folder_threshold": True}},
        {"name": "16_Wave_Shaper", "effect": "wave_shaper", "expected": "Distortion/saturation with extra harmonics.", "kwargs": {"wave_shaper_enabled": True, "wave_shaper_drive": 12.0, "wave_shaper_drive_boost": 1.0, "wave_shaper_output_level": 0.3, "wave_shaper_high_quality": True, "ds_knob_wave_shaper_drive": True, "ds_knob_wave_shaper_boost": True, "ds_knob_wave_shaper_output": True}},
        {"name": "17_Stereo_Simulator", "effect": "stereo_simulator", "expected": "Widening/doubling effect, most obvious in stereo/headphones.", "kwargs": {"stereo_simulator_enabled": True, "stereo_simulator_algorithm": "adt", "stereo_simulator_width": 1.0, "stereo_simulator_delay_time": 0.018, "stereo_simulator_mod_rate": 0.9, "stereo_simulator_mod_depth": 0.8, "ds_knob_stereo_width": True}},
        {"name": "18_Bit_Crusher", "effect": "bit_crusher", "expected": "Crunchy/lo-fi digital degradation.", "kwargs": {"bit_crusher_enabled": True, "bit_crusher_bit_depth": 5, "bit_crusher_sample_rate_reduction": 8, "bit_crusher_mix": 1.0, "ds_knob_bit_depth": True, "ds_knob_bit_crusher_rate": True, "ds_knob_bit_crusher_mix": True}},
    ]

    sample = _sample_for(output_root)
    _make_ir_sample(output_root / "Samples" / "test_ir.wav")

    rows: list[tuple[str, str, str]] = []
    for test in tests:
        name = str(test["name"])
        preset = generate_dspreset(
            name,
            output_root,
            [sample],
            **test.get("kwargs", {}),
        )
        rows.append((preset.name, str(test["effect"]), str(test["expected"])))

    _write_notes(output_root / "LISTENING_CHECKLIST.md", rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local DecentSampler effects listening test pack.")
    parser.add_argument(
        "output",
        nargs="?",
        default="effects-test-pack",
        type=Path,
        help="Output directory to recreate. Defaults to ./effects-test-pack",
    )
    args = parser.parse_args()
    build_pack(args.output.expanduser().resolve())
    print(f"Wrote effects test pack: {args.output.expanduser().resolve()}")
    print("Open LISTENING_CHECKLIST.md in that folder, then open each .dspreset in DecentSampler.")


if __name__ == "__main__":
    main()
