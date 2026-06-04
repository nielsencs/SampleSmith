#!/usr/bin/env python3
"""SampleSmith - a small GUI helper for building Decent Sampler instruments.

This is an MVP. It gives Carl a visual workflow for:
- pitched sampling: detect sung/played lowest and highest notes, build a note list,
  play references, record/trim samples, and generate a .dspreset;
- unpitched/pad sampling: record labelled sounds onto consecutive MIDI pads and
  generate a .dspreset.

Install audio dependencies on the recording machine:
  python -m pip install sounddevice soundfile numpy
Optional, for better pitch detection:
  python -m pip install librosa
"""

from __future__ import annotations

import json
import math
import queue
import re
import threading
import time
import tkinter as tk
import wave
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTE_ALIASES = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"}
A4_MIDI = 69
A4_HZ = 440.0
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

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "root_note": self.root_note,
            "lo_note": self.lo_note,
            "hi_note": self.hi_note,
            "label": self.label,
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SampleInfo":
        return cls(
            path=Path(str(data["path"])),
            root_note=int(data["root_note"]),
            lo_note=int(data["lo_note"]),
            hi_note=int(data["hi_note"]),
            label=str(data.get("label", "")),
            mode=str(data.get("mode", "pitched")),
        )


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


def clamp_midi_note(midi_note: int) -> int:
    return max(0, min(127, midi_note))


def generate_dspreset(
    instrument_name: str,
    output_dir: Path,
    samples: list[SampleInfo],
    loop_enabled: bool = False,
    root_note_offset: int = 0,
    delay_enabled: bool = False,
    delay_time: float = 0.1,
    delay_stereo_offset: float = 0.01,
    delay_feedback: float = 0.7,
    delay_wet_level: float = 0.1,
    lowpass_enabled: bool = False,
    lowpass_frequency: float = 22000.0,
    reverb_enabled: bool = False,
    reverb_wet_level: float = 0.5,
    chorus_enabled: bool = False,
    chorus_mix: float = 0.5,
    chorus_mod_depth: float = 0.5,
    chorus_mod_rate: float = 0.1,
    reverb_ir_file: str = "",
    reverb_mix: float = 0.0,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    root = ET.Element("DecentSampler", {"pluginVersion": "1"})
    groups = ET.SubElement(root, "groups")
    group = ET.SubElement(groups, "group", {"attack": "0.01", "release": "0.8"})
    for sample in samples:
        attrs = {
            "path": sample.path.relative_to(output_dir).as_posix(),
            "rootNote": str(clamp_midi_note(sample.root_note + root_note_offset)),
            "loNote": str(sample.lo_note),
            "hiNote": str(sample.hi_note),
            "loVel": "1",
            "hiVel": "127",
        }
        if loop_enabled:
            attrs["loopEnabled"] = "true"
        ET.SubElement(group, "sample", attrs)
    effects_to_write: list[tuple[str, dict[str, str]]] = []
    if delay_enabled:
        effects_to_write.append(
            (
                "delay",
                {
                    "delayTime": f"{delay_time:.3f}",
                    "stereoOffset": f"{delay_stereo_offset:.3f}",
                    "feedback": f"{delay_feedback:.3f}",
                    "wetLevel": f"{delay_wet_level:.3f}",
                },
            )
        )
    if lowpass_enabled:
        effects_to_write.append(("lowpass_4pl", {"frequency": f"{lowpass_frequency:.1f}"}))
    if reverb_enabled:
        effects_to_write.append(("reverb", {"wetLevel": f"{reverb_wet_level:.3f}"}))
    if chorus_enabled:
        effects_to_write.append(
            (
                "chorus",
                {
                    "mix": f"{chorus_mix:.3f}",
                    "modDepth": f"{chorus_mod_depth:.3f}",
                    "modRate": f"{chorus_mod_rate:.3f}",
                },
            )
        )
    if reverb_ir_file.strip() and reverb_mix > 0:
        effects_to_write.append(("convolution", {"mix": f"{max(0.0, min(1.0, reverb_mix)):.3f}", "irFile": reverb_ir_file.strip()}))
    if effects_to_write:
        effects = ET.SubElement(root, "effects")
        for effect_type, attrs in effects_to_write:
            ET.SubElement(effects, "effect", {"type": effect_type, **attrs})
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    preset_path = output_dir / f"{slugify(instrument_name)}.dspreset"
    tree.write(preset_path, encoding="utf-8", xml_declaration=True)
    return preset_path


class SampleSmithApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("SampleSmith")
        self.geometry("920x680")
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.samples: list[SampleInfo] = []
        self.project_path: Path | None = None
        self.low_note: int | None = None
        self.high_note: int | None = None
        self.note_rows: dict[int, str] = {}
        self.pad_note = DEFAULT_PAD_START_NOTE
        self._build_ui()
        self.after(100, self._drain_queue)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        project = ttk.LabelFrame(outer, text="Project")
        project.pack(fill="x")
        self.name_var = tk.StringVar(value="CarlSampler")
        self.output_var = tk.StringVar(value=str(Path.cwd() / "captured-samplers"))
        self.sample_rate_var = tk.IntVar(value=DEFAULT_SAMPLE_RATE)
        self.record_seconds_var = tk.DoubleVar(value=4.0)
        self.threshold_var = tk.DoubleVar(value=-45.0)
        self.normalise_var = tk.BooleanVar(value=True)
        self.loop_enabled_var = tk.BooleanVar(value=False)
        self.root_note_offset_var = tk.IntVar(value=-12)
        self.delay_enabled_var = tk.BooleanVar(value=False)
        self.delay_time_var = tk.DoubleVar(value=0.1)
        self.delay_stereo_offset_var = tk.DoubleVar(value=0.01)
        self.delay_feedback_var = tk.DoubleVar(value=0.7)
        self.delay_wet_level_var = tk.DoubleVar(value=0.1)
        self.lowpass_enabled_var = tk.BooleanVar(value=False)
        self.lowpass_frequency_var = tk.DoubleVar(value=22000.0)
        self.reverb_enabled_var = tk.BooleanVar(value=False)
        self.reverb_wet_level_var = tk.DoubleVar(value=0.5)
        self.chorus_enabled_var = tk.BooleanVar(value=False)
        self.chorus_mix_var = tk.DoubleVar(value=0.5)
        self.chorus_mod_depth_var = tk.DoubleVar(value=0.5)
        self.chorus_mod_rate_var = tk.DoubleVar(value=0.1)
        self.reverb_ir_var = tk.StringVar(value="")
        self.reverb_mix_var = tk.DoubleVar(value=0.0)

        ttk.Label(project, text="Name").grid(row=0, column=0, sticky="w")
        ttk.Entry(project, textvariable=self.name_var, width=28).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Label(project, text="Output").grid(row=0, column=2, sticky="w")
        ttk.Entry(project, textvariable=self.output_var, width=46).grid(row=0, column=3, sticky="ew", padx=4)
        ttk.Button(project, text="Browse", command=self._browse_output).grid(row=0, column=4)
        ttk.Label(project, text="Record seconds").grid(row=1, column=0, sticky="w")
        ttk.Spinbox(project, textvariable=self.record_seconds_var, from_=0.5, to=30, increment=0.5, width=8).grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(project, text="Trim dB").grid(row=1, column=2, sticky="w")
        ttk.Spinbox(project, textvariable=self.threshold_var, from_=-80, to=-10, increment=1, width=8).grid(row=1, column=3, sticky="w", padx=4)
        ttk.Checkbutton(project, text="Normalise", variable=self.normalise_var).grid(row=1, column=4, sticky="w")
        ttk.Button(project, text="Open project", command=self._open_project_dialog).grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Button(project, text="Save project", command=self._save_project_dialog).grid(row=2, column=1, sticky="w", pady=(6, 0), padx=4)
        project.columnconfigure(3, weight=1)

        tabs = ttk.Notebook(outer)
        tabs.pack(fill="both", expand=True, pady=8)
        self.pitched_tab = ttk.Frame(tabs, padding=8)
        self.pads_tab = ttk.Frame(tabs, padding=8)
        self.decent_sampler_tab = ttk.Frame(tabs, padding=8)
        tabs.add(self.pitched_tab, text="Pitched")
        tabs.add(self.pads_tab, text="Unpitched / Pads")
        tabs.add(self.decent_sampler_tab, text="Decent Sampler")
        self._build_pitched_tab()
        self._build_pads_tab()
        self._build_decent_sampler_tab()

        bottom = ttk.Frame(outer)
        bottom.pack(fill="both")
        ttk.Button(bottom, text="Open output folder", command=self._open_output_folder).pack(side="left", padx=6)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left", padx=12)
        self.log = tk.Text(outer, height=9, wrap="word")
        self.log.pack(fill="both", expand=False, pady=(8, 0))

    def _build_pitched_tab(self) -> None:
        controls = ttk.Frame(self.pitched_tab)
        controls.pack(fill="x")
        ttk.Button(controls, text="Record lowest note", command=lambda: self._detect_note("low")).pack(side="left")
        self.low_var = tk.StringVar(value="not set")
        ttk.Label(controls, textvariable=self.low_var, width=10).pack(side="left", padx=3)
        self.low_entry_var = tk.StringVar()
        ttk.Entry(controls, textvariable=self.low_entry_var, width=7).pack(side="left")
        ttk.Button(controls, text="Set", command=lambda: self._set_note_from_entry("low")).pack(side="left", padx=(2, 8))
        ttk.Button(controls, text="Record highest note", command=lambda: self._detect_note("high")).pack(side="left")
        self.high_var = tk.StringVar(value="not set")
        ttk.Label(controls, textvariable=self.high_var, width=10).pack(side="left", padx=3)
        self.high_entry_var = tk.StringVar()
        ttk.Entry(controls, textvariable=self.high_entry_var, width=7).pack(side="left")
        ttk.Button(controls, text="Set", command=lambda: self._set_note_from_entry("high")).pack(side="left", padx=(2, 8))
        ttk.Label(controls, text="Step").pack(side="left", padx=(4, 2))
        self.step_var = tk.IntVar(value=1)
        ttk.Spinbox(controls, textvariable=self.step_var, from_=1, to=12, width=4).pack(side="left")
        ttk.Button(controls, text="Build note list", command=self._build_note_list).pack(side="left", padx=8)

        self.note_tree = ttk.Treeview(self.pitched_tab, columns=("note", "maps", "file"), show="headings", height=14)
        self.note_tree.heading("note", text="Recorded note")
        self.note_tree.heading("maps", text="Maps to keys")
        self.note_tree.heading("file", text="Sample file")
        self.note_tree.column("note", width=120, stretch=False)
        self.note_tree.column("maps", width=230, stretch=False)
        self.note_tree.column("file", width=420)
        self.note_tree.pack(fill="both", expand=True, pady=8)
        buttons = ttk.Frame(self.pitched_tab)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Play selected reference", command=self._play_selected_reference).pack(side="left")
        ttk.Button(buttons, text="Record selected sample", command=self._record_selected_note).pack(side="left", padx=6)
        ttk.Button(buttons, text="Record all missing", command=self._record_all_missing).pack(side="left")

    def _build_pads_tab(self) -> None:
        controls = ttk.Frame(self.pads_tab)
        controls.pack(fill="x")
        ttk.Label(controls, text="Pad label").pack(side="left")
        self.pad_label_var = tk.StringVar()
        ttk.Entry(controls, textvariable=self.pad_label_var, width=28).pack(side="left", padx=4)
        ttk.Label(controls, text="Start note").pack(side="left", padx=(12, 2))
        self.pad_start_var = tk.StringVar(value=midi_to_name(DEFAULT_PAD_START_NOTE))
        ttk.Entry(controls, textvariable=self.pad_start_var, width=8).pack(side="left")
        ttk.Button(controls, text="Record pad", command=self._record_pad).pack(side="left", padx=8)

        self.pad_tree = ttk.Treeview(self.pads_tab, columns=("note", "label", "file"), show="headings", height=14)
        self.pad_tree.heading("note", text="Maps to pad")
        self.pad_tree.heading("label", text="Label")
        self.pad_tree.heading("file", text="Sample file")
        self.pad_tree.column("note", width=90, stretch=False)
        self.pad_tree.column("label", width=160, stretch=False)
        self.pad_tree.column("file", width=520)
        self.pad_tree.pack(fill="both", expand=True, pady=8)

    def _build_decent_sampler_tab(self) -> None:
        export = ttk.LabelFrame(self.decent_sampler_tab, text="Decent Sampler output")
        export.pack(fill="x")
        ttk.Checkbutton(export, text="Loop samples", variable=self.loop_enabled_var, command=self._on_output_parameter_changed).grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Label(export, text="Root offset").grid(row=0, column=1, sticky="w", padx=(18, 4), pady=6)
        ttk.Spinbox(export, textvariable=self.root_note_offset_var, from_=-36, to=36, increment=12, width=6, command=self._on_output_parameter_changed).grid(row=0, column=2, sticky="w", pady=6)
        ttk.Button(export, text="Generate / update .dspreset", command=self._generate_preset).grid(row=0, column=3, sticky="w", padx=(18, 6), pady=6)
        ttk.Button(export, text="Open output folder", command=self._open_output_folder).grid(row=0, column=4, sticky="w", padx=6, pady=6)

        effects = ttk.LabelFrame(self.decent_sampler_tab, text="DS default-style effects")
        effects.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(effects, text="Tone lowpass_4pl", variable=self.lowpass_enabled_var, command=self._on_output_parameter_changed).grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Label(effects, text="frequency").grid(row=0, column=1, sticky="w")
        ttk.Spinbox(effects, textvariable=self.lowpass_frequency_var, from_=60, to=22000, increment=100, width=8).grid(row=0, column=2, sticky="w", padx=3)
        ttk.Checkbutton(effects, text="Reverb", variable=self.reverb_enabled_var, command=self._on_output_parameter_changed).grid(row=0, column=3, sticky="w", padx=(18, 6), pady=4)
        ttk.Label(effects, text="wetLevel").grid(row=0, column=4, sticky="w")
        ttk.Spinbox(effects, textvariable=self.reverb_wet_level_var, from_=0.0, to=1.0, increment=0.05, width=6).grid(row=0, column=5, sticky="w", padx=3)
        ttk.Button(effects, text="Apply effects", command=self._on_output_parameter_changed).grid(row=0, column=6, sticky="w", padx=8, pady=4)

        experimental = ttk.LabelFrame(self.decent_sampler_tab, text="Experimental effects")
        experimental.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(experimental, text="Delay", variable=self.delay_enabled_var, command=self._on_output_parameter_changed).grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Label(experimental, text="time").grid(row=0, column=1, sticky="w")
        ttk.Spinbox(experimental, textvariable=self.delay_time_var, from_=0.0, to=2.0, increment=0.05, width=6).grid(row=0, column=2, sticky="w", padx=3)
        ttk.Label(experimental, text="stereo").grid(row=0, column=3, sticky="w")
        ttk.Spinbox(experimental, textvariable=self.delay_stereo_offset_var, from_=0.0, to=0.5, increment=0.01, width=6).grid(row=0, column=4, sticky="w", padx=3)
        ttk.Label(experimental, text="feedback").grid(row=0, column=5, sticky="w")
        ttk.Spinbox(experimental, textvariable=self.delay_feedback_var, from_=0.0, to=1.0, increment=0.05, width=6).grid(row=0, column=6, sticky="w", padx=3)
        ttk.Label(experimental, text="wet").grid(row=0, column=7, sticky="w")
        ttk.Spinbox(experimental, textvariable=self.delay_wet_level_var, from_=0.0, to=1.0, increment=0.05, width=6).grid(row=0, column=8, sticky="w", padx=3)

        ttk.Checkbutton(experimental, text="Chorus", variable=self.chorus_enabled_var, command=self._on_output_parameter_changed).grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Label(experimental, text="mix").grid(row=1, column=1, sticky="w")
        ttk.Spinbox(experimental, textvariable=self.chorus_mix_var, from_=0.0, to=1.0, increment=0.05, width=6).grid(row=1, column=2, sticky="w", padx=3)
        ttk.Label(experimental, text="depth").grid(row=1, column=3, sticky="w")
        ttk.Spinbox(experimental, textvariable=self.chorus_mod_depth_var, from_=0.0, to=1.0, increment=0.05, width=6).grid(row=1, column=4, sticky="w", padx=3)
        ttk.Label(experimental, text="rate").grid(row=1, column=5, sticky="w")
        ttk.Spinbox(experimental, textvariable=self.chorus_mod_rate_var, from_=0.0, to=10.0, increment=0.05, width=6).grid(row=1, column=6, sticky="w", padx=3)

        converb = ttk.LabelFrame(self.decent_sampler_tab, text="Advanced: convolution reverb / IR")
        converb.pack(fill="x", pady=(10, 0))
        ttk.Label(converb, text="IR file path in DS instrument").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(converb, textvariable=self.reverb_ir_var, width=42).grid(row=0, column=1, sticky="ew", padx=4, pady=6)
        ttk.Label(converb, text="Mix 0–1").grid(row=0, column=2, sticky="w", padx=(12, 4), pady=6)
        ttk.Spinbox(converb, textvariable=self.reverb_mix_var, from_=0.0, to=1.0, increment=0.05, width=6, command=self._on_output_parameter_changed).grid(row=0, column=3, sticky="w", pady=6)
        ttk.Button(converb, text="Apply", command=self._on_output_parameter_changed).grid(row=0, column=4, sticky="w", padx=8, pady=6)
        converb.columnconfigure(1, weight=1)

        mapping = ttk.LabelFrame(self.decent_sampler_tab, text="Effective exported sample mapping")
        mapping.pack(fill="both", expand=True, pady=(10, 0))
        self.export_tree = ttk.Treeview(mapping, columns=("source", "keys", "root", "mode"), show="headings", height=10)
        self.export_tree.heading("source", text="Source WAV")
        self.export_tree.heading("keys", text="Plays on keys")
        self.export_tree.heading("root", text="Exported root")
        self.export_tree.heading("mode", text="Mode")
        self.export_tree.column("source", width=280)
        self.export_tree.column("keys", width=230)
        self.export_tree.column("root", width=160)
        self.export_tree.column("mode", width=80, stretch=False)
        self.export_tree.pack(fill="both", expand=True, padx=6, pady=6)

        notes = ttk.LabelFrame(self.decent_sampler_tab, text="Notes")
        notes.pack(fill="x", pady=(10, 0))
        ttk.Label(
            notes,
            text=(
                "This tab is for Decent Sampler generation settings. "
                "Loop start/end, sample start/end, envelopes, and other export controls can grow here later."
            ),
            wraplength=820,
            justify="left",
        ).pack(anchor="w", padx=6, pady=6)

    def _audio(self) -> AudioEngine:
        return AudioEngine(
            sample_rate=self.sample_rate_var.get(),
            trim_threshold_db=self.threshold_var.get(),
            pre_roll_ms=40.0,
            post_roll_ms=180.0,
            normalise=self.normalise_var.get(),
        )

    def _instrument_dir(self) -> Path:
        return Path(self.output_var.get()).expanduser() / slugify(self.name_var.get())

    def _sample_path(self, label: str) -> Path:
        return self._instrument_dir() / "Samples" / f"{slugify(self.name_var.get())}_{label}.wav"

    def _browse_output(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.output_var.get() or str(Path.cwd()))
        if chosen:
            self.output_var.set(chosen)

    def _default_project_path(self) -> Path:
        return self._instrument_dir() / f"{slugify(self.name_var.get())}.samplesmith.json"

    def _project_data(self) -> dict[str, object]:
        return {
            "version": 1,
            "name": self.name_var.get(),
            "output": self.output_var.get(),
            "sample_rate": self.sample_rate_var.get(),
            "record_seconds": self.record_seconds_var.get(),
            "trim_threshold_db": self.threshold_var.get(),
            "normalise": self.normalise_var.get(),
            "loop_enabled": self.loop_enabled_var.get(),
            "root_note_offset": self.root_note_offset_var.get(),
            "delay_enabled": self.delay_enabled_var.get(),
            "delay_time": self.delay_time_var.get(),
            "delay_stereo_offset": self.delay_stereo_offset_var.get(),
            "delay_feedback": self.delay_feedback_var.get(),
            "delay_wet_level": self.delay_wet_level_var.get(),
            "lowpass_enabled": self.lowpass_enabled_var.get(),
            "lowpass_frequency": self.lowpass_frequency_var.get(),
            "reverb_enabled": self.reverb_enabled_var.get(),
            "reverb_wet_level": self.reverb_wet_level_var.get(),
            "chorus_enabled": self.chorus_enabled_var.get(),
            "chorus_mix": self.chorus_mix_var.get(),
            "chorus_mod_depth": self.chorus_mod_depth_var.get(),
            "chorus_mod_rate": self.chorus_mod_rate_var.get(),
            "reverb_ir_file": self.reverb_ir_var.get(),
            "reverb_mix": self.reverb_mix_var.get(),
            "low_note": self.low_note,
            "high_note": self.high_note,
            "step": self.step_var.get(),
            "pad_start": self.pad_start_var.get(),
            "next_pad_note": self.pad_note,
            "samples": [sample.to_dict() for sample in self.samples],
        }

    def _save_project(self, path: Path | None = None) -> Path:
        target = path or self.project_path or self._default_project_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self._project_data(), indent=2), encoding="utf-8")
        self.project_path = target
        return target

    def _save_project_dialog(self) -> None:
        initial = self.project_path or self._default_project_path()
        chosen = filedialog.asksaveasfilename(
            initialdir=str(initial.parent),
            initialfile=initial.name,
            defaultextension=".samplesmith.json",
            filetypes=[("SampleSmith project", "*.samplesmith.json"), ("JSON", "*.json"), ("All files", "*.*")],
        )
        if not chosen:
            return
        saved = self._save_project(Path(chosen))
        self._log(f"Saved project: {saved}")

    def _auto_save_project(self) -> None:
        try:
            saved = self._save_project()
            self._log(f"Saved project: {saved.name}")
        except Exception as exc:
            self._log(f"Could not save project: {exc}")

    def _open_project_dialog(self) -> None:
        chosen = filedialog.askopenfilename(
            initialdir=str(self._instrument_dir()),
            filetypes=[("SampleSmith project", "*.samplesmith.json"), ("JSON", "*.json"), ("All files", "*.*")],
        )
        if chosen:
            self._open_project(Path(chosen))

    def _open_project(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.project_path = path
        self.name_var.set(str(data.get("name", "CarlSampler")))
        self.output_var.set(str(data.get("output", str(Path.cwd() / "captured-samplers"))))
        self.sample_rate_var.set(int(data.get("sample_rate", DEFAULT_SAMPLE_RATE)))
        self.record_seconds_var.set(float(data.get("record_seconds", 4.0)))
        self.threshold_var.set(float(data.get("trim_threshold_db", -45.0)))
        self.normalise_var.set(bool(data.get("normalise", True)))
        self.loop_enabled_var.set(bool(data.get("loop_enabled", False)))
        self.root_note_offset_var.set(int(data.get("root_note_offset", 12)))
        self.delay_enabled_var.set(bool(data.get("delay_enabled", False)))
        self.delay_time_var.set(float(data.get("delay_time", 0.1)))
        self.delay_stereo_offset_var.set(float(data.get("delay_stereo_offset", 0.01)))
        self.delay_feedback_var.set(float(data.get("delay_feedback", 0.7)))
        self.delay_wet_level_var.set(float(data.get("delay_wet_level", 0.1)))
        self.lowpass_enabled_var.set(bool(data.get("lowpass_enabled", False)))
        self.lowpass_frequency_var.set(float(data.get("lowpass_frequency", 22000.0)))
        self.reverb_enabled_var.set(bool(data.get("reverb_enabled", False)))
        self.reverb_wet_level_var.set(float(data.get("reverb_wet_level", 0.5)))
        self.chorus_enabled_var.set(bool(data.get("chorus_enabled", False)))
        self.chorus_mix_var.set(float(data.get("chorus_mix", 0.5)))
        self.chorus_mod_depth_var.set(float(data.get("chorus_mod_depth", 0.5)))
        self.chorus_mod_rate_var.set(float(data.get("chorus_mod_rate", 0.1)))
        self.reverb_ir_var.set(str(data.get("reverb_ir_file", "")))
        self.reverb_mix_var.set(float(data.get("reverb_mix", 0.0)))
        self.low_note = int(data["low_note"]) if data.get("low_note") is not None else None
        self.high_note = int(data["high_note"]) if data.get("high_note") is not None else None
        self.low_var.set(midi_to_name(self.low_note) if self.low_note is not None else "not set")
        self.high_var.set(midi_to_name(self.high_note) if self.high_note is not None else "not set")
        self.low_entry_var.set(midi_to_name(self.low_note) if self.low_note is not None else "")
        self.high_entry_var.set(midi_to_name(self.high_note) if self.high_note is not None else "")
        self.step_var.set(int(data.get("step", 1)))
        self.pad_start_var.set(str(data.get("pad_start", midi_to_name(DEFAULT_PAD_START_NOTE))))
        self.pad_note = int(data.get("next_pad_note", DEFAULT_PAD_START_NOTE))
        self.samples = [SampleInfo.from_dict(item) for item in data.get("samples", [])]
        self._rebuild_trees_from_project()
        self._log(f"Opened project: {path}")

    def _rebuild_trees_from_project(self) -> None:
        for item in self.note_tree.get_children():
            self.note_tree.delete(item)
        for item in self.pad_tree.get_children():
            self.pad_tree.delete(item)
        self.note_rows.clear()
        if self.low_note is not None and self.high_note is not None:
            notes = note_range(self.low_note, self.high_note, self.step_var.get())
            ranges = dict((root, (lo, hi)) for root, lo, hi in build_key_ranges(notes))
            for note in notes:
                lo, hi = ranges[note]
                recorded = next((sample for sample in self.samples if sample.mode == "pitched" and sample.root_note == note), None)
                self.note_rows[note] = str(recorded.path) if recorded else ""
                self.note_tree.insert("", "end", iid=str(note), values=(midi_to_name(note), mapping_text(lo, hi), recorded.path.name if recorded else ""))
            self._refresh_pitched_mappings()
        for sample in self.samples:
            if sample.mode == "pad":
                self.pad_tree.insert("", "end", values=(midi_to_name(sample.root_note), sample.label, sample.path.name))
        self._refresh_export_mapping()

    def _log(self, text: str) -> None:
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.status_var.set(text)

    def _run_worker(self, label: str, func) -> None:
        self.status_var.set(label)
        threading.Thread(target=lambda: self._worker_wrapper(func), daemon=True).start()

    def _worker_wrapper(self, func) -> None:
        try:
            result = func()
            self.queue.put(("ok", result))
        except Exception as exc:  # pragma: no cover - GUI error path
            self.queue.put(("error", exc))

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "error":
                    self._log(f"Error: {payload}")
                    messagebox.showerror("SampleSmith", str(payload))
                elif callable(payload):
                    payload()
                elif payload:
                    self._log(str(payload))
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    def _parse_note_entry(self, text: str) -> int:
        text = text.strip()
        if not text:
            raise ValueError("Enter a note, e.g. C2, F#3, or a MIDI number.")
        try:
            midi_note = int(text)
        except ValueError:
            midi_note = name_to_midi(text)
        if not 0 <= midi_note <= 127:
            raise ValueError("MIDI note must be between 0 and 127.")
        return midi_note

    def _set_note_from_entry(self, which: str) -> None:
        try:
            midi_note = self._parse_note_entry(self.low_entry_var.get() if which == "low" else self.high_entry_var.get())
        except ValueError as exc:
            messagebox.showerror("SampleSmith", str(exc))
            return
        note_name = midi_to_name(midi_note)
        if which == "low":
            self.low_note = midi_note
            self.low_var.set(note_name)
            self.low_entry_var.set(note_name)
        else:
            self.high_note = midi_note
            self.high_var.set(note_name)
            self.high_entry_var.set(note_name)
        self._log(f"Set {which} note to {note_name}")

    def _detect_note(self, which: str) -> None:
        if not messagebox.askokcancel("SampleSmith", f"After pressing OK, sing/play your {which} usable note for 2.5 seconds."):
            return

        def work():
            audio = self._audio()
            raw = audio.record(2.5)
            freq = audio.detect_pitch(raw)
            if freq is None:
                raise RuntimeError("Could not detect a clear pitch. Try again, or use pad mode for noisy sounds.")
            midi = freq_to_midi(freq)
            name = midi_to_name(midi)

            def apply():
                if messagebox.askyesno("Confirm pitch", f"I think that was {name} ({freq:.1f} Hz). Accept?"):
                    if which == "low":
                        self.low_note = midi
                        self.low_var.set(name)
                        self.low_entry_var.set(name)
                    else:
                        self.high_note = midi
                        self.high_var.set(name)
                        self.high_entry_var.set(name)
                    self._log(f"Set {which} note to {name}")
            return apply

        self._run_worker("Detecting pitch...", work)

    def _build_note_list(self) -> None:
        if self.low_note is None or self.high_note is None:
            messagebox.showwarning("SampleSmith", "Record lowest and highest notes first.")
            return
        for item in self.note_tree.get_children():
            self.note_tree.delete(item)
        self.note_rows.clear()
        notes = note_range(self.low_note, self.high_note, self.step_var.get())
        ranges = dict((root, (lo, hi)) for root, lo, hi in build_key_ranges(notes))
        for note in notes:
            iid = str(note)
            lo, hi = ranges[note]
            self.note_rows[note] = ""
            self.note_tree.insert("", "end", iid=iid, values=(midi_to_name(note), mapping_text(lo, hi), ""))
        self._log("Built note list with full-keyboard sampler mapping")

    def _selected_note(self) -> int | None:
        selected = self.note_tree.selection()
        if not selected:
            messagebox.showwarning("SampleSmith", "Select a note first.")
            return None
        return int(selected[0])

    def _play_selected_reference(self) -> None:
        note = self._selected_note()
        if note is None:
            return
        self._run_worker(f"Playing {midi_to_name(note)}", lambda: (self._audio().play_tone(note), f"Played {midi_to_name(note)}")[1])

    def _record_selected_note(self) -> None:
        note = self._selected_note()
        if note is not None:
            self._record_note(note)

    def _record_all_missing(self) -> None:
        notes = [int(item) for item in self.note_tree.get_children() if not self.note_rows.get(int(item))]
        if not notes:
            self._log("No missing pitched samples")
            return
        self._record_note_sequence(notes)

    def _record_note_sequence(self, notes: list[int]) -> None:
        if not notes:
            return
        note = notes.pop(0)
        self._record_note(note, after=lambda: self._record_note_sequence(notes))

    def _record_note(self, note: int, after=None) -> None:
        note_name = midi_to_name(note)
        if not messagebox.askokcancel("SampleSmith", f"Ready to record {note_name}? I will play the reference first."):
            return
        path = self._sample_path(note_name.replace("#", "sharp"))

        def work():
            audio = self._audio()
            audio.play_tone(note)
            time.sleep(0.3)
            raw = audio.record(self.record_seconds_var.get())
            trimmed = audio.trim(raw)
            audio.write_wav(path, trimmed)
            ranges = dict((root, (lo, hi)) for root, lo, hi in build_key_ranges([int(i) for i in self.note_tree.get_children()]))
            lo, hi = ranges[note]
            info = SampleInfo(path=path, root_note=note, lo_note=lo, hi_note=hi, label=note_name, mode="pitched")

            def apply():
                self._upsert_sample(info)
                self.note_rows[note] = str(path)
                self._refresh_pitched_mappings()
                mapped = next(sample for sample in self.samples if sample.mode == "pitched" and sample.root_note == note)
                preset = self._write_preset()
                self._log(f"Recorded {note_name}: {path.name} — maps {mapping_text(mapped.lo_note, mapped.hi_note)}")
                self._log(f"Updated Decent Sampler instrument: {preset.name}")
                self._auto_save_project()
                if after:
                    after()
            return apply

        self._run_worker(f"Recording {note_name}...", work)

    def _record_pad(self) -> None:
        label = self.pad_label_var.get().strip()
        if not label:
            messagebox.showwarning("SampleSmith", "Enter a pad label first.")
            return
        if not self.pad_tree.get_children():
            try:
                self.pad_note = int(self.pad_start_var.get())
            except ValueError:
                self.pad_note = name_to_midi(self.pad_start_var.get())
        midi_note = self.pad_note
        self.pad_note += 1
        path = self._sample_path(f"pad_{midi_to_name(midi_note).replace('#', 'sharp')}_{slugify(label)}")
        if not messagebox.askokcancel("SampleSmith", f"Ready to record pad {midi_to_name(midi_note)}: {label}?"):
            self.pad_note -= 1
            return

        def work():
            audio = self._audio()
            raw = audio.record(self.record_seconds_var.get())
            trimmed = audio.trim(raw)
            audio.write_wav(path, trimmed)
            info = SampleInfo(path=path, root_note=midi_note, lo_note=midi_note, hi_note=midi_note, label=label, mode="pad")

            def apply():
                self._upsert_sample(info)
                self.pad_tree.insert("", "end", values=(midi_to_name(midi_note), label, path.name))
                self.pad_label_var.set("")
                preset = self._write_preset()
                self._log(f"Recorded pad {midi_to_name(midi_note)}: {path.name}")
                self._log(f"Updated Decent Sampler instrument: {preset.name}")
                self._auto_save_project()
            return apply

        self._run_worker(f"Recording pad {label}...", work)

    def _upsert_sample(self, info: SampleInfo) -> None:
        self.samples = [sample for sample in self.samples if not (sample.mode == info.mode and sample.root_note == info.root_note)]
        self.samples.append(info)
        self.samples.sort(key=lambda sample: (sample.mode, sample.root_note, sample.path.name))

    def _spread_recorded_pitched_samples(self) -> list[SampleInfo]:
        pitched = [sample for sample in self.samples if sample.mode == "pitched"]
        pads = [sample for sample in self.samples if sample.mode == "pad"]
        ranges = dict((root, (lo, hi)) for root, lo, hi in build_overlapping_key_ranges([sample.root_note for sample in pitched]))
        spread = [
            SampleInfo(path=sample.path, root_note=sample.root_note, lo_note=ranges[sample.root_note][0], hi_note=ranges[sample.root_note][1], label=sample.label, mode=sample.mode)
            for sample in pitched
        ]
        return sorted(spread + pads, key=lambda sample: (sample.mode, sample.root_note, sample.path.name))

    def _refresh_pitched_mappings(self) -> None:
        for sample in self._spread_recorded_pitched_samples():
            if sample.mode != "pitched" or str(sample.root_note) not in self.note_tree.get_children():
                continue
            file_name = sample.path.name if self.note_rows.get(sample.root_note) else ""
            self.note_tree.item(str(sample.root_note), values=(midi_to_name(sample.root_note), mapping_text(sample.lo_note, sample.hi_note), file_name))

    def _refresh_export_mapping(self) -> None:
        for item in self.export_tree.get_children():
            self.export_tree.delete(item)
        for sample in self._spread_recorded_pitched_samples():
            self.export_tree.insert(
                "",
                "end",
                values=(
                    sample.path.name,
                    mapping_text(sample.lo_note, sample.hi_note),
                    exported_root_text(sample.root_note, self.root_note_offset_var.get()),
                    sample.mode,
                ),
            )

    def _write_preset(self) -> Path:
        samples = self._spread_recorded_pitched_samples()
        preset = generate_dspreset(
            self.name_var.get(),
            self._instrument_dir(),
            samples,
            loop_enabled=self.loop_enabled_var.get(),
            root_note_offset=self.root_note_offset_var.get(),
            delay_enabled=self.delay_enabled_var.get(),
            delay_time=self.delay_time_var.get(),
            delay_stereo_offset=self.delay_stereo_offset_var.get(),
            delay_feedback=self.delay_feedback_var.get(),
            delay_wet_level=self.delay_wet_level_var.get(),
            lowpass_enabled=self.lowpass_enabled_var.get(),
            lowpass_frequency=self.lowpass_frequency_var.get(),
            reverb_enabled=self.reverb_enabled_var.get(),
            reverb_wet_level=self.reverb_wet_level_var.get(),
            chorus_enabled=self.chorus_enabled_var.get(),
            chorus_mix=self.chorus_mix_var.get(),
            chorus_mod_depth=self.chorus_mod_depth_var.get(),
            chorus_mod_rate=self.chorus_mod_rate_var.get(),
            reverb_ir_file=self.reverb_ir_var.get(),
            reverb_mix=self.reverb_mix_var.get(),
        )
        self._refresh_export_mapping()
        return preset

    def _on_output_parameter_changed(self) -> None:
        if not self.samples:
            self._auto_save_project()
            return
        preset = self._write_preset()
        self._log(f"Updated Decent Sampler instrument: {preset.name}")
        self._auto_save_project()

    def _generate_preset(self) -> None:
        if not self.samples:
            messagebox.showwarning("SampleSmith", "No recorded samples yet.")
            return
        preset = self._write_preset()
        self._log(f"Generated {preset}")
        messagebox.showinfo("SampleSmith", f"Generated:\n{preset}")

    def _open_output_folder(self) -> None:
        folder = self._instrument_dir()
        folder.mkdir(parents=True, exist_ok=True)
        self._log(f"Output folder: {folder}")


def main() -> None:
    app = SampleSmithApp()
    app.mainloop()


if __name__ == "__main__":
    main()
