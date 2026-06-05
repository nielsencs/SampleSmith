#!/usr/bin/env python3
"""Build a small Decent Sampler octave/MIDI diagnostic pack.

This confirms Decent Sampler standalone's screen-key numbering. Decent
Sampler uses key/root number 72 for its displayed C4 key. This pack uses a
middle-C/C4 tone so the key-72 preset should play unshifted from DS C4.
"""

from __future__ import annotations

import argparse
import math
import shutil
import struct
import sys
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samplesmith_app.dspreset import generate_dspreset
from samplesmith_app.models import SampleInfo

SAMPLE_RATE = 44_100
C4_HZ = 261.625565


def _write_pcm16_wav(path: Path, frames: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        payload = bytearray()
        for value in frames:
            clipped = max(-1.0, min(1.0, value))
            payload.extend(struct.pack("<h", int(clipped * 32767)))
        handle.writeframes(bytes(payload))


def _make_c4_sample(path: Path) -> None:
    seconds = 2.5
    total = int(SAMPLE_RATE * seconds)
    frames: list[float] = []
    for index in range(total):
        t = index / SAMPLE_RATE
        value = 0.45 * math.sin(2 * math.pi * C4_HZ * t)
        value += 0.12 * math.sin(2 * math.pi * C4_HZ * 2 * t)
        value += 0.06 * math.sin(2 * math.pi * C4_HZ * 3 * t)
        attack = min(1.0, index / (SAMPLE_RATE * 0.02))
        release_start = int(total - SAMPLE_RATE * 0.15)
        release = 1.0 if index <= release_start else max(0.0, (total - index) / (total - release_start))
        frames.append(value * attack * release)
    _write_pcm16_wav(path, frames)


def _write_readme(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# SampleSmith octave/MIDI diagnostic pack",
                "",
                "This pack confirms Decent Sampler standalone's screen-key/root-note convention.",
                "",
                "The WAV is a generated middle-C/C4 tone at about 261.63 Hz.",
                "Decent Sampler `rootNote`, `loNote`, and `hiNote` are key/root numbers. Its screen keyboard labels key 72 as C4.",
                "",
                "Open each preset in Decent Sampler standalone and click the on-screen C4 key:",
                "",
                "| Preset | rootNote | Expected result from DS C4 screen key |",
                "| --- | ---: | --- |",
                "| `Root_60_DS_C3.dspreset` | 60 | Shifted, because DS C4 is not key 60. |",
                "| `Root_72_DS_C4.dspreset` | 72 | Unshifted middle-C/C4 tone. |",
                "",
                "",
            ]
        ),
        encoding="utf-8",
    )


def build_pack(output_root: Path) -> None:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    sample_path = output_root / "Samples" / "generated_C4_261Hz.wav"
    _make_c4_sample(sample_path)

    for name, root_note in [("Root_60_DS_C3", 60), ("Root_72_DS_C4", 72)]:
        sample = SampleInfo(path=sample_path, root_note=root_note, lo_note=0, hi_note=127, label=name)
        generate_dspreset(name, output_root, [sample])

    _write_readme(output_root / "README.md")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Decent Sampler octave/MIDI diagnostic pack.")
    parser.add_argument(
        "output",
        nargs="?",
        default="octave-diagnostic-pack",
        type=Path,
        help="Output directory to recreate. Defaults to ./octave-diagnostic-pack",
    )
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    build_pack(output)
    print(f"Wrote octave diagnostic pack: {output}")
    print("Open README.md in that folder, then test the two .dspreset files in Decent Sampler.")


if __name__ == "__main__":
    main()
