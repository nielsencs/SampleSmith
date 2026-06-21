#!/usr/bin/env python3
"""Focused file-handling regression checks for SampleSmith.

These tests use temporary folders and generated WAV files only. They are meant to
catch destructive path/collision regressions without touching real projects.
Run under Xvfb on headless Linux because SampleSmith is a Tk app:

    SAMPLESMITH_SETTINGS_PATH=/tmp/samplesmith-settings.json \
      xvfb-run -a python3 tools/samplesmith_file_handling_regression.py
"""

from __future__ import annotations

import json
import math
import os
import struct
import sys
import tempfile
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from samplesmith_app.app import SampleSmithApp  # noqa: E402
from samplesmith_app.dspreset import export_dsbundle, generate_dspreset  # noqa: E402
from samplesmith_app.models import SampleInfo  # noqa: E402


def make_wav(path: Path, freq: float = 261.63) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        for index in range(800):
            value = int(8000 * math.sin(2 * math.pi * freq * index / 44100))
            handle.writeframes(struct.pack("<h", value))


def test_project_saves_internal_sample_paths_relative(tmp: Path) -> None:
    os.environ["SAMPLESMITH_SETTINGS_PATH"] = str(tmp / "settings.json")
    app = SampleSmithApp()
    try:
        app.name_var.set("Relative Paths")
        app.output_var.set(str(tmp / "projects"))
        sample = app._instrument_dir() / "Samples" / "voice C4.wav"
        make_wav(sample)
        app.samples = [SampleInfo(path=sample, root_note=72, lo_note=72, hi_note=72, label="C4")]
        saved = app._save_project()
        data = json.loads(saved.read_text(encoding="utf-8"))
        assert data["samples"][0]["path"] == "Samples/voice C4.wav", data["samples"][0]["path"]
    finally:
        app.destroy()


def test_save_as_refuses_to_overwrite_existing_audio(tmp: Path) -> None:
    os.environ["SAMPLESMITH_SETTINGS_PATH"] = str(tmp / "settings.json")
    app = SampleSmithApp()
    try:
        app.name_var.set("Original")
        app.output_var.set(str(tmp / "projects"))
        source = app._instrument_dir() / "Samples" / "precious.wav"
        make_wav(source, 220)
        app.samples = [SampleInfo(path=source, root_note=72, lo_note=72, hi_note=72, label="C4")]
        collision = tmp / "projects" / "Copy" / "Samples" / "precious.wav"
        make_wav(collision, 880)
        try:
            app._save_project_as(tmp / "projects" / "Copy" / "Copy.samplesmith.json")
        except FileExistsError:
            pass
        else:  # pragma: no cover - script assertion path
            raise AssertionError("Save As silently overwrote or accepted a colliding sample path")
    finally:
        app.destroy()


def test_generate_preset_rejects_external_samples_clearly(tmp: Path) -> None:
    instrument_dir = tmp / "projects" / "ExternalTest"
    external_sample = tmp / "outside" / "C4.wav"
    make_wav(external_sample)
    try:
        generate_dspreset(
            "ExternalTest",
            instrument_dir,
            [SampleInfo(path=external_sample, root_note=72, lo_note=72, hi_note=72, label="C4")],
        )
    except RuntimeError as exc:
        assert "outside this instrument folder" in str(exc)
    else:  # pragma: no cover - script assertion path
        raise AssertionError("external sample path was accepted for a movable .dspreset")


def test_dsbundle_export_preserves_existing_bundle_dir(tmp: Path) -> None:
    instrument_dir = tmp / "projects" / "BundleTest"
    sample = instrument_dir / "Samples" / "C4.wav"
    make_wav(sample)
    existing_bundle = tmp / "projects" / "BundleTest.dsbundle"
    existing_bundle.mkdir(parents=True)
    sentinel = existing_bundle / "do-not-delete.txt"
    sentinel.write_text("precious note", encoding="utf-8")

    export_dsbundle(
        "BundleTest",
        instrument_dir,
        [SampleInfo(path=sample, root_note=72, lo_note=72, hi_note=72, label="C4")],
    )

    backups = sorted(tmp.joinpath("projects").glob("BundleTest.dsbundle.backup-*"))
    assert backups, "existing bundle directory was not backed up"
    assert (backups[-1] / "do-not-delete.txt").read_text(encoding="utf-8") == "precious note"
    assert (existing_bundle / "Samples" / "C4.wav").exists()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="samplesmith-file-regression-") as raw:
        tmp = Path(raw)
        test_project_saves_internal_sample_paths_relative(tmp)
        test_save_as_refuses_to_overwrite_existing_audio(tmp)
        test_generate_preset_rejects_external_samples_clearly(tmp)
        test_dsbundle_export_preserves_existing_bundle_dir(tmp)
    print("file-handling regression checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
