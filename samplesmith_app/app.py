"""Tkinter GUI application for SampleSmith."""

from __future__ import annotations

import json
import math
import os
import re
import queue
import shutil
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .audio import AudioEngine, render_bridge_wav, render_retuned_bridge_wav
from .dspreset import export_dsbundle, generate_dspreset
from .looping import read_wav_smpl_loop_points
from .ui_preview import DecentSamplerUiPreview, normalise_ui_layout
from .models import (
    DEFAULT_SAMPLE_RATE,
    SampleInfo,
    build_key_ranges,
    build_overlapping_key_ranges,
    exported_root_text,
    freq_to_midi,
    mapping_text,
    midi_to_name,
    name_to_midi,
    note_range,
    optional_non_negative_int,
    slugify,
)

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
        self.export_samples_by_iid: dict[str, SampleInfo] = {}
        self._output_update_after_id: str | None = None
        self.pending_recording_review: dict[str, object] | None = None
        self._updating_review_trim_fields = False
        self.selected_panel_kind: str | None = None
        self._review_load_token = 0
        self._queue_after_id: str | None = None
        self.ui_layout: dict[str, dict[str, int]] = {}
        self.ui_preview: DecentSamplerUiPreview | None = None
        self._build_ui()
        self.blank_project_data = self._project_data()
        self.after_idle(self._open_last_project_if_available)
        self._queue_after_id = self.after(100, self._drain_queue)

    def destroy(self) -> None:
        if self._queue_after_id is not None:
            try:
                self.after_cancel(self._queue_after_id)
            except tk.TclError:
                pass
            self._queue_after_id = None
        super().destroy()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        project = ttk.LabelFrame(outer, text="Project")
        project.pack(fill="x")
        self.name_var = tk.StringVar(value="NewInstrument")
        self.output_var = tk.StringVar(value=str(Path.cwd() / "samplesmith-projects"))
        self.sample_rate_var = tk.IntVar(value=DEFAULT_SAMPLE_RATE)
        self.sample_format_var = tk.StringVar(value="flac")
        self.record_seconds_var = tk.DoubleVar(value=4.0)
        self.threshold_var = tk.DoubleVar(value=-45.0)
        self.normalise_var = tk.BooleanVar(value=True)
        self.confirm_before_record_var = tk.BooleanVar(value=False)
        self.play_reference_before_record_var = tk.BooleanVar(value=True)
        self.loop_enabled_var = tk.BooleanVar(value=False)
        self.loop_start_var = tk.StringVar(value="")
        self.loop_end_var = tk.StringVar(value="")
        self.loop_crossfade_var = tk.DoubleVar(value=0.0)
        self.loop_crossfade_mode_var = tk.StringVar(value="equal_power")
        self.amp_env_enabled_var = tk.BooleanVar(value=False)
        self.amp_attack_var = tk.DoubleVar(value=0.01)
        self.amp_decay_var = tk.DoubleVar(value=0.0)
        self.amp_sustain_var = tk.DoubleVar(value=1.0)
        self.amp_release_var = tk.DoubleVar(value=0.8)
        self.ds_knob_amp_env_var = tk.BooleanVar(value=True)
        self.delay_enabled_var = tk.BooleanVar(value=False)
        self.delay_time_var = tk.DoubleVar(value=0.7)
        self.delay_stereo_offset_var = tk.DoubleVar(value=0.0)
        self.delay_feedback_var = tk.DoubleVar(value=0.2)
        self.delay_wet_level_var = tk.DoubleVar(value=0.5)
        self.lowpass_enabled_var = tk.BooleanVar(value=False)
        self.filter_type_var = tk.StringVar(value="lowpass_4pl")
        self.lowpass_frequency_var = tk.DoubleVar(value=22000.0)
        self.filter_resonance_var = tk.DoubleVar(value=0.7)
        self.notch_enabled_var = tk.BooleanVar(value=False)
        self.notch_frequency_var = tk.DoubleVar(value=10000.0)
        self.notch_q_var = tk.DoubleVar(value=0.7)
        self.peak_enabled_var = tk.BooleanVar(value=False)
        self.peak_frequency_var = tk.DoubleVar(value=10000.0)
        self.peak_q_var = tk.DoubleVar(value=0.7)
        self.peak_gain_var = tk.DoubleVar(value=1.0)
        self.gain_enabled_var = tk.BooleanVar(value=False)
        self.gain_level_var = tk.DoubleVar(value=0.0)
        self.reverb_enabled_var = tk.BooleanVar(value=False)
        self.reverb_room_size_var = tk.DoubleVar(value=0.7)
        self.reverb_damping_var = tk.DoubleVar(value=0.3)
        self.reverb_wet_level_var = tk.DoubleVar(value=0.5)
        self.chorus_enabled_var = tk.BooleanVar(value=False)
        self.chorus_mix_var = tk.DoubleVar(value=0.5)
        self.chorus_mod_depth_var = tk.DoubleVar(value=0.2)
        self.chorus_mod_rate_var = tk.DoubleVar(value=0.2)
        self.phaser_enabled_var = tk.BooleanVar(value=False)
        self.phaser_mix_var = tk.DoubleVar(value=0.5)
        self.phaser_mod_depth_var = tk.DoubleVar(value=0.2)
        self.phaser_mod_rate_var = tk.DoubleVar(value=0.2)
        self.phaser_center_frequency_var = tk.DoubleVar(value=400.0)
        self.phaser_feedback_var = tk.DoubleVar(value=0.7)
        self.convolution_enabled_var = tk.BooleanVar(value=False)
        self.reverb_ir_var = tk.StringVar(value="")
        self.reverb_mix_var = tk.DoubleVar(value=0.0)
        self.pitch_shift_enabled_var = tk.BooleanVar(value=False)
        self.pitch_shift_var = tk.DoubleVar(value=0.0)
        self.pitch_shift_mix_var = tk.DoubleVar(value=0.5)
        self.wave_folder_enabled_var = tk.BooleanVar(value=False)
        self.wave_folder_drive_var = tk.DoubleVar(value=1.0)
        self.wave_folder_threshold_var = tk.DoubleVar(value=0.25)
        self.wave_shaper_enabled_var = tk.BooleanVar(value=False)
        self.wave_shaper_drive_var = tk.DoubleVar(value=1.0)
        self.wave_shaper_drive_boost_var = tk.DoubleVar(value=1.0)
        self.wave_shaper_output_level_var = tk.DoubleVar(value=0.1)
        self.wave_shaper_high_quality_var = tk.BooleanVar(value=True)
        self.stereo_simulator_enabled_var = tk.BooleanVar(value=False)
        self.stereo_simulator_algorithm_var = tk.StringVar(value="adt")
        self.stereo_simulator_width_var = tk.DoubleVar(value=0.5)
        self.stereo_simulator_delay_time_var = tk.DoubleVar(value=0.005)
        self.stereo_simulator_mod_rate_var = tk.DoubleVar(value=0.5)
        self.stereo_simulator_mod_depth_var = tk.DoubleVar(value=0.3)
        self.bit_crusher_enabled_var = tk.BooleanVar(value=False)
        self.bit_crusher_bit_depth_var = tk.IntVar(value=8)
        self.bit_crusher_sample_rate_reduction_var = tk.IntVar(value=4)
        self.bit_crusher_mix_var = tk.DoubleVar(value=1.0)
        self.ds_knob_tone_var = tk.BooleanVar(value=True)
        self.ds_knob_filter_resonance_var = tk.BooleanVar(value=False)
        self.ds_knob_notch_frequency_var = tk.BooleanVar(value=False)
        self.ds_knob_notch_q_var = tk.BooleanVar(value=False)
        self.ds_knob_peak_frequency_var = tk.BooleanVar(value=False)
        self.ds_knob_peak_q_var = tk.BooleanVar(value=False)
        self.ds_knob_peak_gain_var = tk.BooleanVar(value=False)
        self.ds_knob_gain_level_var = tk.BooleanVar(value=False)
        self.ds_knob_reverb_wet_var = tk.BooleanVar(value=True)
        self.ds_knob_reverb_room_var = tk.BooleanVar(value=False)
        self.ds_knob_reverb_damping_var = tk.BooleanVar(value=False)
        self.ds_knob_delay_wet_var = tk.BooleanVar(value=True)
        self.ds_knob_delay_time_var = tk.BooleanVar(value=False)
        self.ds_knob_delay_stereo_offset_var = tk.BooleanVar(value=False)
        self.ds_knob_delay_feedback_var = tk.BooleanVar(value=False)
        self.ds_knob_chorus_mix_var = tk.BooleanVar(value=True)
        self.ds_knob_chorus_depth_var = tk.BooleanVar(value=False)
        self.ds_knob_chorus_rate_var = tk.BooleanVar(value=False)
        self.ds_knob_phaser_mix_var = tk.BooleanVar(value=False)
        self.ds_knob_phaser_depth_var = tk.BooleanVar(value=False)
        self.ds_knob_phaser_rate_var = tk.BooleanVar(value=False)
        self.ds_knob_phaser_frequency_var = tk.BooleanVar(value=False)
        self.ds_knob_phaser_feedback_var = tk.BooleanVar(value=False)
        self.ds_knob_convolution_mix_var = tk.BooleanVar(value=False)
        self.ds_knob_pitch_shift_var = tk.BooleanVar(value=False)
        self.ds_knob_pitch_shift_mix_var = tk.BooleanVar(value=False)
        self.ds_knob_wave_folder_drive_var = tk.BooleanVar(value=False)
        self.ds_knob_wave_folder_threshold_var = tk.BooleanVar(value=False)
        self.ds_knob_wave_shaper_drive_var = tk.BooleanVar(value=False)
        self.ds_knob_wave_shaper_boost_var = tk.BooleanVar(value=False)
        self.ds_knob_wave_shaper_output_var = tk.BooleanVar(value=False)
        self.ds_knob_stereo_width_var = tk.BooleanVar(value=False)
        self.ds_knob_bit_depth_var = tk.BooleanVar(value=False)
        self.ds_knob_bit_crusher_rate_var = tk.BooleanVar(value=False)
        self.ds_knob_bit_crusher_mix_var = tk.BooleanVar(value=False)

        ttk.Label(project, text="Instrument name").grid(row=0, column=0, sticky="w")
        ttk.Entry(project, textvariable=self.name_var, width=28).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Label(project, text="Output").grid(row=0, column=2, sticky="w")
        ttk.Entry(project, textvariable=self.output_var, width=46).grid(row=0, column=3, sticky="ew", padx=4)
        ttk.Button(project, text="Browse", command=self._browse_output).grid(row=0, column=4)
        ttk.Label(project, text="Record seconds").grid(row=1, column=0, sticky="w")
        ttk.Spinbox(project, textvariable=self.record_seconds_var, from_=0.5, to=30, increment=0.5, width=8).grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(project, text="Trim dB").grid(row=1, column=2, sticky="w")
        ttk.Spinbox(project, textvariable=self.threshold_var, from_=-80, to=-10, increment=1, width=8).grid(row=1, column=3, sticky="w", padx=4)
        ttk.Checkbutton(project, text="Normalise", variable=self.normalise_var).grid(row=1, column=4, sticky="w")
        ttk.Label(project, text="Sample format").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.OptionMenu(project, self.sample_format_var, self.sample_format_var.get(), "flac", "wav").grid(row=2, column=1, sticky="w", pady=(6, 0), padx=4)
        ttk.Button(project, text="New project", command=self._new_project).grid(row=2, column=2, sticky="w", pady=(6, 0), padx=4)
        ttk.Button(project, text="Open project", command=self._open_project_dialog).grid(row=2, column=3, sticky="w", pady=(6, 0), padx=4)
        ttk.Button(project, text="Save project", command=self._save_project_command).grid(row=2, column=4, sticky="w", pady=(6, 0), padx=4)
        ttk.Button(project, text="Review stray audio", command=self._review_stray_audio).grid(row=3, column=3, sticky="w", pady=(6, 0), padx=4)
        ttk.Checkbutton(project, text="Confirm before recording", variable=self.confirm_before_record_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Checkbutton(project, text="Play reference before pitched recording", variable=self.play_reference_before_record_var).grid(row=3, column=2, sticky="w", pady=(6, 0), padx=4)
        project.columnconfigure(3, weight=1)

        main_area = ttk.Frame(outer)
        main_area.pack(fill="both", expand=True, pady=8)
        tabs = ttk.Notebook(main_area)
        tabs.pack(side="left", fill="both", expand=True)
        self.pitched_tab = ttk.Frame(tabs, padding=8)
        self.decent_sampler_tab = ttk.Frame(tabs, padding=8)
        tabs.add(self.pitched_tab, text="Notes")
        tabs.add(self.decent_sampler_tab, text="DecentSampler")
        self._build_pitched_tab()
        self._build_decent_sampler_tab()
        self._bind_output_parameter_traces()
        self._build_recording_review_panel(main_area)

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Generate / update .dspreset", command=self._generate_preset).pack(side="left", padx=(0, 6))
        ttk.Button(bottom, text="Export .dsbundle", command=self._export_dsbundle).pack(side="left", padx=(0, 6))
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

        self.note_tree = ttk.Treeview(self.pitched_tab, columns=("note", "maps", "file", "action"), show="headings", height=14)
        self.note_tree.heading("note", text="Target note")
        self.note_tree.heading("maps", text="Maps to keys")
        self.note_tree.heading("file", text="Sample file")
        self.note_tree.heading("action", text="Action")
        self.note_tree.column("note", width=120, stretch=False)
        self.note_tree.column("maps", width=230, stretch=False)
        self.note_tree.column("file", width=340)
        self.note_tree.column("action", width=110, stretch=False, anchor="center")
        self.note_tree.tag_configure("generated", foreground="#666666")
        self.note_tree.pack(fill="both", expand=True, pady=8)
        self.note_tree.bind("<<TreeviewSelect>>", self._on_pitched_selection_changed)
        self.note_tree.bind("<Button-1>", self._on_note_tree_click, add="+")
        buttons = ttk.Frame(self.pitched_tab)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Record all missing", command=self._record_all_missing).pack(side="left")

    def _build_recording_review_panel(self, parent) -> None:
        review = ttk.LabelFrame(parent, text="Selected sample")
        review.pack(side="right", fill="y", padx=(8, 0))
        self.selected_sample_title_var = tk.StringVar(value="Select a note")
        ttk.Label(review, textvariable=self.selected_sample_title_var, wraplength=260, justify="left", font=("TkDefaultFont", 10, "bold")).pack(fill="x", padx=8, pady=(8, 4))
        action_row = ttk.Frame(review)
        action_row.pack(fill="x", padx=8, pady=(0, 6))
        self.panel_action_buttons = []
        for text, command in (
            ("Play selected reference", self._play_selected_reference),
            ("Record selected sample", self._record_selected_note),
        ):
            button = ttk.Button(action_row, text=text, command=command)
            button.pack(side="left", fill="x", expand=True, padx=(0, 4))
            self.panel_action_buttons.append(button)
        self.recording_review_status_var = tk.StringVar(value="No audio loaded.")
        ttk.Label(review, textvariable=self.recording_review_status_var, wraplength=260, justify="left").pack(fill="x", padx=8, pady=(2, 6))

        self.review_canvas_width = 260
        self.review_canvas_height = 120
        self.recording_review_canvas = tk.Canvas(review, width=self.review_canvas_width, height=self.review_canvas_height, bg="#101010", highlightthickness=1, highlightbackground="#666666")
        self.recording_review_canvas.pack(fill="x", padx=8, pady=(0, 6))
        self.recording_review_canvas.bind("<Button-1>", self._set_review_trim_start_from_canvas)
        self.recording_review_canvas.bind("<Button-3>", self._set_review_trim_end_from_canvas)

        trim_row = ttk.Frame(review)
        trim_row.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(trim_row, text="Start").pack(side="left")
        self.recording_review_start_var = tk.IntVar(value=0)
        self.recording_review_start_spinbox = ttk.Spinbox(trim_row, textvariable=self.recording_review_start_var, from_=0, to=0, increment=1, width=8, command=self._on_review_trim_fields_changed)
        self.recording_review_start_spinbox.pack(side="left", padx=(4, 8))
        ttk.Label(trim_row, text="End").pack(side="left")
        self.recording_review_end_var = tk.IntVar(value=0)
        self.recording_review_end_spinbox = ttk.Spinbox(trim_row, textvariable=self.recording_review_end_var, from_=0, to=0, increment=1, width=8, command=self._on_review_trim_fields_changed)
        self.recording_review_end_spinbox.pack(side="left", padx=4)
        self.recording_review_start_var.trace_add("write", lambda *_: self._on_review_trim_fields_changed())
        self.recording_review_end_var.trace_add("write", lambda *_: self._on_review_trim_fields_changed())

        ttk.Label(review, text="Left-click waveform to set start; right-click to set end.", foreground="#666666", wraplength=260, justify="left").pack(fill="x", padx=8, pady=(0, 8))

        ttk.Label(review, text="Takes / round-robin slots will live here.", foreground="#666666", wraplength=260, justify="left").pack(fill="x", padx=8, pady=(0, 8))
        self.recording_review_buttons = []
        for text, command in (
            ("Play full", self._play_review_full),
            ("Play selection", self._play_review_selection),
            ("Keep selection", self._keep_review_recording),
            ("Reset from backup", self._reset_review_recording),
        ):
            button = ttk.Button(review, text=text, command=command)
            button.pack(fill="x", padx=8, pady=(0, 4))
            self.recording_review_buttons.append(button)
        self.recording_review_reset_button = self.recording_review_buttons[-1]
        self._set_review_controls_enabled(False)
        self._set_panel_action_controls_enabled(False, False)

    def _set_review_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        if hasattr(self, "recording_review_start_spinbox"):
            self.recording_review_start_spinbox.configure(state=state)
        if hasattr(self, "recording_review_end_spinbox"):
            self.recording_review_end_spinbox.configure(state=state)
        for button in getattr(self, "recording_review_buttons", []):
            button.configure(state=state)

    def _set_panel_action_controls_enabled(self, can_play_reference: bool, can_record: bool) -> None:
        if not hasattr(self, "panel_action_buttons"):
            return
        self.panel_action_buttons[0].configure(state="normal" if can_play_reference else "disabled")
        self.panel_action_buttons[1].configure(state="normal" if can_record else "disabled")

    def _build_decent_sampler_tab(self) -> None:
        ds_tabs = ttk.Notebook(self.decent_sampler_tab)
        ds_tabs.pack(fill="both", expand=True)
        basics_tab = ttk.Frame(ds_tabs, padding=8)
        tone_tab = ttk.Frame(ds_tabs, padding=8)
        space_tab = ttk.Frame(ds_tabs, padding=8)
        shape_tab = ttk.Frame(ds_tabs, padding=8)
        ui_tab = ttk.Frame(ds_tabs, padding=8)
        mapping_tab = ttk.Frame(ds_tabs, padding=8)
        ds_tabs.add(basics_tab, text="Basics / Export")
        ds_tabs.add(tone_tab, text="Tone")
        ds_tabs.add(space_tab, text="Space")
        ds_tabs.add(shape_tab, text="Shape")
        ds_tabs.add(ui_tab, text="UI Preview")
        ds_tabs.add(mapping_tab, text="Mapping")

        export = ttk.LabelFrame(basics_tab, text="DecentSampler output")
        export.pack(fill="x")
        ttk.Checkbutton(export, text="Loop samples by default", variable=self.loop_enabled_var, command=self._on_output_parameter_changed).grid(row=0, column=0, sticky="w", padx=6, pady=6)

        loop = ttk.LabelFrame(basics_tab, text="Fallback/default loop points")
        loop.pack(fill="x", pady=(10, 0))
        ttk.Label(loop, text="start sample").pack(side="left", padx=(6, 2), pady=6)
        ttk.Entry(loop, textvariable=self.loop_start_var, width=10).pack(side="left", padx=(0, 10), pady=6)
        ttk.Label(loop, text="end sample").pack(side="left", padx=(0, 2), pady=6)
        ttk.Entry(loop, textvariable=self.loop_end_var, width=10).pack(side="left", padx=(0, 10), pady=6)
        ttk.Label(loop, text="crossfade").pack(side="left", padx=(0, 2), pady=6)
        ttk.Spinbox(loop, textvariable=self.loop_crossfade_var, from_=0, to=60000, increment=10, width=8).pack(side="left", padx=(0, 10), pady=6)
        ttk.OptionMenu(loop, self.loop_crossfade_mode_var, self.loop_crossfade_mode_var.get(), "equal_power", "linear").pack(side="left", padx=(0, 10), pady=6)
        ttk.Button(loop, text="Use first WAV marker", command=self._import_first_wav_loop_marker).pack(side="left", padx=(0, 6), pady=6)

        envelope = ttk.LabelFrame(basics_tab, text="Amp envelope")
        envelope.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(envelope, text="Enable ADSR", variable=self.amp_env_enabled_var, command=self._on_output_parameter_changed).pack(side="left", padx=6, pady=6)
        ttk.Label(envelope, text="attack").pack(side="left", padx=(6, 2), pady=6)
        ttk.Spinbox(envelope, textvariable=self.amp_attack_var, from_=0, to=10, increment=0.01, width=7).pack(side="left", padx=(0, 6), pady=6)
        ttk.Label(envelope, text="decay").pack(side="left", padx=(0, 2), pady=6)
        ttk.Spinbox(envelope, textvariable=self.amp_decay_var, from_=0, to=25, increment=0.01, width=7).pack(side="left", padx=(0, 6), pady=6)
        ttk.Label(envelope, text="sustain").pack(side="left", padx=(0, 2), pady=6)
        ttk.Spinbox(envelope, textvariable=self.amp_sustain_var, from_=0, to=1, increment=0.05, width=6).pack(side="left", padx=(0, 6), pady=6)
        ttk.Label(envelope, text="release").pack(side="left", padx=(0, 2), pady=6)
        ttk.Spinbox(envelope, textvariable=self.amp_release_var, from_=0, to=25, increment=0.05, width=7).pack(side="left", padx=(0, 6), pady=6)
        ttk.Checkbutton(envelope, text="K", variable=self.ds_knob_amp_env_var, command=self._on_output_parameter_changed).pack(side="left", padx=(4, 6), pady=6)
        ttk.Button(envelope, text="defaults", command=lambda: self._set_effect_defaults("amp_env")).pack(side="left", padx=(0, 6), pady=6)

        def make_effects(parent: ttk.Frame, title: str) -> ttk.LabelFrame:
            effects = ttk.LabelFrame(parent, text=title)
            effects.pack(fill="x")
            ttk.Label(effects, text="Effect").grid(row=0, column=0, sticky="w", padx=6, pady=(3, 2))
            ttk.Label(effects, text="Parameters  (K = knob included in DS display)").grid(row=0, column=1, sticky="w", padx=6, pady=(3, 2))
            ttk.Label(effects, text="Defaults").grid(row=0, column=2, sticky="w", padx=6, pady=(3, 2))
            effects.columnconfigure(1, weight=1)
            return effects

        def params_frame(parent: ttk.LabelFrame, row: int) -> ttk.Frame:
            frame = ttk.Frame(parent)
            frame.grid(row=row, column=1, sticky="ew", padx=6, pady=2)
            return frame

        def title_check(parent: ttk.LabelFrame, row: int, text: str, variable: tk.BooleanVar) -> None:
            ttk.Checkbutton(parent, text=text, variable=variable, command=self._on_output_parameter_changed).grid(row=row, column=0, sticky="w", padx=6, pady=2)

        def defaults_button(parent: ttk.LabelFrame, row: int, group: str) -> None:
            ttk.Button(parent, text="defaults", command=lambda: self._set_effect_defaults(group)).grid(row=row, column=2, sticky="w", padx=6, pady=2)

        def param_label(parent: ttk.Frame, text: str) -> None:
            ttk.Label(parent, text=text).pack(side="left", padx=(0, 2))

        def spin_param(parent: ttk.Frame, text: str, variable, from_: float, to: float, increment: float, width: int = 6, k_var: tk.BooleanVar | None = None) -> None:
            param_label(parent, text)
            ttk.Spinbox(parent, textvariable=variable, from_=from_, to=to, increment=increment, width=width).pack(side="left", padx=(0, 3))
            if k_var is not None:
                ttk.Checkbutton(parent, text="K", variable=k_var, command=self._on_output_parameter_changed).pack(side="left", padx=(0, 10))
            else:
                ttk.Label(parent, text="").pack(side="left", padx=(0, 10))

        tone = make_effects(tone_tab, "Tone effects")
        row = 1
        title_check(tone, row, "Filter", self.lowpass_enabled_var)
        frame = params_frame(tone, row)
        ttk.OptionMenu(frame, self.filter_type_var, self.filter_type_var.get(), "lowpass", "lowpass_1pl", "lowpass_4pl", "bandpass", "highpass").pack(side="left", padx=(0, 10))
        spin_param(frame, "freq", self.lowpass_frequency_var, 60, 22000, 100, width=8, k_var=self.ds_knob_tone_var)
        spin_param(frame, "res", self.filter_resonance_var, 0.001, 5.0, 0.1, k_var=self.ds_knob_filter_resonance_var)
        defaults_button(tone, row, "filter")
        row += 1
        title_check(tone, row, "Notch", self.notch_enabled_var)
        frame = params_frame(tone, row)
        spin_param(frame, "freq", self.notch_frequency_var, 60, 22000, 100, width=8, k_var=self.ds_knob_notch_frequency_var)
        spin_param(frame, "Q", self.notch_q_var, 0.01, 18.0, 0.1, k_var=self.ds_knob_notch_q_var)
        defaults_button(tone, row, "eq")
        row += 1
        title_check(tone, row, "Peak", self.peak_enabled_var)
        frame = params_frame(tone, row)
        spin_param(frame, "freq", self.peak_frequency_var, 60, 22000, 100, width=8, k_var=self.ds_knob_peak_frequency_var)
        spin_param(frame, "Q", self.peak_q_var, 0.01, 18.0, 0.1, k_var=self.ds_knob_peak_q_var)
        spin_param(frame, "gain", self.peak_gain_var, 0.0, 2.0, 0.1, k_var=self.ds_knob_peak_gain_var)
        defaults_button(tone, row, "eq")
        row += 1
        title_check(tone, row, "Gain", self.gain_enabled_var)
        frame = params_frame(tone, row)
        spin_param(frame, "dB", self.gain_level_var, -99, 24, 1, k_var=self.ds_knob_gain_level_var)
        defaults_button(tone, row, "gain")

        space = make_effects(space_tab, "Space effects")
        row = 1
        title_check(space, row, "Reverb", self.reverb_enabled_var)
        frame = params_frame(space, row)
        spin_param(frame, "wet", self.reverb_wet_level_var, 0.0, 1.0, 0.05, k_var=self.ds_knob_reverb_wet_var)
        spin_param(frame, "room", self.reverb_room_size_var, 0.0, 1.0, 0.05, k_var=self.ds_knob_reverb_room_var)
        spin_param(frame, "damping", self.reverb_damping_var, 0.0, 1.0, 0.05, k_var=self.ds_knob_reverb_damping_var)
        defaults_button(space, row, "reverb")
        row += 1
        title_check(space, row, "Delay", self.delay_enabled_var)
        frame = params_frame(space, row)
        spin_param(frame, "time", self.delay_time_var, 0.0, 20.0, 0.05, k_var=self.ds_knob_delay_time_var)
        spin_param(frame, "offset", self.delay_stereo_offset_var, -10.0, 10.0, 0.05, k_var=self.ds_knob_delay_stereo_offset_var)
        spin_param(frame, "feedback", self.delay_feedback_var, 0.0, 1.0, 0.05, k_var=self.ds_knob_delay_feedback_var)
        spin_param(frame, "wet", self.delay_wet_level_var, 0.0, 1.0, 0.05, k_var=self.ds_knob_delay_wet_var)
        defaults_button(space, row, "delay")
        row += 1
        title_check(space, row, "Chorus", self.chorus_enabled_var)
        frame = params_frame(space, row)
        spin_param(frame, "mix", self.chorus_mix_var, 0.0, 1.0, 0.05, k_var=self.ds_knob_chorus_mix_var)
        spin_param(frame, "depth", self.chorus_mod_depth_var, 0.0, 1.0, 0.05, k_var=self.ds_knob_chorus_depth_var)
        spin_param(frame, "rate", self.chorus_mod_rate_var, 0.0, 10.0, 0.05, k_var=self.ds_knob_chorus_rate_var)
        defaults_button(space, row, "chorus")
        row += 1
        title_check(space, row, "Phaser", self.phaser_enabled_var)
        frame = params_frame(space, row)
        spin_param(frame, "mix", self.phaser_mix_var, 0.0, 1.0, 0.05, k_var=self.ds_knob_phaser_mix_var)
        spin_param(frame, "depth", self.phaser_mod_depth_var, 0.0, 1.0, 0.05, k_var=self.ds_knob_phaser_depth_var)
        spin_param(frame, "rate", self.phaser_mod_rate_var, 0.0, 10.0, 0.05, k_var=self.ds_knob_phaser_rate_var)
        spin_param(frame, "freq", self.phaser_center_frequency_var, 0.0, 22000, 50, width=8, k_var=self.ds_knob_phaser_frequency_var)
        spin_param(frame, "feedback", self.phaser_feedback_var, 0.0, 1.0, 0.05, k_var=self.ds_knob_phaser_feedback_var)
        defaults_button(space, row, "modulation")
        row += 1
        title_check(space, row, "Convolution / IR", self.convolution_enabled_var)
        frame = params_frame(space, row)
        ttk.Entry(frame, textvariable=self.reverb_ir_var, width=30).pack(side="left", padx=(0, 10))
        spin_param(frame, "mix", self.reverb_mix_var, 0.0, 1.0, 0.05, k_var=self.ds_knob_convolution_mix_var)
        defaults_button(space, row, "convolution")

        shape = make_effects(shape_tab, "Shape effects")
        row = 1
        title_check(shape, row, "Pitch shift", self.pitch_shift_enabled_var)
        frame = params_frame(shape, row)
        spin_param(frame, "semitones", self.pitch_shift_var, -24, 24, 1, k_var=self.ds_knob_pitch_shift_var)
        spin_param(frame, "mix", self.pitch_shift_mix_var, 0.0, 1.0, 0.05, k_var=self.ds_knob_pitch_shift_mix_var)
        defaults_button(shape, row, "modulation")
        row += 1
        title_check(shape, row, "Wave folder", self.wave_folder_enabled_var)
        frame = params_frame(shape, row)
        spin_param(frame, "drive", self.wave_folder_drive_var, 1, 100, 1, k_var=self.ds_knob_wave_folder_drive_var)
        spin_param(frame, "threshold", self.wave_folder_threshold_var, 0, 10, 0.1, k_var=self.ds_knob_wave_folder_threshold_var)
        defaults_button(shape, row, "wave_folder")
        row += 1
        title_check(shape, row, "Wave shaper", self.wave_shaper_enabled_var)
        frame = params_frame(shape, row)
        spin_param(frame, "drive", self.wave_shaper_drive_var, 1, 1000, 1, k_var=self.ds_knob_wave_shaper_drive_var)
        spin_param(frame, "boost", self.wave_shaper_drive_boost_var, 0, 1, 0.05, k_var=self.ds_knob_wave_shaper_boost_var)
        spin_param(frame, "out", self.wave_shaper_output_level_var, 0, 1, 0.05, k_var=self.ds_knob_wave_shaper_output_var)
        ttk.Checkbutton(frame, text="high quality", variable=self.wave_shaper_high_quality_var, command=self._on_output_parameter_changed).pack(side="left", padx=(0, 10))
        defaults_button(shape, row, "wave_shaper")
        row += 1
        title_check(shape, row, "Stereo simulator", self.stereo_simulator_enabled_var)
        frame = params_frame(shape, row)
        ttk.OptionMenu(frame, self.stereo_simulator_algorithm_var, self.stereo_simulator_algorithm_var.get(), "adt", "lauridsen", "schroeder").pack(side="left", padx=(0, 10))
        spin_param(frame, "width", self.stereo_simulator_width_var, 0, 1, 0.05, k_var=self.ds_knob_stereo_width_var)
        spin_param(frame, "delay", self.stereo_simulator_delay_time_var, 0.001, 0.030, 0.001, width=7)
        spin_param(frame, "rate", self.stereo_simulator_mod_rate_var, 0.1, 10.0, 0.1)
        spin_param(frame, "depth", self.stereo_simulator_mod_depth_var, 0.0, 1.0, 0.05)
        defaults_button(shape, row, "stereo_simulator")
        row += 1
        title_check(shape, row, "Bit crusher", self.bit_crusher_enabled_var)
        frame = params_frame(shape, row)
        spin_param(frame, "bits", self.bit_crusher_bit_depth_var, 1, 24, 1, k_var=self.ds_knob_bit_depth_var)
        spin_param(frame, "rate div", self.bit_crusher_sample_rate_reduction_var, 1, 32, 1, k_var=self.ds_knob_bit_crusher_rate_var)
        spin_param(frame, "mix", self.bit_crusher_mix_var, 0, 1, 0.05, k_var=self.ds_knob_bit_crusher_mix_var)
        defaults_button(shape, row, "bit_crusher")

        self.ui_preview = DecentSamplerUiPreview(ui_tab, self)

        mapping = ttk.LabelFrame(mapping_tab, text="Effective exported sample mapping")
        mapping.pack(fill="both", expand=True)
        self.export_tree = ttk.Treeview(mapping, columns=("source", "keys", "root", "mode", "loop"), show="headings", height=10)
        self.export_tree.heading("source", text="Source audio")
        self.export_tree.heading("keys", text="Plays on keys")
        self.export_tree.heading("root", text="Root note")
        self.export_tree.heading("mode", text="Mode")
        self.export_tree.heading("loop", text="Loop")
        self.export_tree.column("source", width=250)
        self.export_tree.column("keys", width=220)
        self.export_tree.column("root", width=150)
        self.export_tree.column("mode", width=80, stretch=False)
        self.export_tree.column("loop", width=150, stretch=False)
        self.export_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.export_tree.bind("<Double-1>", self._edit_export_row_from_double_click)
        mapping_buttons = ttk.Frame(mapping)
        mapping_buttons.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(mapping_buttons, text="Edit plays-on keys…", command=self._edit_selected_sample_mapping).pack(side="left", padx=(0, 6))
        ttk.Button(mapping_buttons, text="Edit selected audio loop…", command=self._edit_selected_sample_loop).pack(side="left")

        notes = ttk.LabelFrame(mapping_tab, text="Notes")
        notes.pack(fill="x", pady=(10, 0))
        ttk.Label(
            notes,
            text=(
                "DecentSampler settings are split into sub-tabs. Loop controls here are fallback/default values; "
                "double-click Source audio/Plays on keys to edit key mapping; double-click the other columns to edit loop points. "
                "per-audio-file loop edits are shown in the mapping table and take priority during export. "
                "Generated bridge samples are marked generated in the mapping table and saved under Samples/generated."
            ),
            wraplength=820,
            justify="left",
        ).pack(anchor="w", padx=6, pady=6)

    def _normalise_ui_layout(self, raw_layout: object) -> dict[str, dict[str, int]]:
        return normalise_ui_layout(raw_layout)

    def _redraw_ui_preview(self) -> None:
        if self.ui_preview is not None:
            self.ui_preview.redraw()

    def _visible_ui_controls(self) -> list[dict[str, object]]:
        if self.ui_preview is None:
            return []
        return self.ui_preview.visible_controls()

    def _bind_output_parameter_traces(self) -> None:
        output_vars = [
            self.loop_enabled_var,
            self.loop_start_var,
            self.loop_end_var,
            self.loop_crossfade_var,
            self.loop_crossfade_mode_var,
            self.amp_env_enabled_var,
            self.amp_attack_var,
            self.amp_decay_var,
            self.amp_sustain_var,
            self.amp_release_var,
            self.ds_knob_amp_env_var,
            self.delay_enabled_var,
            self.delay_time_var,
            self.delay_stereo_offset_var,
            self.delay_feedback_var,
            self.delay_wet_level_var,
            self.lowpass_enabled_var,
            self.filter_type_var,
            self.lowpass_frequency_var,
            self.filter_resonance_var,
            self.notch_enabled_var,
            self.notch_frequency_var,
            self.notch_q_var,
            self.peak_enabled_var,
            self.peak_frequency_var,
            self.peak_q_var,
            self.peak_gain_var,
            self.gain_enabled_var,
            self.gain_level_var,
            self.reverb_enabled_var,
            self.reverb_room_size_var,
            self.reverb_damping_var,
            self.reverb_wet_level_var,
            self.chorus_enabled_var,
            self.chorus_mix_var,
            self.chorus_mod_depth_var,
            self.chorus_mod_rate_var,
            self.phaser_enabled_var,
            self.phaser_mix_var,
            self.phaser_mod_depth_var,
            self.phaser_mod_rate_var,
            self.phaser_center_frequency_var,
            self.phaser_feedback_var,
            self.convolution_enabled_var,
            self.reverb_ir_var,
            self.reverb_mix_var,
            self.pitch_shift_enabled_var,
            self.pitch_shift_var,
            self.pitch_shift_mix_var,
            self.wave_folder_enabled_var,
            self.wave_folder_drive_var,
            self.wave_folder_threshold_var,
            self.wave_shaper_enabled_var,
            self.wave_shaper_drive_var,
            self.wave_shaper_drive_boost_var,
            self.wave_shaper_output_level_var,
            self.wave_shaper_high_quality_var,
            self.stereo_simulator_enabled_var,
            self.stereo_simulator_algorithm_var,
            self.stereo_simulator_width_var,
            self.stereo_simulator_delay_time_var,
            self.stereo_simulator_mod_rate_var,
            self.stereo_simulator_mod_depth_var,
            self.bit_crusher_enabled_var,
            self.bit_crusher_bit_depth_var,
            self.bit_crusher_sample_rate_reduction_var,
            self.bit_crusher_mix_var,
            self.ds_knob_tone_var,
            self.ds_knob_filter_resonance_var,
            self.ds_knob_notch_frequency_var,
            self.ds_knob_notch_q_var,
            self.ds_knob_peak_frequency_var,
            self.ds_knob_peak_q_var,
            self.ds_knob_peak_gain_var,
            self.ds_knob_gain_level_var,
            self.ds_knob_reverb_wet_var,
            self.ds_knob_reverb_room_var,
            self.ds_knob_reverb_damping_var,
            self.ds_knob_delay_wet_var,
            self.ds_knob_delay_time_var,
            self.ds_knob_delay_stereo_offset_var,
            self.ds_knob_delay_feedback_var,
            self.ds_knob_chorus_mix_var,
            self.ds_knob_chorus_depth_var,
            self.ds_knob_chorus_rate_var,
            self.ds_knob_phaser_mix_var,
            self.ds_knob_phaser_depth_var,
            self.ds_knob_phaser_rate_var,
            self.ds_knob_phaser_frequency_var,
            self.ds_knob_phaser_feedback_var,
            self.ds_knob_convolution_mix_var,
            self.ds_knob_pitch_shift_var,
            self.ds_knob_pitch_shift_mix_var,
            self.ds_knob_wave_folder_drive_var,
            self.ds_knob_wave_folder_threshold_var,
            self.ds_knob_wave_shaper_drive_var,
            self.ds_knob_wave_shaper_boost_var,
            self.ds_knob_wave_shaper_output_var,
            self.ds_knob_stereo_width_var,
            self.ds_knob_bit_depth_var,
            self.ds_knob_bit_crusher_rate_var,
            self.ds_knob_bit_crusher_mix_var,
        ]
        for var in output_vars:
            var.trace_add("write", lambda *_args: self._schedule_output_parameter_changed())

    def _schedule_output_parameter_changed(self) -> None:
        if self._output_update_after_id is not None:
            self.after_cancel(self._output_update_after_id)
        self._output_update_after_id = self.after(600, self._on_output_parameter_changed)

    def _set_effect_defaults(self, effect_group: str) -> None:
        if effect_group == "filter":
            self.filter_type_var.set("lowpass_4pl")
            self.lowpass_frequency_var.set(22000.0)
            self.filter_resonance_var.set(0.7)
        elif effect_group == "eq":
            self.notch_frequency_var.set(10000.0)
            self.notch_q_var.set(0.7)
            self.peak_frequency_var.set(10000.0)
            self.peak_q_var.set(0.7)
            self.peak_gain_var.set(1.0)
        elif effect_group == "gain":
            self.gain_level_var.set(0.0)
        elif effect_group == "reverb":
            self.reverb_room_size_var.set(0.7)
            self.reverb_damping_var.set(0.3)
            self.reverb_wet_level_var.set(0.5)
        elif effect_group == "delay":
            self.delay_time_var.set(0.7)
            self.delay_stereo_offset_var.set(0.0)
            self.delay_feedback_var.set(0.2)
            self.delay_wet_level_var.set(0.5)
        elif effect_group == "chorus":
            self.chorus_mix_var.set(0.5)
            self.chorus_mod_depth_var.set(0.2)
            self.chorus_mod_rate_var.set(0.2)
        elif effect_group == "modulation":
            self.phaser_mix_var.set(0.5)
            self.phaser_mod_depth_var.set(0.2)
            self.phaser_mod_rate_var.set(0.2)
            self.phaser_center_frequency_var.set(400.0)
            self.phaser_feedback_var.set(0.7)
            self.pitch_shift_var.set(0.0)
            self.pitch_shift_mix_var.set(0.5)
        elif effect_group == "convolution":
            self.reverb_mix_var.set(0.5)
        elif effect_group == "wave_folder":
            self.wave_folder_drive_var.set(1.0)
            self.wave_folder_threshold_var.set(0.25)
        elif effect_group == "wave_shaper":
            self.wave_shaper_drive_var.set(1.0)
            self.wave_shaper_drive_boost_var.set(1.0)
            self.wave_shaper_output_level_var.set(0.1)
            self.wave_shaper_high_quality_var.set(True)
        elif effect_group == "stereo_simulator":
            self.stereo_simulator_algorithm_var.set("adt")
            self.stereo_simulator_width_var.set(0.5)
            self.stereo_simulator_delay_time_var.set(0.005)
            self.stereo_simulator_mod_rate_var.set(0.5)
            self.stereo_simulator_mod_depth_var.set(0.3)
        elif effect_group == "bit_crusher":
            self.bit_crusher_bit_depth_var.set(8)
            self.bit_crusher_sample_rate_reduction_var.set(4)
            self.bit_crusher_mix_var.set(1.0)
        elif effect_group == "amp_env":
            self.amp_attack_var.set(0.01)
            self.amp_decay_var.set(0.0)
            self.amp_sustain_var.set(1.0)
            self.amp_release_var.set(0.8)

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
        suffix = ".flac" if self.sample_format_var.get().lower() == "flac" else ".wav"
        return self._instrument_dir() / "Samples" / f"{slugify(self.name_var.get())}_{label}{suffix}"

    def _backup_path_for_sample(self, path: Path) -> Path:
        return path.parent / ".samplesmith-backups" / f"{path.stem}.original{path.suffix}"

    def _ensure_sample_backup(self, path: Path) -> Path | None:
        if not path.exists():
            return None
        backup = self._backup_path_for_sample(path)
        if not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            self._log(f"Saved original backup: {backup.relative_to(self._instrument_dir()) if backup.is_relative_to(self._instrument_dir()) else backup}")
        return backup

    def _restore_sample_backup(self, path: Path) -> bool:
        backup = self._backup_path_for_sample(path)
        if not backup.exists():
            messagebox.showinfo("SampleSmith", "No original backup exists for this audio file yet.")
            return False
        shutil.copy2(backup, path)
        self._log(f"Restored original audio: {path.name}")
        return True

    def _write_reviewed_audio(self, path: Path, audio, sample_rate: int | None = None) -> None:
        self._ensure_sample_backup(path)
        self._audio().write_audio(path, audio, sample_rate=sample_rate)

    def _bridge_sample_path(self, target_note: int, low_root: int, high_root: int) -> Path:
        target = midi_to_name(target_note).replace("#", "sharp")
        low = midi_to_name(low_root).replace("#", "sharp")
        high = midi_to_name(high_root).replace("#", "sharp")
        suffix = ".flac" if self.sample_format_var.get().lower() == "flac" else ".wav"
        return self._instrument_dir() / "Samples" / "generated" / f"bridge_note_{target_note:03d}_{target}_from_{low}_{high}{suffix}"

    def _browse_output(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.output_var.get() or str(Path.cwd()))
        if chosen:
            self.output_var.set(chosen)

    def _default_project_path(self) -> Path:
        return self._instrument_dir() / f"{slugify(self.name_var.get())}.samplesmith.json"

    def _project_path_for_name(self, name: str, output: str | None = None) -> Path:
        output_root = Path(output or self.output_var.get()).expanduser()
        slug = slugify(name)
        return output_root / slug / f"{slug}.samplesmith.json"

    def _project_data(self) -> dict[str, object]:
        return {
            "version": 2,
            "note_convention": "decent_sampler_screen_keys",
            "name": self.name_var.get(),
            "output": self.output_var.get(),
            "sample_rate": self.sample_rate_var.get(),
            "sample_format": self.sample_format_var.get(),
            "record_seconds": self.record_seconds_var.get(),
            "trim_threshold_db": self.threshold_var.get(),
            "normalise": self.normalise_var.get(),
            "confirm_before_record": self.confirm_before_record_var.get(),
            "play_reference_before_record": self.play_reference_before_record_var.get(),
            "loop_enabled": self.loop_enabled_var.get(),
            "loop_start": self.loop_start_var.get(),
            "loop_end": self.loop_end_var.get(),
            "loop_crossfade": self.loop_crossfade_var.get(),
            "loop_crossfade_mode": self.loop_crossfade_mode_var.get(),
            "amp_env_enabled": self.amp_env_enabled_var.get(),
            "amp_attack": self.amp_attack_var.get(),
            "amp_decay": self.amp_decay_var.get(),
            "amp_sustain": self.amp_sustain_var.get(),
            "amp_release": self.amp_release_var.get(),
            "ds_knob_amp_env": self.ds_knob_amp_env_var.get(),
            "delay_enabled": self.delay_enabled_var.get(),
            "delay_time": self.delay_time_var.get(),
            "delay_stereo_offset": self.delay_stereo_offset_var.get(),
            "delay_feedback": self.delay_feedback_var.get(),
            "delay_wet_level": self.delay_wet_level_var.get(),
            "lowpass_enabled": self.lowpass_enabled_var.get(),
            "filter_type": self.filter_type_var.get(),
            "lowpass_frequency": self.lowpass_frequency_var.get(),
            "filter_resonance": self.filter_resonance_var.get(),
            "notch_enabled": self.notch_enabled_var.get(),
            "notch_frequency": self.notch_frequency_var.get(),
            "notch_q": self.notch_q_var.get(),
            "peak_enabled": self.peak_enabled_var.get(),
            "peak_frequency": self.peak_frequency_var.get(),
            "peak_q": self.peak_q_var.get(),
            "peak_gain": self.peak_gain_var.get(),
            "gain_enabled": self.gain_enabled_var.get(),
            "gain_level": self.gain_level_var.get(),
            "reverb_enabled": self.reverb_enabled_var.get(),
            "reverb_room_size": self.reverb_room_size_var.get(),
            "reverb_damping": self.reverb_damping_var.get(),
            "reverb_wet_level": self.reverb_wet_level_var.get(),
            "chorus_enabled": self.chorus_enabled_var.get(),
            "chorus_mix": self.chorus_mix_var.get(),
            "chorus_mod_depth": self.chorus_mod_depth_var.get(),
            "chorus_mod_rate": self.chorus_mod_rate_var.get(),
            "phaser_enabled": self.phaser_enabled_var.get(),
            "phaser_mix": self.phaser_mix_var.get(),
            "phaser_mod_depth": self.phaser_mod_depth_var.get(),
            "phaser_mod_rate": self.phaser_mod_rate_var.get(),
            "phaser_center_frequency": self.phaser_center_frequency_var.get(),
            "phaser_feedback": self.phaser_feedback_var.get(),
            "convolution_enabled": self.convolution_enabled_var.get(),
            "reverb_ir_file": self.reverb_ir_var.get(),
            "reverb_mix": self.reverb_mix_var.get(),
            "pitch_shift_enabled": self.pitch_shift_enabled_var.get(),
            "pitch_shift": self.pitch_shift_var.get(),
            "pitch_shift_mix": self.pitch_shift_mix_var.get(),
            "wave_folder_enabled": self.wave_folder_enabled_var.get(),
            "wave_folder_drive": self.wave_folder_drive_var.get(),
            "wave_folder_threshold": self.wave_folder_threshold_var.get(),
            "wave_shaper_enabled": self.wave_shaper_enabled_var.get(),
            "wave_shaper_drive": self.wave_shaper_drive_var.get(),
            "wave_shaper_drive_boost": self.wave_shaper_drive_boost_var.get(),
            "wave_shaper_output_level": self.wave_shaper_output_level_var.get(),
            "wave_shaper_high_quality": self.wave_shaper_high_quality_var.get(),
            "stereo_simulator_enabled": self.stereo_simulator_enabled_var.get(),
            "stereo_simulator_algorithm": self.stereo_simulator_algorithm_var.get(),
            "stereo_simulator_width": self.stereo_simulator_width_var.get(),
            "stereo_simulator_delay_time": self.stereo_simulator_delay_time_var.get(),
            "stereo_simulator_mod_rate": self.stereo_simulator_mod_rate_var.get(),
            "stereo_simulator_mod_depth": self.stereo_simulator_mod_depth_var.get(),
            "bit_crusher_enabled": self.bit_crusher_enabled_var.get(),
            "bit_crusher_bit_depth": self.bit_crusher_bit_depth_var.get(),
            "bit_crusher_sample_rate_reduction": self.bit_crusher_sample_rate_reduction_var.get(),
            "bit_crusher_mix": self.bit_crusher_mix_var.get(),
            "ds_knob_tone": self.ds_knob_tone_var.get(),
            "ds_knob_filter_resonance": self.ds_knob_filter_resonance_var.get(),
            "ds_knob_notch_frequency": self.ds_knob_notch_frequency_var.get(),
            "ds_knob_notch_q": self.ds_knob_notch_q_var.get(),
            "ds_knob_peak_frequency": self.ds_knob_peak_frequency_var.get(),
            "ds_knob_peak_q": self.ds_knob_peak_q_var.get(),
            "ds_knob_peak_gain": self.ds_knob_peak_gain_var.get(),
            "ds_knob_gain_level": self.ds_knob_gain_level_var.get(),
            "ds_knob_reverb_wet": self.ds_knob_reverb_wet_var.get(),
            "ds_knob_reverb_room": self.ds_knob_reverb_room_var.get(),
            "ds_knob_reverb_damping": self.ds_knob_reverb_damping_var.get(),
            "ds_knob_delay_wet": self.ds_knob_delay_wet_var.get(),
            "ds_knob_delay_time": self.ds_knob_delay_time_var.get(),
            "ds_knob_delay_stereo_offset": self.ds_knob_delay_stereo_offset_var.get(),
            "ds_knob_delay_feedback": self.ds_knob_delay_feedback_var.get(),
            "ds_knob_chorus_mix": self.ds_knob_chorus_mix_var.get(),
            "ds_knob_chorus_depth": self.ds_knob_chorus_depth_var.get(),
            "ds_knob_chorus_rate": self.ds_knob_chorus_rate_var.get(),
            "ds_knob_phaser_mix": self.ds_knob_phaser_mix_var.get(),
            "ds_knob_phaser_depth": self.ds_knob_phaser_depth_var.get(),
            "ds_knob_phaser_rate": self.ds_knob_phaser_rate_var.get(),
            "ds_knob_phaser_frequency": self.ds_knob_phaser_frequency_var.get(),
            "ds_knob_phaser_feedback": self.ds_knob_phaser_feedback_var.get(),
            "ds_knob_convolution_mix": self.ds_knob_convolution_mix_var.get(),
            "ds_knob_pitch_shift": self.ds_knob_pitch_shift_var.get(),
            "ds_knob_pitch_shift_mix": self.ds_knob_pitch_shift_mix_var.get(),
            "ds_knob_wave_folder_drive": self.ds_knob_wave_folder_drive_var.get(),
            "ds_knob_wave_folder_threshold": self.ds_knob_wave_folder_threshold_var.get(),
            "ds_knob_wave_shaper_drive": self.ds_knob_wave_shaper_drive_var.get(),
            "ds_knob_wave_shaper_boost": self.ds_knob_wave_shaper_boost_var.get(),
            "ds_knob_wave_shaper_output": self.ds_knob_wave_shaper_output_var.get(),
            "ds_knob_stereo_width": self.ds_knob_stereo_width_var.get(),
            "ds_knob_bit_depth": self.ds_knob_bit_depth_var.get(),
            "ds_knob_bit_crusher_rate": self.ds_knob_bit_crusher_rate_var.get(),
            "ds_knob_bit_crusher_mix": self.ds_knob_bit_crusher_mix_var.get(),
            "low_note": self.low_note,
            "high_note": self.high_note,
            "step": self.step_var.get(),
            "samples": [sample.to_dict() for sample in self.samples],
            "ui_layout": self.ui_layout,
        }

    def _save_project(self, path: Path | None = None) -> Path:
        target = path or self.project_path or self._default_project_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self._project_data(), indent=2), encoding="utf-8")
        self.project_path = target
        self._remember_last_project(target)
        return target

    def _settings_path(self) -> Path:
        override = os.environ.get("SAMPLESMITH_SETTINGS_PATH")
        if override:
            return Path(override).expanduser()
        return Path.home() / ".samplesmith" / "settings.json"

    def _remember_last_project(self, path: Path) -> None:
        try:
            settings_path = self._settings_path()
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(json.dumps({"last_project": str(path.expanduser())}, indent=2), encoding="utf-8")
        except Exception as exc:
            self._log(f"Could not remember last project: {exc}")

    def _last_project_path(self) -> Path | None:
        try:
            settings_path = self._settings_path()
            if not settings_path.exists():
                return None
            value = json.loads(settings_path.read_text(encoding="utf-8")).get("last_project")
            if not value:
                return None
            path = Path(str(value)).expanduser()
            return path if path.exists() else None
        except Exception:
            return None

    def _open_last_project_if_available(self) -> None:
        if self.project_path is not None:
            return
        path = self._last_project_path()
        if path is None:
            return
        try:
            self._open_project(path, prompt_for_strays=False)
            self._log(f"Reopened last project: {path.name}")
        except Exception as exc:
            self._log(f"Could not reopen last project: {exc}")

    def _new_project_data(self) -> dict[str, object]:
        data = dict(self.blank_project_data)
        data["output"] = self.output_var.get()
        base_name = str(data.get("name", "NewInstrument") or "NewInstrument")
        name = base_name
        suffix = 2
        while self._project_path_for_name(name, str(data["output"])).exists():
            name = f"{base_name}{suffix}"
            suffix += 1
        data["name"] = name
        return data

    def _current_project_has_unsaved_changes(self) -> bool:
        current = self._project_data()
        if self.project_path is not None and self.project_path.exists():
            try:
                saved = json.loads(self.project_path.read_text(encoding="utf-8"))
                return current != saved
            except Exception:
                return True
        blank = dict(self.blank_project_data)
        blank["output"] = current.get("output", blank.get("output"))
        return current != blank

    def _confirm_replace_current_project(self, action: str) -> bool:
        if not self._current_project_has_unsaved_changes():
            return True
        choice = messagebox.askyesnocancel(
            "SampleSmith",
            f"Save the current project before {action}?\n\n"
            "Yes saves first. No discards unsaved changes. Cancel keeps the current project open.",
        )
        if choice is None:
            return False
        if choice is False:
            return True
        try:
            if self.project_path is None:
                return self._save_project_dialog() is not None
            saved = self._save_project()
            self._log(f"Saved project: {saved}")
            return True
        except Exception as exc:
            messagebox.showerror("SampleSmith", f"Could not save the current project:\n\n{exc}")
            return False

    def _new_project(self) -> None:
        if not self._confirm_replace_current_project("starting a new blank project"):
            return
        self._load_project_data(self._new_project_data(), None)
        self.log.delete("1.0", "end")
        self._log("Started new blank project.")

    def _save_project_dialog(self) -> Path | None:
        initial = self.project_path or self._default_project_path()
        chosen = filedialog.asksaveasfilename(
            initialdir=str(initial.parent),
            initialfile=initial.name,
            defaultextension=".samplesmith.json",
            filetypes=[("SampleSmith project", "*.samplesmith.json"), ("JSON", "*.json"), ("All files", "*.*")],
        )
        if not chosen:
            return None
        saved = self._save_project(Path(chosen))
        self._log(f"Saved project: {saved}")
        return saved

    def _save_project_command(self) -> Path | None:
        try:
            if self.project_path is None:
                return self._save_project_dialog()
            saved = self._save_project()
            self._log(f"Saved project: {saved}")
            return saved
        except Exception as exc:
            messagebox.showerror("SampleSmith", f"Could not save project:\n\n{exc}")
            return None

    @staticmethod
    def _guess_note_from_audio_filename(path: Path) -> str:
        stem = path.stem
        note_match = re.search(r"(?<![A-Za-z0-9])([A-Ga-g])([#b♯♭]?)(-?\d)(?![A-Za-z0-9])", stem)
        if note_match:
            letter = note_match.group(1).upper()
            accidental = note_match.group(2).replace("♯", "#").replace("♭", "b")
            octave = note_match.group(3)
            guessed = f"{letter}{accidental}{octave}"
            try:
                name_to_midi(guessed)
            except ValueError:
                pass
            else:
                return guessed
        number_match = re.search(r"(?i)(?:note|root|key|midi)[_-]?(\d{1,3})(?!\d)", stem)
        if number_match:
            note_number = int(number_match.group(1))
            if 0 <= note_number <= 127:
                return str(note_number)
        return ""

    def _stray_audio_candidates(self) -> list[Path]:
        roots = [self._instrument_dir(), self._instrument_dir() / "Samples"]
        if self.project_path is not None:
            roots.append(self.project_path.parent)
        seen_roots: set[Path] = set()
        seen_audio: set[Path] = set()
        known = {sample.path.resolve() for sample in self.samples if sample.path.exists()}
        strays: list[Path] = []
        for root in roots:
            root = root.expanduser()
            if not root.exists() or not root.is_dir():
                continue
            resolved_root = root.resolve()
            if resolved_root in seen_roots:
                continue
            seen_roots.add(resolved_root)
            audio_files = sorted(path for path in root.iterdir() if path.is_file() and path.suffix.lower() in {".wav", ".flac"})
            for audio_file in audio_files:
                resolved_audio = audio_file.resolve()
                if resolved_audio in known or resolved_audio in seen_audio:
                    continue
                seen_audio.add(resolved_audio)
                strays.append(audio_file)
        return strays

    def _review_stray_audio(self) -> None:
        strays = self._stray_audio_candidates()
        if not strays:
            self._log("No stray audio files found in this instrument/project folder.")
            messagebox.showinfo("SampleSmith", "No stray audio files found in this instrument/project folder.")
            return
        preview = "\n".join(str(path.relative_to(self._instrument_dir())) if path.is_relative_to(self._instrument_dir()) else str(path) for path in strays[:12])
        if len(strays) > 12:
            preview += f"\n… and {len(strays) - 12} more"
        if not messagebox.askyesno(
            "SampleSmith",
            "Found audio files in the project/instrument folders that are not in the current mapping.\n\n"
            f"{preview}\n\nReview and import any of these now?",
        ):
            self._log(f"Stray audio review skipped ({len(strays)} found).")
            return
        imported = 0
        for audio_path in strays:
            rel = str(audio_path.relative_to(self._instrument_dir())) if audio_path.is_relative_to(self._instrument_dir()) else str(audio_path)
            if not messagebox.askyesno("SampleSmith", f"Include this audio file in the project?\n\n{rel}"):
                continue
            note_text = simpledialog.askstring(
                "SampleSmith",
                "Enter its root note for pitched mapping (e.g. C4 or 72).\n"
                "Leave blank to skip this file.",
                initialvalue=self._guess_note_from_audio_filename(audio_path),
            )
            if note_text is None:
                continue
            note_text = note_text.strip()
            if note_text:
                try:
                    try:
                        root_note = int(note_text)
                    except ValueError:
                        root_note = name_to_midi(note_text)
                except ValueError as exc:
                    messagebox.showwarning("SampleSmith", f"Skipping {audio_path.name}: {exc}")
                    continue
                info = SampleInfo(path=audio_path, root_note=root_note, lo_note=root_note, hi_note=root_note, label=audio_path.stem, mode="pitched")
                self._upsert_sample(info)
                imported += 1
                self._log(f"Imported stray pitched audio: {audio_path.name} as {midi_to_name(root_note)}")
            else:
                self._log(f"Skipped stray audio without a root note: {audio_path.name}")
        if imported:
            self._rebuild_trees_from_project()
            preset = self._write_preset()
            self._auto_save_project()
            self._log(f"Imported {imported} stray audio file(s) and updated {preset.name}")
        else:
            self._log("No stray audio files imported.")

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
        if chosen and self._confirm_replace_current_project("opening another project"):
            self._open_project(Path(chosen))

    def _load_project_data(self, data: dict[str, object], project_path: Path | None) -> None:
        self.project_path = project_path
        self.name_var.set(str(data.get("name", "NewInstrument")))
        self.output_var.set(str(data.get("output", str(Path.cwd() / "samplesmith-projects"))))
        self.sample_rate_var.set(int(data.get("sample_rate", DEFAULT_SAMPLE_RATE)))
        sample_format = str(data.get("sample_format", "flac") or "flac").lower()
        self.sample_format_var.set(sample_format if sample_format in {"flac", "wav"} else "flac")
        self.record_seconds_var.set(float(data.get("record_seconds", 4.0)))
        self.threshold_var.set(float(data.get("trim_threshold_db", -45.0)))
        self.normalise_var.set(bool(data.get("normalise", True)))
        self.confirm_before_record_var.set(bool(data.get("confirm_before_record", False)))
        self.play_reference_before_record_var.set(bool(data.get("play_reference_before_record", True)))
        self.loop_enabled_var.set(bool(data.get("loop_enabled", False)))
        self.loop_start_var.set(str(data.get("loop_start", "") or ""))
        self.loop_end_var.set(str(data.get("loop_end", "") or ""))
        self.loop_crossfade_var.set(float(data.get("loop_crossfade", 0.0)))
        self.loop_crossfade_mode_var.set(str(data.get("loop_crossfade_mode", "equal_power")))
        self.amp_env_enabled_var.set(bool(data.get("amp_env_enabled", False)))
        self.amp_attack_var.set(float(data.get("amp_attack", 0.01)))
        self.amp_decay_var.set(float(data.get("amp_decay", 0.0)))
        self.amp_sustain_var.set(float(data.get("amp_sustain", 1.0)))
        self.amp_release_var.set(float(data.get("amp_release", 0.8)))
        self.ds_knob_amp_env_var.set(bool(data.get("ds_knob_amp_env", True)))
        self.delay_enabled_var.set(bool(data.get("delay_enabled", False)))
        self.delay_time_var.set(float(data.get("delay_time", 0.7)))
        self.delay_stereo_offset_var.set(float(data.get("delay_stereo_offset", 0.0)))
        self.delay_feedback_var.set(float(data.get("delay_feedback", 0.2)))
        self.delay_wet_level_var.set(float(data.get("delay_wet_level", 0.5)))
        self.lowpass_enabled_var.set(bool(data.get("lowpass_enabled", False)))
        self.filter_type_var.set(str(data.get("filter_type", "lowpass_4pl")))
        self.lowpass_frequency_var.set(float(data.get("lowpass_frequency", 22000.0)))
        self.filter_resonance_var.set(float(data.get("filter_resonance", 0.7)))
        self.notch_enabled_var.set(bool(data.get("notch_enabled", False)))
        self.notch_frequency_var.set(float(data.get("notch_frequency", 10000.0)))
        self.notch_q_var.set(float(data.get("notch_q", 0.7)))
        self.peak_enabled_var.set(bool(data.get("peak_enabled", False)))
        self.peak_frequency_var.set(float(data.get("peak_frequency", 10000.0)))
        self.peak_q_var.set(float(data.get("peak_q", 0.7)))
        self.peak_gain_var.set(float(data.get("peak_gain", 1.0)))
        self.gain_enabled_var.set(bool(data.get("gain_enabled", False)))
        self.gain_level_var.set(float(data.get("gain_level", 0.0)))
        self.reverb_enabled_var.set(bool(data.get("reverb_enabled", False)))
        self.reverb_room_size_var.set(float(data.get("reverb_room_size", 0.7)))
        self.reverb_damping_var.set(float(data.get("reverb_damping", 0.3)))
        self.reverb_wet_level_var.set(float(data.get("reverb_wet_level", 0.5)))
        self.chorus_enabled_var.set(bool(data.get("chorus_enabled", False)))
        self.chorus_mix_var.set(float(data.get("chorus_mix", 0.5)))
        self.chorus_mod_depth_var.set(float(data.get("chorus_mod_depth", 0.2)))
        self.chorus_mod_rate_var.set(float(data.get("chorus_mod_rate", 0.2)))
        self.phaser_enabled_var.set(bool(data.get("phaser_enabled", False)))
        self.phaser_mix_var.set(float(data.get("phaser_mix", 0.5)))
        self.phaser_mod_depth_var.set(float(data.get("phaser_mod_depth", 0.2)))
        self.phaser_mod_rate_var.set(float(data.get("phaser_mod_rate", 0.2)))
        self.phaser_center_frequency_var.set(float(data.get("phaser_center_frequency", 400.0)))
        self.phaser_feedback_var.set(float(data.get("phaser_feedback", 0.7)))
        self.convolution_enabled_var.set(bool(data.get("convolution_enabled", False)))
        self.reverb_ir_var.set(str(data.get("reverb_ir_file", "")))
        self.reverb_mix_var.set(float(data.get("reverb_mix", 0.0)))
        self.pitch_shift_enabled_var.set(bool(data.get("pitch_shift_enabled", False)))
        self.pitch_shift_var.set(float(data.get("pitch_shift", 0.0)))
        self.pitch_shift_mix_var.set(float(data.get("pitch_shift_mix", 0.5)))
        self.wave_folder_enabled_var.set(bool(data.get("wave_folder_enabled", False)))
        self.wave_folder_drive_var.set(float(data.get("wave_folder_drive", 1.0)))
        self.wave_folder_threshold_var.set(float(data.get("wave_folder_threshold", 0.25)))
        self.wave_shaper_enabled_var.set(bool(data.get("wave_shaper_enabled", False)))
        self.wave_shaper_drive_var.set(float(data.get("wave_shaper_drive", 1.0)))
        self.wave_shaper_drive_boost_var.set(float(data.get("wave_shaper_drive_boost", 1.0)))
        self.wave_shaper_output_level_var.set(float(data.get("wave_shaper_output_level", 0.1)))
        self.wave_shaper_high_quality_var.set(bool(data.get("wave_shaper_high_quality", True)))
        self.stereo_simulator_enabled_var.set(bool(data.get("stereo_simulator_enabled", False)))
        self.stereo_simulator_algorithm_var.set(str(data.get("stereo_simulator_algorithm", "adt")))
        self.stereo_simulator_width_var.set(float(data.get("stereo_simulator_width", 0.5)))
        self.stereo_simulator_delay_time_var.set(float(data.get("stereo_simulator_delay_time", 0.005)))
        self.stereo_simulator_mod_rate_var.set(float(data.get("stereo_simulator_mod_rate", 0.5)))
        self.stereo_simulator_mod_depth_var.set(float(data.get("stereo_simulator_mod_depth", 0.3)))
        self.bit_crusher_enabled_var.set(bool(data.get("bit_crusher_enabled", False)))
        self.bit_crusher_bit_depth_var.set(int(data.get("bit_crusher_bit_depth", 8)))
        self.bit_crusher_sample_rate_reduction_var.set(int(data.get("bit_crusher_sample_rate_reduction", 4)))
        self.bit_crusher_mix_var.set(float(data.get("bit_crusher_mix", 1.0)))
        self.ds_knob_tone_var.set(bool(data.get("ds_knob_tone", True)))
        self.ds_knob_filter_resonance_var.set(bool(data.get("ds_knob_filter_resonance", False)))
        self.ds_knob_notch_frequency_var.set(bool(data.get("ds_knob_notch_frequency", False)))
        self.ds_knob_notch_q_var.set(bool(data.get("ds_knob_notch_q", False)))
        self.ds_knob_peak_frequency_var.set(bool(data.get("ds_knob_peak_frequency", False)))
        self.ds_knob_peak_q_var.set(bool(data.get("ds_knob_peak_q", False)))
        self.ds_knob_peak_gain_var.set(bool(data.get("ds_knob_peak_gain", False)))
        self.ds_knob_gain_level_var.set(bool(data.get("ds_knob_gain_level", False)))
        self.ds_knob_reverb_wet_var.set(bool(data.get("ds_knob_reverb_wet", True)))
        self.ds_knob_reverb_room_var.set(bool(data.get("ds_knob_reverb_room", False)))
        self.ds_knob_reverb_damping_var.set(bool(data.get("ds_knob_reverb_damping", False)))
        self.ds_knob_delay_wet_var.set(bool(data.get("ds_knob_delay_wet", True)))
        self.ds_knob_delay_time_var.set(bool(data.get("ds_knob_delay_time", False)))
        self.ds_knob_delay_stereo_offset_var.set(bool(data.get("ds_knob_delay_stereo_offset", False)))
        self.ds_knob_delay_feedback_var.set(bool(data.get("ds_knob_delay_feedback", False)))
        self.ds_knob_chorus_mix_var.set(bool(data.get("ds_knob_chorus_mix", True)))
        self.ds_knob_chorus_depth_var.set(bool(data.get("ds_knob_chorus_depth", False)))
        self.ds_knob_chorus_rate_var.set(bool(data.get("ds_knob_chorus_rate", False)))
        self.ds_knob_phaser_mix_var.set(bool(data.get("ds_knob_phaser_mix", False)))
        self.ds_knob_phaser_depth_var.set(bool(data.get("ds_knob_phaser_depth", False)))
        self.ds_knob_phaser_rate_var.set(bool(data.get("ds_knob_phaser_rate", False)))
        self.ds_knob_phaser_frequency_var.set(bool(data.get("ds_knob_phaser_frequency", False)))
        self.ds_knob_phaser_feedback_var.set(bool(data.get("ds_knob_phaser_feedback", False)))
        self.ds_knob_convolution_mix_var.set(bool(data.get("ds_knob_convolution_mix", False)))
        self.ds_knob_pitch_shift_var.set(bool(data.get("ds_knob_pitch_shift", False)))
        self.ds_knob_pitch_shift_mix_var.set(bool(data.get("ds_knob_pitch_shift_mix", False)))
        self.ds_knob_wave_folder_drive_var.set(bool(data.get("ds_knob_wave_folder_drive", False)))
        self.ds_knob_wave_folder_threshold_var.set(bool(data.get("ds_knob_wave_folder_threshold", False)))
        self.ds_knob_wave_shaper_drive_var.set(bool(data.get("ds_knob_wave_shaper_drive", False)))
        self.ds_knob_wave_shaper_boost_var.set(bool(data.get("ds_knob_wave_shaper_boost", False)))
        self.ds_knob_wave_shaper_output_var.set(bool(data.get("ds_knob_wave_shaper_output", False)))
        self.ds_knob_stereo_width_var.set(bool(data.get("ds_knob_stereo_width", False)))
        self.ds_knob_bit_depth_var.set(bool(data.get("ds_knob_bit_depth", False)))
        self.ds_knob_bit_crusher_rate_var.set(bool(data.get("ds_knob_bit_crusher_rate", False)))
        self.ds_knob_bit_crusher_mix_var.set(bool(data.get("ds_knob_bit_crusher_mix", False)))
        self.ui_layout = self._normalise_ui_layout(data.get("ui_layout"))
        self._redraw_ui_preview()
        self.low_note = int(data["low_note"]) if data.get("low_note") is not None else None
        self.high_note = int(data["high_note"]) if data.get("high_note") is not None else None
        self.low_var.set(midi_to_name(self.low_note) if self.low_note is not None else "not set")
        self.high_var.set(midi_to_name(self.high_note) if self.high_note is not None else "not set")
        self.low_entry_var.set(midi_to_name(self.low_note) if self.low_note is not None else "")
        self.high_entry_var.set(midi_to_name(self.high_note) if self.high_note is not None else "")
        self.step_var.set(int(data.get("step", 1)))
        self.samples = [SampleInfo.from_dict(item) for item in data.get("samples", [])]
        self._rebuild_trees_from_project()


    def _open_project(self, path: Path, *, prompt_for_strays: bool = True) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self._load_project_data(data, path)
        self._remember_last_project(path)
        self._log(f"Opened project: {path}")
        if prompt_for_strays:
            self.after_idle(self._prompt_for_stray_audio_if_any)

    def _prompt_for_stray_audio_if_any(self) -> None:
        strays = self._stray_audio_candidates()
        if not strays:
            return
        if messagebox.askyesno("SampleSmith", f"Found {len(strays)} stray audio file(s) in this project/instrument folder. Review them now?"):
            self._review_stray_audio()
        else:
            self._log(f"Stray audio files found but not imported: {len(strays)}")

    def _rebuild_trees_from_project(self) -> None:
        for item in self.note_tree.get_children():
            self.note_tree.delete(item)
        self.note_rows.clear()
        if self.low_note is not None and self.high_note is not None:
            notes = note_range(self.low_note, self.high_note, self.step_var.get())
            ranges = dict((root, (lo, hi)) for root, lo, hi in build_key_ranges(notes))
            for note in notes:
                lo, hi = ranges[note]
                recorded = next((sample for sample in self.samples if sample.mode == "pitched" and sample.root_note == note), None)
                self.note_rows[note] = str(recorded.path) if recorded else ""
                action = self._bridge_action_text(note)
                self.note_tree.insert("", "end", iid=str(note), values=(midi_to_name(note), mapping_text(lo, hi), recorded.path.name if recorded else "", action))
            self._refresh_pitched_mappings()
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
        self._queue_after_id = self.after(100, self._drain_queue)

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
                raise RuntimeError("Could not detect a clear pitch. Try again, or enter the note manually for noisy sounds.")
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
            self.note_tree.insert("", "end", iid=iid, values=(midi_to_name(note), mapping_text(lo, hi), "", self._bridge_action_text(note)))
        self._log("Built note list with full-keyboard sample mapping")

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

    def _sample_for_pitched_note(self, note: int) -> SampleInfo | None:
        sample = next((sample for sample in self.samples if sample.mode == "pitched" and sample.root_note == note and not sample.generated), None)
        if sample is None:
            sample = next((sample for sample in self.samples if sample.mode == "pitched" and sample.root_note == note), None)
        return sample

    def _on_pitched_selection_changed(self, _event=None) -> None:
        selected = self.note_tree.selection()
        if not selected:
            self.selected_panel_kind = None
            self.selected_sample_title_var.set("Select a note")
            self._set_panel_action_controls_enabled(False, False)
            return
        self.selected_panel_kind = "pitched"
        note = int(selected[0])
        self.selected_sample_title_var.set(f"{midi_to_name(note)}")
        self._set_panel_action_controls_enabled(True, True)
        sample = self._sample_for_pitched_note(note)
        if sample is not None:
            self._schedule_sample_review_load(sample)
        else:
            self._clear_pending_recording_review()

    def _schedule_sample_review_load(self, sample: SampleInfo) -> None:
        self._review_load_token += 1
        token = self._review_load_token
        self.recording_review_status_var.set(f"Loading {sample.path.name}...")
        self._set_review_controls_enabled(False)
        self.after(1, lambda: self._load_scheduled_sample_review(sample, token))

    def _load_scheduled_sample_review(self, sample: SampleInfo, token: int) -> None:
        if token != self._review_load_token:
            return
        self._load_existing_sample_for_review(sample, confirm_discard=False)

    def _selected_panel_pitched_note(self) -> int | None:
        if self.selected_panel_kind != "pitched":
            return None
        selected = self.note_tree.selection()
        if not selected:
            return None
        try:
            return int(selected[0])
        except ValueError:
            return None

    def _record_all_missing(self) -> None:
        notes = [int(item) for item in self.note_tree.get_children() if not self.note_rows.get(int(item))]
        if not notes:
            self._log("No missing pitched samples")
            return
        self._record_note_sequence(notes)

    def _on_note_tree_click(self, event) -> None:
        if self.note_tree.identify_region(event.x, event.y) != "cell":
            return
        row_id = self.note_tree.identify_row(event.y)
        column = self.note_tree.identify_column(event.x)
        if not row_id or column != "#4":
            return
        try:
            note = int(row_id)
        except ValueError:
            return
        if not self._bridge_action_text(note):
            return
        self.after_idle(lambda: self._show_bridge_gap_menu(note, event.x_root, event.y_root))

    def _show_bridge_gap_menu(self, note: int, x_root: int, y_root: int) -> None:
        menu = tk.Menu(self, tearoff=False)
        note_name = midi_to_name(note)
        menu.add_command(label=f"Generate {note_name}", command=lambda: self._bridge_gap_for_notes([note]))
        targets = self._bridge_gap_targets(note)
        if len(targets) > 1:
            label = f"Bridge gap {midi_to_name(targets[0])}–{midi_to_name(targets[-1])}"
            menu.add_command(label=label, command=lambda: self._bridge_gap_for_notes(targets))
        menu.tk_popup(x_root, y_root)

    def _recorded_pitched_sample_for_note(self, note: int) -> SampleInfo | None:
        return next((sample for sample in self.samples if sample.mode == "pitched" and sample.root_note == note and not sample.generated), None)

    def _bridge_action_text(self, note: int) -> str:
        if self._recorded_pitched_sample_for_note(note):
            return ""
        if not self._recorded_pitched_samples():
            return ""
        return "Bridge gap"

    def _bridge_gap_targets(self, note: int) -> list[int]:
        if self._recorded_pitched_sample_for_note(note):
            return []
        notes = sorted(int(item) for item in self.note_tree.get_children())
        if note not in notes:
            return [note]
        index = notes.index(note)
        start = index
        while start > 0 and not self._recorded_pitched_sample_for_note(notes[start - 1]):
            start -= 1
        end = index
        while end + 1 < len(notes) and not self._recorded_pitched_sample_for_note(notes[end + 1]):
            end += 1
        return [target for target in notes[start : end + 1] if self._bridge_plan_for_note(target) is not None]

    def _bridge_plan_for_note(self, target_note: int) -> tuple[str, SampleInfo, SampleInfo | None, Path] | None:
        if self._recorded_pitched_sample_for_note(target_note):
            return None
        recorded = sorted(self._recorded_pitched_samples(), key=lambda sample: sample.root_note)
        if not recorded:
            return None
        lower = next((sample for sample in reversed(recorded) if sample.root_note < target_note), None)
        higher = next((sample for sample in recorded if sample.root_note > target_note), None)
        if lower and higher:
            return ("blend", lower, higher, self._bridge_sample_path(target_note, lower.root_note, higher.root_note))
        nearest = min(recorded, key=lambda sample: abs(sample.root_note - target_note))
        return ("retune", nearest, None, self._bridge_sample_path(target_note, nearest.root_note, nearest.root_note))

    def _bridge_gap_for_notes(self, notes: list[int]) -> None:
        plans = [(note, self._bridge_plan_for_note(note)) for note in notes]
        plans = [(note, plan) for note, plan in plans if plan is not None]
        if not plans:
            messagebox.showinfo("SampleSmith", "No bridgeable missing notes here yet.")
            return
        before = {plan[3] for _, plan in plans if plan[3].exists()}
        written: list[Path] = []
        for target_note, plan in plans:
            kind, first, second, target_path = plan
            missing_sources = [source.path for source in (first, second) if source is not None and not source.path.exists()]
            if missing_sources:
                for path in missing_sources:
                    self._log(f"Cannot bridge {midi_to_name(target_note)}; source audio is missing: {path}")
                continue
            try:
                if kind == "blend" and second is not None:
                    render_bridge_wav(first.path, second.path, target_path, first.root_note, target_note, second.root_note)
                    source_text = f"{first.path.name} + {second.path.name}"
                else:
                    render_retuned_bridge_wav(first.path, target_path, first.root_note, target_note)
                    source_text = f"retuned from {first.path.name}"
            except RuntimeError as exc:
                self._log(f"Cannot bridge {midi_to_name(target_note)}: {exc}")
                continue
            sources = [source for source in (first, second) if source is not None]
            self._upsert_sample(
                SampleInfo(
                    path=target_path,
                    root_note=target_note,
                    lo_note=target_note,
                    hi_note=target_note,
                    label=f"BRIDGE {midi_to_name(target_note)} (generated)",
                    mode="pitched",
                    generated=True,
                    source_roots=[source.root_note for source in sources],
                    source_paths=[source.path for source in sources],
                )
            )
            written.append(target_path)
            self._log(f"Bridged {midi_to_name(target_note)}: {target_path.relative_to(self._instrument_dir())} ({source_text})")
        if not written:
            return
        self._refresh_pitched_mappings()
        preset = self._write_preset()
        self._auto_save_project()
        created = len({path for path in written if path not in before})
        self._log(f"Bridge gap wrote {len(written)} generated sample(s); {created} newly created. Updated {preset.name}")

    def _record_note_sequence(self, notes: list[int]) -> None:
        if not notes:
            return
        note = notes.pop(0)
        self._record_note(note, after=lambda: self._record_note_sequence(notes))

    def _record_note(self, note: int, after=None) -> None:
        note_name = midi_to_name(note)
        path = self._sample_path(note_name.replace("#", "sharp"))
        if not self._confirm_recording(f"Ready to record {note_name}?", path):
            return

        def work():
            audio = self._audio()
            if self.play_reference_before_record_var.get():
                audio.play_tone(note)
                time.sleep(0.3)
            raw = audio.record(self.record_seconds_var.get())
            selection = raw
            ranges = dict((root, (lo, hi)) for root, lo, hi in build_key_ranges([int(i) for i in self.note_tree.get_children()]))
            lo, hi = ranges[note]
            info = SampleInfo(path=path, root_note=note, lo_note=lo, hi_note=hi, label=note_name, mode="pitched")

            def apply():
                def keep(reviewed):
                    self._write_reviewed_audio(path, reviewed)
                    self._upsert_sample(info)
                    self.note_rows[note] = str(path)
                    self._refresh_pitched_mappings()
                    mapped = next(sample for sample in self.samples if sample.mode == "pitched" and sample.root_note == note)
                    preset = self._write_preset()
                    self._log(f"Recorded {note_name}: {path.name} — maps {mapping_text(mapped.lo_note, mapped.hi_note)}")
                    self._log(f"Updated DecentSampler patch: {preset.name}")
                    self._auto_save_project()
                    if after:
                        after()

                def record_take():
                    self._record_note(note, after=after)

                self._set_pending_recording_review(f"Review {note_name}", raw, selection, keep, record_take)
            return apply

        self._run_worker(f"Recording {note_name}...", work)

    def _confirm_recording(self, prompt: str, path: Path) -> bool:
        if self.pending_recording_review:
            self._clear_pending_recording_review()
        if self.confirm_before_record_var.get():
            return messagebox.askokcancel("SampleSmith", prompt)
        return True

    def _confirm_discard_pending_review(self) -> bool:
        if not self.pending_recording_review:
            return True
        if not messagebox.askokcancel(
            "SampleSmith",
            "There is already a recording waiting in the Recording review panel. Discard it and review another sample?",
        ):
            return False
        self._clear_pending_recording_review()
        return True

    def _load_existing_sample_for_review(self, sample: SampleInfo, confirm_discard: bool = True) -> None:
        if confirm_discard:
            if not self._confirm_discard_pending_review():
                return
        elif self.pending_recording_review:
            self._clear_pending_recording_review()
        if not sample.path.exists():
            if confirm_discard:
                messagebox.showwarning("SampleSmith", f"Could not find this audio file:\n\n{sample.path}")
            return
        try:
            raw, sample_rate = self._audio().read_audio(sample.path)
            self._ensure_sample_backup(sample.path)
        except Exception as exc:
            messagebox.showerror("SampleSmith", f"Could not load this audio file for review:\n\n{exc}")
            return

        def keep(reviewed):
            self._write_reviewed_audio(sample.path, reviewed, sample_rate=sample_rate)
            preset = self._write_preset()
            self._auto_save_project()
            self._log(f"Updated reviewed audio: {sample.path.name}")
            self._log(f"Updated DecentSampler patch: {preset.name}")

        def record_take():
            self._record_existing_sample_again(sample)

        def reset():
            if self._restore_sample_backup(sample.path):
                preset = self._write_preset()
                self._auto_save_project()
                self._log(f"Updated DecentSampler patch: {preset.name}")
                self._load_existing_sample_for_review(sample, confirm_discard=False)

        self._set_pending_recording_review(f"Review {sample.label or sample.path.name}", raw, raw, keep, record_take, sample_rate=sample_rate, reset=reset)

    def _record_existing_sample_again(self, sample: SampleInfo) -> None:
        def work():
            audio = self._audio()
            if sample.mode == "pitched" and sample.root_note is not None and self.play_reference_before_record_var.get():
                audio.play_tone(sample.root_note)
                time.sleep(0.3)
            raw = audio.record(self.record_seconds_var.get())
            selection = raw
            sample_rate = int(audio.sample_rate)

            def apply():
                def keep(reviewed):
                    self._write_reviewed_audio(sample.path, reviewed, sample_rate=sample_rate)
                    preset = self._write_preset()
                    self._auto_save_project()
                    self._log(f"Updated reviewed audio: {sample.path.name}")
                    self._log(f"Updated DecentSampler patch: {preset.name}")

                def record_take():
                    self._record_existing_sample_again(sample)

                def reset():
                    if self._restore_sample_backup(sample.path):
                        preset = self._write_preset()
                        self._auto_save_project()
                        self._log(f"Updated DecentSampler patch: {preset.name}")
                        self._load_existing_sample_for_review(sample, confirm_discard=False)

                self._set_pending_recording_review(f"Review {sample.label or sample.path.name}", raw, selection, keep, record_take, sample_rate=sample_rate, reset=reset)
            return apply

        self._run_worker(f"Recording {sample.label or sample.path.name}...", work)

    def _duration_text(self, audio, sample_rate: int | None = None) -> str:
        return f"{len(audio) / max(1, int(sample_rate or self.sample_rate_var.get())):.2f}s"

    def _review_status_text(self) -> str:
        if not self.pending_recording_review:
            return "No audio loaded yet. Record a sample, or select a row with an existing audio file."
        return (
            f"{self.pending_recording_review['title']} — "
            f"full {self._duration_text(self.pending_recording_review['raw_audio'], self.pending_recording_review['sample_rate'])}; "
            f"selection {self._duration_text(self._review_selected_audio(), self.pending_recording_review['sample_rate'])}"
        )

    def _set_pending_recording_review(self, title: str, raw_audio, _selection_audio, on_keep, on_record_take, sample_rate: int | None = None, reset=None) -> None:
        end_frame = max(0, len(raw_audio))
        self.pending_recording_review = {
            "title": title,
            "raw_audio": raw_audio,
            "sample_rate": int(sample_rate or self.sample_rate_var.get()),
            "trim_start": 0,
            "trim_end": end_frame,
            "on_keep": on_keep,
            "on_record_take": on_record_take,
            "on_reset": reset,
        }
        self._sync_review_trim_fields()
        self.recording_review_status_var.set(self._review_status_text())
        self._set_review_controls_enabled(True)
        self._refresh_reset_button_state()
        self._draw_review_waveform()

    def _clear_pending_recording_review(self) -> None:
        self.pending_recording_review = None
        self.recording_review_status_var.set(self._review_status_text())
        self.recording_review_canvas.delete("all")
        self.recording_review_start_var.set(0)
        self.recording_review_end_var.set(0)
        self._set_review_controls_enabled(False)

    def _refresh_reset_button_state(self) -> None:
        if not hasattr(self, "recording_review_reset_button"):
            return
        can_reset = bool(self.pending_recording_review and self.pending_recording_review.get("on_reset"))
        self.recording_review_reset_button.configure(state="normal" if can_reset else "disabled")

    def _sync_review_trim_fields(self) -> None:
        if not self.pending_recording_review:
            return
        self._updating_review_trim_fields = True
        try:
            frames = len(self.pending_recording_review["raw_audio"])
            start = int(self.pending_recording_review["trim_start"])
            end = int(self.pending_recording_review["trim_end"])
            self.recording_review_start_spinbox.configure(from_=0, to=max(0, frames - 1))
            self.recording_review_end_spinbox.configure(from_=1 if frames else 0, to=max(0, frames))
            self.recording_review_start_var.set(start)
            self.recording_review_end_var.set(end)
        finally:
            self._updating_review_trim_fields = False

    def _on_review_trim_fields_changed(self) -> None:
        if self._updating_review_trim_fields or not self.pending_recording_review:
            return
        frames = len(self.pending_recording_review["raw_audio"])
        if frames <= 0:
            return
        try:
            start = int(self.recording_review_start_var.get())
            end = int(self.recording_review_end_var.get())
        except (tk.TclError, ValueError):
            return
        start = max(0, min(frames - 1, start))
        end = max(start + 1, min(frames, end))
        self.pending_recording_review["trim_start"] = start
        self.pending_recording_review["trim_end"] = end
        self.recording_review_status_var.set(self._review_status_text())
        self._draw_review_waveform()

    def _review_frame_at_x(self, x: int) -> int:
        if not self.pending_recording_review:
            return 0
        frames = max(1, len(self.pending_recording_review["raw_audio"]))
        width = int(self.recording_review_canvas.winfo_width() or self.review_canvas_width)
        if width < 10:
            width = self.review_canvas_width
        return max(0, min(frames - 1, int((max(0, min(width - 1, x)) / max(1, width - 1)) * (frames - 1))))

    def _set_review_trim_start_from_canvas(self, event) -> None:
        if not self.pending_recording_review:
            return
        frame = self._review_frame_at_x(event.x)
        end = int(self.pending_recording_review["trim_end"])
        self.pending_recording_review["trim_start"] = max(0, min(frame, max(0, end - 1)))
        self._sync_review_trim_fields()
        self.recording_review_status_var.set(self._review_status_text())
        self._draw_review_waveform()

    def _set_review_trim_end_from_canvas(self, event) -> None:
        if not self.pending_recording_review:
            return
        frame = self._review_frame_at_x(event.x) + 1
        frames = len(self.pending_recording_review["raw_audio"])
        start = int(self.pending_recording_review["trim_start"])
        self.pending_recording_review["trim_end"] = max(start + 1, min(frames, frame))
        self._sync_review_trim_fields()
        self.recording_review_status_var.set(self._review_status_text())
        self._draw_review_waveform()

    def _review_selected_audio(self):
        if not self.pending_recording_review:
            return []
        audio = self.pending_recording_review["raw_audio"]
        start = int(self.pending_recording_review.get("trim_start", 0))
        end = int(self.pending_recording_review.get("trim_end", len(audio)))
        return audio[start:end]

    def _frame_peak(self, frame) -> float:
        try:
            return max(abs(float(value)) for value in frame)
        except TypeError:
            return abs(float(frame))

    def _draw_review_waveform(self) -> None:
        canvas = self.recording_review_canvas
        canvas.delete("all")
        if not self.pending_recording_review:
            return
        audio = self.pending_recording_review["raw_audio"]
        frames = len(audio)
        if frames <= 0:
            return
        width = int(canvas.winfo_width() or self.review_canvas_width)
        height = int(canvas.winfo_height() or self.review_canvas_height)
        if width < 10:
            width = self.review_canvas_width
        if height < 10:
            height = self.review_canvas_height
        mid = height // 2
        start = int(self.pending_recording_review["trim_start"])
        end = int(self.pending_recording_review["trim_end"])
        x_start = int(start / max(1, frames) * width)
        x_end = int(end / max(1, frames) * width)
        canvas.create_rectangle(x_start, 0, max(x_start + 1, x_end), height, fill="#1d3d54", outline="")
        step = max(1, frames // width)
        peaks = []
        for x in range(width):
            left = min(frames, x * step)
            right = min(frames, max(left + 1, (x + 1) * step))
            peak = max((self._frame_peak(audio[i]) for i in range(left, right)), default=0.0)
            peaks.append(peak)
        scale = max(peaks) or 1.0
        upper_points: list[int] = []
        lower_points: list[int] = []
        for x, peak in enumerate(peaks):
            y = int((peak / scale) * (height / 2 - 4))
            upper_points.extend((x, mid - y))
            lower_points.extend((x, mid + y))
        if len(upper_points) >= 4:
            canvas.create_line(*upper_points, fill="#d8d8d8", smooth=True, splinesteps=8)
            canvas.create_line(*lower_points, fill="#d8d8d8", smooth=True, splinesteps=8)
        canvas.create_line(0, mid, width, mid, fill="#444444")
        canvas.create_line(x_start, 0, x_start, height, fill="#63d471", width=2)
        canvas.create_line(x_end, 0, x_end, height, fill="#ff6b6b", width=2)

    def _play_review_audio(self, audio) -> None:
        if not self.pending_recording_review:
            return
        sample_rate = int(self.pending_recording_review["sample_rate"])

        def work():
            try:
                self._audio().play_audio(audio, sample_rate=sample_rate)
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("SampleSmith", f"Could not play recording:\n\n{exc}"))

        threading.Thread(target=work, daemon=True).start()

    def _play_review_full(self) -> None:
        self._play_review_audio(self.pending_recording_review["raw_audio"] if self.pending_recording_review else [])

    def _play_review_selection(self) -> None:
        self._play_review_audio(self._review_selected_audio())

    def _keep_review_recording(self) -> None:
        if not self.pending_recording_review:
            return
        reviewed = self._review_selected_audio()
        on_keep = self.pending_recording_review["on_keep"]
        on_keep(reviewed)
        if self.pending_recording_review:
            self.pending_recording_review["raw_audio"] = reviewed
            self.pending_recording_review["trim_start"] = 0
            self.pending_recording_review["trim_end"] = len(reviewed)
            self._sync_review_trim_fields()
            self.recording_review_status_var.set(self._review_status_text())
            self._set_review_controls_enabled(True)
            self._refresh_reset_button_state()
            self._draw_review_waveform()

    def _record_review_take(self) -> None:
        if not self.pending_recording_review:
            return
        on_record_take = self.pending_recording_review["on_record_take"]
        self._clear_pending_recording_review()
        on_record_take()

    def _reset_review_recording(self) -> None:
        if not self.pending_recording_review:
            return
        on_reset = self.pending_recording_review.get("on_reset")
        if not on_reset:
            return
        on_reset()

    def _upsert_sample(self, info: SampleInfo) -> None:
        self.samples = [sample for sample in self.samples if not (sample.mode == info.mode and sample.root_note == info.root_note)]
        self.samples.append(info)
        self.samples.sort(key=lambda sample: (sample.mode, sample.root_note, sample.path.name))

    def _recorded_pitched_samples(self) -> list[SampleInfo]:
        return [sample for sample in self.samples if sample.mode == "pitched" and not sample.generated]

    def _generated_bridge_samples(self, render_missing: bool = False) -> list[SampleInfo]:
        generated: list[SampleInfo] = []
        saved_generated = {
            (sample.root_note, sample.path): sample
            for sample in self.samples
            if sample.mode == "pitched" and sample.generated
        }
        if self.note_tree.get_children():
            target_notes = [int(item) for item in self.note_tree.get_children()]
        elif self.low_note is not None and self.high_note is not None:
            target_notes = note_range(self.low_note, self.high_note, self.step_var.get())
        else:
            target_notes = []
        for target_note in target_notes:
            plan = self._bridge_plan_for_note(target_note)
            if plan is None:
                continue
            kind, first, second, target_path = plan
            sources = [source for source in (first, second) if source is not None]
            missing_sources = [source.path for source in sources if not source.path.exists()]
            if render_missing and missing_sources:
                for path in missing_sources:
                    self._log(f"Cannot bridge {midi_to_name(target_note)}; source audio is missing: {path}")
                continue
            if render_missing and not missing_sources:
                source_mtime = max(source.path.stat().st_mtime for source in sources)
                if not target_path.exists() or target_path.stat().st_mtime < source_mtime:
                    try:
                        if kind == "blend" and second is not None:
                            render_bridge_wav(first.path, second.path, target_path, first.root_note, target_note, second.root_note)
                        else:
                            render_retuned_bridge_wav(first.path, target_path, first.root_note, target_note)
                    except RuntimeError as exc:
                        self._log(f"Cannot bridge {midi_to_name(target_note)}: {exc}")
                        continue
            if not target_path.exists():
                continue
            saved_sample = saved_generated.get((target_note, target_path))
            if saved_sample is not None:
                generated.append(saved_sample)
                continue
            generated.append(
                SampleInfo(
                    path=target_path,
                    root_note=target_note,
                    lo_note=target_note,
                    hi_note=target_note,
                    label=f"BRIDGE {midi_to_name(target_note)} (generated)",
                    mode="pitched",
                    generated=True,
                    source_roots=[source.root_note for source in sources],
                    source_paths=[source.path for source in sources],
                )
            )
        return generated

    def _exportable_note_samples(self) -> list[SampleInfo]:
        pitched = self._recorded_pitched_samples() + self._generated_bridge_samples()
        if not pitched:
            return []
        ranges = dict((root, (lo, hi)) for root, lo, hi in build_overlapping_key_ranges([sample.root_note for sample in pitched]))
        spread = [
            SampleInfo(
                path=sample.path,
                root_note=sample.root_note,
                lo_note=sample.lo_note if sample.custom_mapping else ranges[sample.root_note][0],
                hi_note=sample.hi_note if sample.custom_mapping else ranges[sample.root_note][1],
                label=sample.label,
                mode=sample.mode,
                loop_enabled=sample.loop_enabled,
                loop_start=sample.loop_start,
                loop_end=sample.loop_end,
                loop_crossfade=sample.loop_crossfade,
                loop_crossfade_mode=sample.loop_crossfade_mode,
                generated=sample.generated,
                custom_mapping=sample.custom_mapping,
                source_roots=sample.source_roots,
                source_paths=sample.source_paths,
            )
            for sample in pitched
        ]
        return sorted(spread, key=lambda sample: (sample.mode, sample.root_note, sample.path.name))

    def _refresh_pitched_mappings(self) -> None:
        exported = [sample for sample in self._exportable_note_samples() if sample.mode == "pitched"]
        exported_roots = {sample.root_note for sample in exported}
        recorded_roots = {sample.root_note for sample in exported if not sample.generated}
        generated_roots = exported_roots - recorded_roots
        for item in list(self.note_tree.get_children()):
            note = int(item)
            if "generated" in self.note_tree.item(item, "tags") and note not in generated_roots and note not in recorded_roots:
                self.note_tree.delete(item)
                self.note_rows.pop(note, None)

        for sample in exported:
            iid = str(sample.root_note)
            is_generated = sample.generated
            file_name = f"[GENERATED] {sample.path.name}" if is_generated else sample.path.name
            values = (midi_to_name(sample.root_note), mapping_text(sample.lo_note, sample.hi_note), file_name, self._bridge_action_text(sample.root_note))
            if iid in self.note_tree.get_children():
                self.note_tree.item(iid, values=values, tags=("generated",) if is_generated else ())
            else:
                self.note_rows[sample.root_note] = "" if is_generated else str(sample.path)
                self.note_tree.insert("", "end", iid=iid, values=values, tags=("generated",) if is_generated else ())
        self._refresh_bridge_actions()

    def _refresh_bridge_actions(self) -> None:
        for item in self.note_tree.get_children():
            note = int(item)
            values = list(self.note_tree.item(item, "values"))
            while len(values) < 4:
                values.append("")
            values[3] = self._bridge_action_text(note)
            self.note_tree.item(item, values=tuple(values))

    def _sample_loop_text(self, sample: SampleInfo) -> str:
        if not sample.loop_enabled:
            return "—"
        start, end = optional_non_negative_int(sample.loop_start), optional_non_negative_int(sample.loop_end)
        if start is None or end is None or end <= start:
            return "on"
        text = f"{start}–{end}"
        if sample.loop_crossfade and sample.loop_crossfade > 0:
            text += f" / xfade {sample.loop_crossfade:g}"
        return text

    def _refresh_export_mapping(self) -> None:
        for item in self.export_tree.get_children():
            self.export_tree.delete(item)
        self.export_samples_by_iid.clear()
        for index, sample in enumerate(self._exportable_note_samples()):
            iid = f"export-{index}"
            self.export_samples_by_iid[iid] = sample
            self.export_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    f"[GENERATED] {sample.path.name}" if sample.generated else sample.path.name,
                    mapping_text(sample.lo_note, sample.hi_note),
                    exported_root_text(sample.root_note),
                    "bridge" if sample.generated else sample.mode,
                    self._sample_loop_text(sample),
                ),
            )

    def _editable_sample_for_exported(self, exported: SampleInfo) -> SampleInfo | None:
        for sample in self.samples:
            if sample.mode == exported.mode and sample.root_note == exported.root_note and sample.path == exported.path:
                return sample
        if exported.generated:
            self.samples.append(exported)
            self.samples.sort(key=lambda sample: (sample.mode, sample.root_note, sample.path.name))
            return exported
        return None

    def _edit_export_row_from_double_click(self, event) -> str:
        row_id = self.export_tree.identify_row(event.y)
        if not row_id:
            return "break"
        self.export_tree.selection_set(row_id)
        column = self.export_tree.identify_column(event.x)
        if column in {"#1", "#2"}:
            self._edit_selected_sample_mapping()
        else:
            self._edit_selected_sample_loop()
        return "break"

    def _edit_selected_sample_loop(self) -> None:
        selected = self.export_tree.selection()
        if not selected:
            messagebox.showwarning("SampleSmith", "Select an audio file in the exported mapping first.")
            return
        exported = self.export_samples_by_iid.get(selected[0])
        if exported is None:
            messagebox.showwarning("SampleSmith", "Could not find that exported sample. Try refreshing the mapping.")
            return
        sample = self._editable_sample_for_exported(exported)
        if sample is None:
            messagebox.showinfo(
                "SampleSmith",
                "That generated row could not be made editable. Try refreshing the mapping, then try again.",
            )
            return
        if not sample.path.exists():
            messagebox.showwarning("SampleSmith", f"Audio file not found:\n{sample.path}")
            return
        try:
            LoopEditorDialog(self, sample, self._apply_sample_loop_edit)
        except RuntimeError as exc:
            messagebox.showerror("SampleSmith", str(exc))

    def _edit_selected_sample_mapping(self) -> None:
        selected = self.export_tree.selection()
        if not selected:
            messagebox.showwarning("SampleSmith", "Select a row in the exported mapping first.")
            return
        exported = self.export_samples_by_iid.get(selected[0])
        if exported is None:
            messagebox.showwarning("SampleSmith", "Could not find that exported sample. Try refreshing the mapping.")
            return
        sample = self._editable_sample_for_exported(exported)
        if sample is None:
            messagebox.showinfo(
                "SampleSmith",
                "That generated row could not be made editable. Try refreshing the mapping, then try again.",
            )
            return
        MappingEditorDialog(self, sample, self._apply_sample_mapping_edit)

    def _apply_sample_mapping_edit(self, sample: SampleInfo) -> None:
        self._refresh_pitched_mappings()
        preset = self._write_preset()
        self._auto_save_project()
        self._log(f"Updated key mapping for {sample.path.name}; regenerated {preset.name}")

    def _apply_sample_loop_edit(self, sample: SampleInfo) -> None:
        self._refresh_pitched_mappings()
        preset = self._write_preset()
        self._auto_save_project()
        self._log(f"Updated loop settings for {sample.path.name}; regenerated {preset.name}")

    def _import_first_wav_loop_marker(self) -> None:
        for sample in self.samples:
            marker = read_wav_smpl_loop_points(sample.path)
            if marker is None:
                continue
            start, end = marker
            self.loop_start_var.set(str(start))
            self.loop_end_var.set(str(end))
            self.loop_enabled_var.set(True)
            self._log(f"Imported WAV loop marker from {sample.path.name}: {start}–{end}")
            self._on_output_parameter_changed()
            return
        messagebox.showinfo(
            "SampleSmith",
            "No embedded WAV smpl loop markers found in the recorded samples. Enter loop start/end manually.",
        )

    def _dspreset_options(self) -> dict[str, object]:
        return dict(
            loop_enabled=self.loop_enabled_var.get(),
            loop_start=optional_non_negative_int(self.loop_start_var.get()),
            loop_end=optional_non_negative_int(self.loop_end_var.get()),
            loop_crossfade=self.loop_crossfade_var.get(),
            loop_crossfade_mode=self.loop_crossfade_mode_var.get(),
            amp_env_enabled=self.amp_env_enabled_var.get(),
            amp_attack=self.amp_attack_var.get(),
            amp_decay=self.amp_decay_var.get(),
            amp_sustain=self.amp_sustain_var.get(),
            amp_release=self.amp_release_var.get(),
            ds_knob_amp_env=self.ds_knob_amp_env_var.get(),
            delay_enabled=self.delay_enabled_var.get(),
            delay_time=self.delay_time_var.get(),
            delay_stereo_offset=self.delay_stereo_offset_var.get(),
            delay_feedback=self.delay_feedback_var.get(),
            delay_wet_level=self.delay_wet_level_var.get(),
            lowpass_enabled=self.lowpass_enabled_var.get(),
            filter_type=self.filter_type_var.get(),
            lowpass_frequency=self.lowpass_frequency_var.get(),
            filter_resonance=self.filter_resonance_var.get(),
            notch_enabled=self.notch_enabled_var.get(),
            notch_frequency=self.notch_frequency_var.get(),
            notch_q=self.notch_q_var.get(),
            peak_enabled=self.peak_enabled_var.get(),
            peak_frequency=self.peak_frequency_var.get(),
            peak_q=self.peak_q_var.get(),
            peak_gain=self.peak_gain_var.get(),
            gain_enabled=self.gain_enabled_var.get(),
            gain_level=self.gain_level_var.get(),
            reverb_enabled=self.reverb_enabled_var.get(),
            reverb_room_size=self.reverb_room_size_var.get(),
            reverb_damping=self.reverb_damping_var.get(),
            reverb_wet_level=self.reverb_wet_level_var.get(),
            chorus_enabled=self.chorus_enabled_var.get(),
            chorus_mix=self.chorus_mix_var.get(),
            chorus_mod_depth=self.chorus_mod_depth_var.get(),
            chorus_mod_rate=self.chorus_mod_rate_var.get(),
            phaser_enabled=self.phaser_enabled_var.get(),
            phaser_mix=self.phaser_mix_var.get(),
            phaser_mod_depth=self.phaser_mod_depth_var.get(),
            phaser_mod_rate=self.phaser_mod_rate_var.get(),
            phaser_center_frequency=self.phaser_center_frequency_var.get(),
            phaser_feedback=self.phaser_feedback_var.get(),
            convolution_enabled=self.convolution_enabled_var.get(),
            reverb_ir_file=self.reverb_ir_var.get(),
            reverb_mix=self.reverb_mix_var.get(),
            pitch_shift_enabled=self.pitch_shift_enabled_var.get(),
            pitch_shift=self.pitch_shift_var.get(),
            pitch_shift_mix=self.pitch_shift_mix_var.get(),
            wave_folder_enabled=self.wave_folder_enabled_var.get(),
            wave_folder_drive=self.wave_folder_drive_var.get(),
            wave_folder_threshold=self.wave_folder_threshold_var.get(),
            wave_shaper_enabled=self.wave_shaper_enabled_var.get(),
            wave_shaper_drive=self.wave_shaper_drive_var.get(),
            wave_shaper_drive_boost=self.wave_shaper_drive_boost_var.get(),
            wave_shaper_output_level=self.wave_shaper_output_level_var.get(),
            wave_shaper_high_quality=self.wave_shaper_high_quality_var.get(),
            stereo_simulator_enabled=self.stereo_simulator_enabled_var.get(),
            stereo_simulator_algorithm=self.stereo_simulator_algorithm_var.get(),
            stereo_simulator_width=self.stereo_simulator_width_var.get(),
            stereo_simulator_delay_time=self.stereo_simulator_delay_time_var.get(),
            stereo_simulator_mod_rate=self.stereo_simulator_mod_rate_var.get(),
            stereo_simulator_mod_depth=self.stereo_simulator_mod_depth_var.get(),
            bit_crusher_enabled=self.bit_crusher_enabled_var.get(),
            bit_crusher_bit_depth=self.bit_crusher_bit_depth_var.get(),
            bit_crusher_sample_rate_reduction=self.bit_crusher_sample_rate_reduction_var.get(),
            bit_crusher_mix=self.bit_crusher_mix_var.get(),
            ds_knob_tone=self.ds_knob_tone_var.get(),
            ds_knob_filter_resonance=self.ds_knob_filter_resonance_var.get(),
            ds_knob_notch_frequency=self.ds_knob_notch_frequency_var.get(),
            ds_knob_notch_q=self.ds_knob_notch_q_var.get(),
            ds_knob_peak_frequency=self.ds_knob_peak_frequency_var.get(),
            ds_knob_peak_q=self.ds_knob_peak_q_var.get(),
            ds_knob_peak_gain=self.ds_knob_peak_gain_var.get(),
            ds_knob_gain_level=self.ds_knob_gain_level_var.get(),
            ds_knob_reverb_wet=self.ds_knob_reverb_wet_var.get(),
            ds_knob_reverb_room=self.ds_knob_reverb_room_var.get(),
            ds_knob_reverb_damping=self.ds_knob_reverb_damping_var.get(),
            ds_knob_delay_wet=self.ds_knob_delay_wet_var.get(),
            ds_knob_delay_time=self.ds_knob_delay_time_var.get(),
            ds_knob_delay_stereo_offset=self.ds_knob_delay_stereo_offset_var.get(),
            ds_knob_delay_feedback=self.ds_knob_delay_feedback_var.get(),
            ds_knob_chorus_mix=self.ds_knob_chorus_mix_var.get(),
            ds_knob_chorus_depth=self.ds_knob_chorus_depth_var.get(),
            ds_knob_chorus_rate=self.ds_knob_chorus_rate_var.get(),
            ds_knob_phaser_mix=self.ds_knob_phaser_mix_var.get(),
            ds_knob_phaser_depth=self.ds_knob_phaser_depth_var.get(),
            ds_knob_phaser_rate=self.ds_knob_phaser_rate_var.get(),
            ds_knob_phaser_frequency=self.ds_knob_phaser_frequency_var.get(),
            ds_knob_phaser_feedback=self.ds_knob_phaser_feedback_var.get(),
            ds_knob_convolution_mix=self.ds_knob_convolution_mix_var.get(),
            ds_knob_pitch_shift=self.ds_knob_pitch_shift_var.get(),
            ds_knob_pitch_shift_mix=self.ds_knob_pitch_shift_mix_var.get(),
            ds_knob_wave_folder_drive=self.ds_knob_wave_folder_drive_var.get(),
            ds_knob_wave_folder_threshold=self.ds_knob_wave_folder_threshold_var.get(),
            ds_knob_wave_shaper_drive=self.ds_knob_wave_shaper_drive_var.get(),
            ds_knob_wave_shaper_boost=self.ds_knob_wave_shaper_boost_var.get(),
            ds_knob_wave_shaper_output=self.ds_knob_wave_shaper_output_var.get(),
            ds_knob_stereo_width=self.ds_knob_stereo_width_var.get(),
            ds_knob_bit_depth=self.ds_knob_bit_depth_var.get(),
            ds_knob_bit_crusher_rate=self.ds_knob_bit_crusher_rate_var.get(),
            ds_knob_bit_crusher_mix=self.ds_knob_bit_crusher_mix_var.get(),
            ui_layout=self.ui_layout,
        )

    def _write_preset(self) -> Path:
        samples = self._exportable_note_samples()
        preset = generate_dspreset(
            self.name_var.get(),
            self._instrument_dir(),
            samples,
            **self._dspreset_options(),
        )
        self._refresh_pitched_mappings()
        self._refresh_export_mapping()
        return preset

    def _on_output_parameter_changed(self) -> None:
        self._output_update_after_id = None
        self._redraw_ui_preview()
        if not self.samples:
            self._auto_save_project()
            return
        preset = self._write_preset()
        self._log(f"Updated DecentSampler patch: {preset.name}")
        self._auto_save_project()

    def _generate_preset(self) -> None:
        if not self.samples:
            messagebox.showwarning("SampleSmith", "No recorded samples yet.")
            return
        preset = self._write_preset()
        self._log(f"Generated {preset}")
        messagebox.showinfo("SampleSmith", f"Generated:\n{preset}")

    def _export_dsbundle(self) -> None:
        if not self.samples:
            messagebox.showwarning("SampleSmith", "No recorded samples yet.")
            return
        samples = self._exportable_note_samples()
        bundle = export_dsbundle(
            self.name_var.get(),
            self._instrument_dir(),
            samples,
            **self._dspreset_options(),
        )
        self._refresh_pitched_mappings()
        self._refresh_export_mapping()
        self._log(f"Exported DecentSampler bundle: {bundle}")
        messagebox.showinfo("SampleSmith", f"Exported .dsbundle:\n{bundle}")


class MappingEditorDialog(tk.Toplevel):
    def __init__(self, parent: SampleSmithApp, sample: SampleInfo, on_apply) -> None:
        super().__init__(parent)
        self.parent = parent
        self.sample = sample
        self.on_apply = on_apply
        self.title(f"Key mapping — {sample.path.name}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=sample.path.name, font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(
            outer,
            text="DecentSampler: pitch centre = rootNote; plays-on keys = loNote–hiNote.",
            foreground="#555555",
            wraplength=360,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self.root_var = tk.StringVar(value=midi_to_name(sample.root_note))
        self.lo_var = tk.StringVar(value=midi_to_name(sample.lo_note))
        self.hi_var = tk.StringVar(value=midi_to_name(sample.hi_note))
        self.preview_var = tk.StringVar(value="")

        for row, (label, variable) in enumerate(
            (("Root / pitch centre", self.root_var), ("Plays from", self.lo_var), ("Plays to", self.hi_var)),
            start=2,
        ):
            ttk.Label(outer, text=label).grid(row=row, column=0, sticky="w", pady=3)
            entry = ttk.Entry(outer, textvariable=variable, width=12)
            entry.grid(row=row, column=1, sticky="w", pady=3)
            variable.trace_add("write", lambda *_: self._refresh_preview())

        ttk.Label(outer, textvariable=self.preview_var, foreground="#555555").grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        buttons = ttk.Frame(outer)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Apply", command=self._apply).pack(side="right", padx=(0, 6))

        self._refresh_preview()
        self.wait_window(self)

    def _parse_note(self, value: str) -> int:
        value = value.strip()
        if not value:
            raise ValueError("Enter a DecentSampler key such as C4 or 72.")
        try:
            note = int(value)
        except ValueError:
            note = name_to_midi(value)
        if not 0 <= note <= 127:
            raise ValueError("DecentSampler key must be between 0 and 127.")
        return note

    def _current_values(self) -> tuple[int, int, int]:
        root = self._parse_note(self.root_var.get())
        lo = self._parse_note(self.lo_var.get())
        hi = self._parse_note(self.hi_var.get())
        if hi < lo:
            raise ValueError("'Plays to' must be the same as or higher than 'Plays from'.")
        return root, lo, hi

    def _refresh_preview(self) -> None:
        try:
            root, lo, hi = self._current_values()
        except ValueError:
            self.preview_var.set("Enter notes like C4 or DS key numbers like 72.")
            return
        self.preview_var.set(f"Will export root {midi_to_name(root)}; plays on {mapping_text(lo, hi)}")

    def _apply(self) -> None:
        try:
            root, lo, hi = self._current_values()
        except ValueError as exc:
            messagebox.showerror("SampleSmith", str(exc), parent=self)
            return
        self.sample.root_note = root
        self.sample.lo_note = lo
        self.sample.hi_note = hi
        self.sample.custom_mapping = True
        self.on_apply(self.sample)
        self.destroy()


class LoopEditorDialog(tk.Toplevel):
    def __init__(self, parent: SampleSmithApp, sample: SampleInfo, on_apply) -> None:
        super().__init__(parent)
        self.parent = parent
        self.sample = sample
        self.on_apply = on_apply
        self.title(f"Loop editor — {sample.path.name}")
        self.geometry("940x590")
        self.canvas_width = 880
        self.canvas_height = 220
        self.zoom_width = 420
        self.zoom_height = 120
        self.default_zoom_half_frames = 1200
        self.zoom_half_frames = 1200
        self.dragging: str | None = None
        self.audition_stop_event: threading.Event | None = None
        self.audition_thread: threading.Thread | None = None
        self.audition_mode: str | None = None
        self.audition_restart_after_id: str | None = None
        try:
            self.frames, self.sample_rate, self.peaks, self.waveform, self.audio = self._load_waveform(sample.path, self.canvas_width)
        except RuntimeError:
            self.destroy()
            raise
        self.transient(parent)
        self.grab_set()

        self.loop_enabled_var = tk.BooleanVar(value=bool(sample.loop_enabled))
        self.loop_start_var = tk.StringVar(value="" if sample.loop_start is None else str(sample.loop_start))
        self.loop_end_var = tk.StringVar(value="" if sample.loop_end is None else str(sample.loop_end))
        self.loop_crossfade_var = tk.DoubleVar(value=0.0 if sample.loop_crossfade is None else sample.loop_crossfade)
        self.loop_crossfade_mode_var = tk.StringVar(value=sample.loop_crossfade_mode or "equal_power")
        self.invert_wheel_zoom_var = tk.BooleanVar(value=False)
        self.visual_status_var = tk.StringVar(value="Crossfade display shows the fade-out tail before loop end and fade-in head after loop start.")
        self.audition_status_var = tk.StringVar(value="Audition raw exposes the end→start join; Audition xfade uses the current crossfade setting.")

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=str(sample.path), wraplength=900).pack(anchor="w")
        ttk.Label(outer, text=f"{self.frames:,} frames at {self.sample_rate:,} Hz").pack(anchor="w", pady=(2, 8))

        self.canvas = tk.Canvas(outer, width=self.canvas_width, height=self.canvas_height, bg="#101010", highlightthickness=1, highlightbackground="#666666")
        self.canvas.pack(fill="x")
        ttk.Label(outer, text="Left-click waveform to set loop start; right-click to set loop end. Drag the start/end lines to fine-tune.", foreground="#555555").pack(anchor="w", pady=(3, 0))
        ttk.Label(outer, textvariable=self.visual_status_var, foreground="#555555").pack(anchor="w", pady=(1, 0))
        self.canvas.bind("<Button-1>", self._set_loop_start_from_canvas)
        self.canvas.bind("<Button-3>", self._set_loop_end_from_canvas)
        self.canvas.bind("<B1-Motion>", self._drag_start)
        self.canvas.bind("<B3-Motion>", self._drag_end)

        zooms = ttk.Frame(outer)
        zooms.pack(fill="x", pady=(8, 0))
        start_zoom = ttk.LabelFrame(zooms, text="Loop start close-up — left-click to set start")
        start_zoom.pack(side="left", fill="x", expand=True, padx=(0, 6))
        end_zoom = ttk.LabelFrame(zooms, text="Loop end close-up — right-click to set end")
        end_zoom.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.start_zoom_canvas = tk.Canvas(start_zoom, width=self.zoom_width, height=self.zoom_height, bg="#101010", cursor="crosshair", highlightthickness=1, highlightbackground="#666666")
        self.start_zoom_canvas.pack(fill="x", padx=6, pady=6)
        self.end_zoom_canvas = tk.Canvas(end_zoom, width=self.zoom_width, height=self.zoom_height, bg="#101010", cursor="crosshair", highlightthickness=1, highlightbackground="#666666")
        self.end_zoom_canvas.pack(fill="x", padx=6, pady=6)
        self.start_zoom_canvas.bind("<Button-1>", lambda event: self._set_zoom_frame("start", event.x))
        self.end_zoom_canvas.bind("<Button-3>", lambda event: self._set_zoom_frame("end", event.x))
        for zoom_canvas in (self.start_zoom_canvas, self.end_zoom_canvas):
            zoom_canvas.bind("<MouseWheel>", self._on_closeup_mousewheel)
            zoom_canvas.bind("<Button-4>", self._on_closeup_mousewheel)
            zoom_canvas.bind("<Button-5>", self._on_closeup_mousewheel)

        zoom_controls = ttk.Frame(outer)
        zoom_controls.pack(fill="x", pady=(6, 0))
        ttk.Label(zoom_controls, text="Close-up zoom").pack(side="left")
        ttk.Button(zoom_controls, text="−", width=3, command=self._zoom_in_closeups).pack(side="left", padx=(6, 2))
        ttk.Button(zoom_controls, text="+", width=3, command=self._zoom_out_closeups).pack(side="left", padx=2)
        ttk.Button(zoom_controls, text="Reset", command=self._reset_closeup_zoom).pack(side="left", padx=(2, 8))
        self.zoom_status_var = tk.StringVar(value=self._zoom_status_text())
        ttk.Label(zoom_controls, textvariable=self.zoom_status_var, foreground="#555555").pack(side="left")
        ttk.Checkbutton(zoom_controls, text="Invert wheel zoom", variable=self.invert_wheel_zoom_var).pack(side="left", padx=(10, 0))

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=10)
        ttk.Checkbutton(controls, text="Loop this sample", variable=self.loop_enabled_var, command=self._draw).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(controls, text="start").grid(row=0, column=1, sticky="w")
        ttk.Entry(controls, textvariable=self.loop_start_var, width=12).grid(row=0, column=2, sticky="w", padx=(3, 12))
        ttk.Label(controls, text="end").grid(row=0, column=3, sticky="w")
        ttk.Entry(controls, textvariable=self.loop_end_var, width=12).grid(row=0, column=4, sticky="w", padx=(3, 12))
        ttk.Label(controls, text="crossfade").grid(row=0, column=5, sticky="w")
        ttk.Spinbox(controls, textvariable=self.loop_crossfade_var, from_=0, to=60000, increment=10, width=9).grid(row=0, column=6, sticky="w", padx=(3, 12))
        ttk.OptionMenu(controls, self.loop_crossfade_mode_var, self.loop_crossfade_mode_var.get(), "equal_power", "linear").grid(row=0, column=7, sticky="w")

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Import WAV marker", command=self._import_marker).pack(side="left")
        ttk.Button(buttons, text="Use visible middle 60%", command=self._use_middle).pack(side="left", padx=6)
        ttk.Button(buttons, text="Audition raw", command=lambda: self._start_loop_audition("raw")).pack(side="left", padx=6)
        ttk.Button(buttons, text="Audition xfade", command=lambda: self._start_loop_audition("xfade")).pack(side="left")
        ttk.Button(buttons, text="Stop", command=self._stop_loop_audition).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Clear sample loop", command=self._clear_loop).pack(side="left", padx=6)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Apply", command=self._apply).pack(side="right", padx=6)
        ttk.Label(outer, textvariable=self.audition_status_var, foreground="#555555").pack(anchor="w", pady=(6, 0))

        for var in (self.loop_start_var, self.loop_end_var, self.loop_crossfade_var, self.loop_crossfade_mode_var):
            var.trace_add("write", lambda *_args: self._on_loop_edit())
        self._draw()
        self.wait_window(self)

    def _load_waveform(self, path: Path, buckets: int):
        try:
            import numpy as np
            import soundfile as sf
        except ImportError as exc:
            raise RuntimeError("Loop editor needs soundfile and numpy installed. Run: python -m pip install -r requirements.txt") from exc
        try:
            audio, sample_rate = sf.read(path, always_2d=True, dtype="float32")
        except Exception as exc:
            raise RuntimeError(f"Could not read audio file for loop editing: {path}") from exc
        if audio.size == 0:
            raise RuntimeError(f"Cannot edit an empty audio file: {path}")
        mono = np.mean(audio, axis=1)
        abs_mono = np.abs(mono)
        frames = int(abs_mono.shape[0])
        bucket_size = max(1, math.ceil(frames / buckets))
        padded = np.pad(abs_mono, (0, bucket_size * buckets - frames), mode="constant")
        peaks = padded.reshape(buckets, bucket_size).max(axis=1)
        max_peak = float(peaks.max()) if peaks.size else 0.0
        if max_peak > 0:
            peaks = peaks / max_peak
        max_wave = float(np.max(np.abs(mono))) if mono.size else 0.0
        if max_wave > 0:
            mono = mono / max_wave
        return frames, int(sample_rate), [float(value) for value in peaks], [float(value) for value in mono], audio

    def _parse_frame(self, text: str | None, fallback: int) -> int:
        try:
            value = int(float((text or "").strip()))
        except ValueError:
            value = fallback
        return max(0, min(self.frames - 1, value))

    def _loop_points(self) -> tuple[int, int]:
        start = self._parse_frame(self.loop_start_var.get(), 0)
        end = self._parse_frame(self.loop_end_var.get(), self.frames - 1)
        if end <= start:
            end = min(self.frames - 1, start + 1)
        return start, end

    def _x_for_frame(self, frame: int) -> int:
        if self.frames <= 1:
            return 0
        return int(round(frame / (self.frames - 1) * (self.canvas_width - 1)))

    def _frame_for_x(self, x: int) -> int:
        x = max(0, min(self.canvas_width - 1, x))
        if self.frames <= 1:
            return 0
        return int(round(x / (self.canvas_width - 1) * (self.frames - 1)))

    def _zoom_window(self, center_frame: int) -> tuple[int, int]:
        left = max(0, center_frame - self.zoom_half_frames)
        right = min(self.frames - 1, center_frame + self.zoom_half_frames)
        if right <= left:
            right = min(self.frames - 1, left + 1)
        return left, right

    def _zoom_status_text(self) -> str:
        return f"±{self.zoom_half_frames:,} frames ({(self.zoom_half_frames / max(1, self.sample_rate)):.3f}s each side)"

    def _set_closeup_zoom(self, half_frames: int) -> None:
        self.zoom_half_frames = max(8, min(max(8, self.frames // 2), int(half_frames)))
        if hasattr(self, "zoom_status_var"):
            self.zoom_status_var.set(self._zoom_status_text())
        self._draw()

    def _zoom_in_closeups(self) -> None:
        self._set_closeup_zoom(max(8, self.zoom_half_frames // 2))

    def _zoom_out_closeups(self) -> None:
        self._set_closeup_zoom(self.zoom_half_frames * 2)

    def _reset_closeup_zoom(self) -> None:
        self._set_closeup_zoom(self.default_zoom_half_frames)

    def _on_closeup_mousewheel(self, event) -> str:
        if getattr(event, "num", None) == 4:
            zoom_in = True
        elif getattr(event, "num", None) == 5:
            zoom_in = False
        else:
            zoom_in = getattr(event, "delta", 0) > 0
        if self.invert_wheel_zoom_var.get():
            zoom_in = not zoom_in
        if zoom_in:
            self._zoom_in_closeups()
        else:
            self._zoom_out_closeups()
        return "break"

    def _zoom_frame_for_x(self, center_frame: int, x: int) -> int:
        left, right = self._zoom_window(center_frame)
        x = max(0, min(self.zoom_width - 1, x))
        return int(round(left + (x / (self.zoom_width - 1)) * (right - left)))

    def _requested_crossfade_frames(self) -> int:
        try:
            return max(0, int(float(self.loop_crossfade_var.get())))
        except (tk.TclError, ValueError):
            return 0

    def _effective_crossfade_frames(self, start: int, end: int) -> int:
        before, after = self._crossfade_halves(start, end)
        return before + after

    def _crossfade_halves(self, start: int, end: int) -> tuple[int, int]:
        requested = self._requested_crossfade_frames()
        return self._crossfade_halves_for_requested(requested, start, end)

    def _crossfade_halves_for_requested(self, requested: int, start: int, end: int) -> tuple[int, int]:
        if requested <= 0 or end <= start:
            return 0, 0
        wanted_before = requested // 2
        wanted_after = requested - wanted_before
        max_before = min(start, (end - start) // 2)
        max_after = min(max(0, self.frames - 1 - end), (end - start) // 2)
        scale = 1.0
        if wanted_before > 0:
            scale = min(scale, max_before / wanted_before)
        if wanted_after > 0:
            scale = min(scale, max_after / wanted_after)
        before = int(wanted_before * scale)
        after = int(wanted_after * scale)
        return max(0, before), max(0, after)

    def _crossfade_regions(self, start: int, end: int) -> tuple[int, int, tuple[int, int], tuple[int, int]]:
        before, after = self._crossfade_halves(start, end)
        effective = before + after
        return effective, before, (start - before, start + after), (end - before, end + after)

    def _x_for_zoom_frame(self, frame: int, left: int, right: int) -> int:
        span = max(1, right - left)
        return int(round((frame - left) / span * (self.zoom_width - 1)))

    def _draw(self) -> None:
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")
        mid = self.canvas_height // 2
        scale = (self.canvas_height // 2) - 14
        upper_points: list[int] = []
        lower_points: list[int] = []
        for x, peak in enumerate(self.peaks):
            y = int(peak * scale)
            upper_points.extend((x, mid - y))
            lower_points.extend((x, mid + y))
        if len(upper_points) >= 4:
            self.canvas.create_line(*upper_points, fill="#72b7ff", smooth=True, splinesteps=8)
            self.canvas.create_line(*lower_points, fill="#72b7ff", smooth=True, splinesteps=8)
        start, end = self._loop_points()
        start_x = self._x_for_frame(start)
        end_x = self._x_for_frame(end)
        if self.loop_enabled_var.get():
            self.canvas.create_rectangle(start_x, 0, end_x, self.canvas_height, fill="#24402c", stipple="gray25", outline="")
            crossfade, before, start_region, end_region = self._crossfade_regions(start, end)
            requested_crossfade = self._requested_crossfade_frames()
            if crossfade > 0:
                start_fade_x1 = self._x_for_frame(start_region[0])
                start_fade_x2 = self._x_for_frame(start_region[1])
                end_fade_x1 = self._x_for_frame(end_region[0])
                end_fade_x2 = self._x_for_frame(end_region[1])
                self.canvas.create_rectangle(end_fade_x1, 0, end_fade_x2, self.canvas_height, fill="#ffcc00", stipple="gray50", outline="#ffcc00")
                self.canvas.create_rectangle(start_fade_x1, 0, start_fade_x2, self.canvas_height, fill="#00c7be", stipple="gray50", outline="#00c7be")
                self.canvas.create_text(
                    max(6, min(self.canvas_width - 6, (end_fade_x1 + end_fade_x2) // 2)),
                    32,
                    text="xfade out",
                    fill="#ffcc00",
                )
                self.canvas.create_text(
                    max(6, min(self.canvas_width - 6, (start_fade_x1 + start_fade_x2) // 2)),
                    self.canvas_height - 32,
                    text="xfade in",
                    fill="#00c7be",
                )
                status = f"Crossfade visualised: {crossfade:,} frames centred on start/end ({before:,} before + {crossfade - before:,} after, {self.loop_crossfade_mode_var.get()})."
                if requested_crossfade != crossfade:
                    status += f" Requested {requested_crossfade:,} frames was clamped to half the loop length."
                self.visual_status_var.set(status)
            elif requested_crossfade > 0:
                self.visual_status_var.set("Crossfade is set, but the loop is too short to display an effective crossfade.")
            else:
                self.visual_status_var.set("Crossfade display is centred around the selected loop start/end points.")
        else:
            self.visual_status_var.set("Loop is disabled for this sample; enable it to visualise the loop region and crossfade.")
        self.canvas.create_line(start_x, 0, start_x, self.canvas_height, fill="#30d158", width=3, tags=("start",))
        self.canvas.create_line(end_x, 0, end_x, self.canvas_height, fill="#ff453a", width=3, tags=("end",))
        self.canvas.create_text(start_x + 4, 12, text=f"start {start}", anchor="w", fill="#30d158")
        self.canvas.create_text(end_x - 4, self.canvas_height - 12, text=f"end {end}", anchor="e", fill="#ff453a")
        if hasattr(self, "start_zoom_canvas"):
            self._draw_zoom(self.start_zoom_canvas, start, "#30d158", "start", start, end)
            self._draw_zoom(self.end_zoom_canvas, end, "#ff453a", "end", start, end)

    def _draw_zoom(self, canvas: tk.Canvas, center_frame: int, color: str, label: str, loop_start: int, loop_end: int) -> None:
        canvas.delete("all")
        mid = self.zoom_height // 2
        scale = (self.zoom_height // 2) - 12
        canvas.create_line(0, mid, self.zoom_width, mid, fill="#555555")
        left, right = self._zoom_window(center_frame)
        span = max(1, right - left)
        if self.loop_enabled_var.get():
            crossfade, _before, start_region, end_region = self._crossfade_regions(loop_start, loop_end)
            regions = [
                (loop_start, loop_end, "#24402c", "gray25"),
            ]
            if crossfade > 0:
                regions.extend(
                    [
                        (end_region[0], end_region[1], "#ffcc00", "gray50"),
                        (start_region[0], start_region[1], "#00c7be", "gray50"),
                    ]
                )
            for region_start, region_end, fill, stipple in regions:
                visible_start = max(left, region_start)
                visible_end = min(right, region_end)
                if visible_end > visible_start:
                    x1 = self._x_for_zoom_frame(visible_start, left, right)
                    x2 = self._x_for_zoom_frame(visible_end, left, right)
                    canvas.create_rectangle(x1, 0, x2, self.zoom_height, fill=fill, stipple=stipple, outline="")
        upper_points: list[int] = []
        lower_points: list[int] = []
        for x in range(self.zoom_width):
            start = left + int((x / self.zoom_width) * span)
            end = left + int(((x + 1) / self.zoom_width) * span)
            if end <= start:
                end = start + 1
            segment = self.waveform[start:min(end, self.frames)]
            if not segment:
                continue
            lo = min(segment)
            hi = max(segment)
            upper_points.extend((x, mid - int(hi * scale)))
            lower_points.extend((x, mid - int(lo * scale)))
        if len(upper_points) >= 4:
            canvas.create_line(*upper_points, fill="#72b7ff", smooth=True, splinesteps=8)
            canvas.create_line(*lower_points, fill="#72b7ff", smooth=True, splinesteps=8)
        center_x = int(round((center_frame - left) / span * (self.zoom_width - 1)))
        canvas.create_line(center_x, 0, center_x, self.zoom_height, fill=color, width=3)
        canvas.create_text(6, 12, text=f"{label} {center_frame}", anchor="w", fill=color)
        canvas.create_text(self.zoom_width - 6, self.zoom_height - 12, text=f"{left}–{right}", anchor="e", fill="#bbbbbb")

    def _set_zoom_frame(self, which: str, x: int) -> None:
        start, end = self._loop_points()
        center = start if which == "start" else end
        frame = self._zoom_frame_for_x(center, x)
        self.loop_enabled_var.set(True)
        if which == "start":
            self.loop_start_var.set(str(max(0, min(frame, end - 1))))
        else:
            self.loop_end_var.set(str(min(self.frames - 1, max(frame, start + 1))))

    def _set_loop_start_from_canvas(self, event) -> None:
        self.dragging = "start"
        self._drag_loop_point(event)

    def _set_loop_end_from_canvas(self, event) -> None:
        self.dragging = "end"
        self._drag_loop_point(event)

    def _drag_start(self, event) -> None:
        self.dragging = "start"
        self._drag_loop_point(event)

    def _drag_end(self, event) -> None:
        self.dragging = "end"
        self._drag_loop_point(event)

    def _drag_loop_point(self, event) -> None:
        self.loop_enabled_var.set(True)
        start, end = self._loop_points()
        frame = self._frame_for_x(event.x)
        if self.dragging == "start":
            start = min(frame, end - 1)
            self.loop_start_var.set(str(max(0, start)))
        else:
            end = max(frame, start + 1)
            self.loop_end_var.set(str(min(self.frames - 1, end)))

    def _end_drag(self, _event) -> None:
        self.dragging = None

    def _import_marker(self) -> None:
        marker = read_wav_smpl_loop_points(self.sample.path)
        if marker is None:
            messagebox.showinfo("SampleSmith", "No embedded WAV smpl loop marker found in this audio file.")
            return
        start, end = marker
        self.loop_enabled_var.set(True)
        self.loop_start_var.set(str(start))
        self.loop_end_var.set(str(end))
        self._draw()

    def _use_middle(self) -> None:
        self.loop_enabled_var.set(True)
        self.loop_start_var.set(str(max(0, int(self.frames * 0.2))))
        self.loop_end_var.set(str(min(self.frames - 1, int(self.frames * 0.8))))
        self._draw()

    def _clear_loop(self) -> None:
        self._stop_loop_audition()
        self.loop_enabled_var.set(False)
        self.loop_start_var.set("")
        self.loop_end_var.set("")
        self.loop_crossfade_var.set(0.0)
        self.loop_crossfade_mode_var.set("equal_power")
        self._draw()

    def _set_audition_status(self, text: str) -> None:
        if self.winfo_exists():
            self.audition_status_var.set(text)

    def _on_loop_edit(self) -> None:
        self._draw()
        self._schedule_audition_restart()

    def _schedule_audition_restart(self) -> None:
        if self.audition_mode is None:
            return
        if self.audition_restart_after_id is not None:
            self.after_cancel(self.audition_restart_after_id)
        self.audition_restart_after_id = self.after(250, self._restart_loop_audition)

    def _restart_loop_audition(self) -> None:
        self.audition_restart_after_id = None
        mode = self.audition_mode
        if mode is None:
            return
        self._stop_loop_audition(join=False, keep_mode=True, update_status=False)
        self._start_loop_audition(mode, automatic=True)

    def _start_loop_audition(self, mode: str = "raw", automatic: bool = False) -> None:
        if self.audition_restart_after_id is not None:
            self.after_cancel(self.audition_restart_after_id)
            self.audition_restart_after_id = None
        start, end = self._loop_points()
        if end <= start + 8:
            if automatic:
                self._set_audition_status("Loop edit made the region too short to audition. Adjust the loop or press Stop.")
            else:
                messagebox.showwarning("SampleSmith", "Choose a longer loop region before auditioning.")
            return
        crossfade = 0
        if mode == "xfade":
            try:
                crossfade = int(float(self.loop_crossfade_var.get()))
            except (TypeError, ValueError, tk.TclError):
                crossfade = 0
            if crossfade <= 0:
                if automatic:
                    self._set_audition_status("Crossfade audition is still active, but crossfade is now 0. Increase it or press Stop.")
                else:
                    messagebox.showwarning("SampleSmith", "Set a crossfade above 0 before auditioning with crossfade.")
                return
        self.loop_enabled_var.set(True)
        self.audition_mode = mode
        self._stop_loop_audition(join=False, keep_mode=True, update_status=False)
        stop_event = threading.Event()
        self.audition_stop_event = stop_event
        self.audition_thread = threading.Thread(
            target=self._loop_audition_worker,
            args=(start, end, mode, crossfade, self.loop_crossfade_mode_var.get(), stop_event),
            daemon=True,
        )
        self.audition_thread.start()
        if mode == "xfade":
            self._set_audition_status(f"Auditioning crossfaded loop {start}–{end}, xfade {crossfade} ({self.loop_crossfade_mode_var.get()}). Press Stop to end playback.")
        else:
            self._set_audition_status(f"Auditioning raw loop {start}–{end}. Press Stop to end playback.")

    def _stop_loop_audition(self, join: bool = True, keep_mode: bool = False, update_status: bool = True) -> None:
        if not keep_mode and self.audition_restart_after_id is not None:
            self.after_cancel(self.audition_restart_after_id)
            self.audition_restart_after_id = None
        if self.audition_stop_event is not None:
            self.audition_stop_event.set()
        try:
            import sounddevice as sd

            sd.stop()
        except Exception:
            pass
        if join and self.audition_thread is not None and self.audition_thread.is_alive():
            self.audition_thread.join(timeout=0.3)
        self.audition_thread = None
        self.audition_stop_event = None
        if not keep_mode:
            self.audition_mode = None
        if update_status and hasattr(self, "audition_status_var"):
            self._set_audition_status("Audition stopped. Audition raw exposes the join; Audition xfade uses the current crossfade setting.")

    def _loop_audition_worker(
        self,
        start: int,
        end: int,
        mode: str,
        crossfade: int,
        crossfade_mode: str,
        stop_event: threading.Event,
    ) -> None:
        try:
            import sounddevice as sd
        except ImportError:
            self.after(0, self._set_audition_status, "Loop audition needs sounddevice. Run: python -m pip install -r requirements.txt")
            return

        try:
            pre_roll = int(self.sample_rate * 0.35)
            intro_start = max(0, start - pre_roll)
            chunk_frames = max(1, int(self.sample_rate * 0.08))
            if mode == "xfade":
                cycle, _effective_crossfade, before, _after = self._crossfaded_loop_cycle(start, end, crossfade, crossfade_mode)
                intro = self.audio[intro_start:max(start, end - before)]
            else:
                cycle = self.audio[start:end]
                intro = self.audio[intro_start:end]
            channels = 1 if cycle.ndim == 1 else cycle.shape[1]
            with sd.OutputStream(samplerate=self.sample_rate, channels=channels, dtype="float32") as stream:
                if intro.size:
                    self._write_audio_chunks(stream, intro, chunk_frames, stop_event)
                while not stop_event.is_set():
                    self._write_audio_chunks(stream, cycle, chunk_frames, stop_event)
        except Exception as exc:
            self.after(0, self._set_audition_status, f"Loop audition failed: {exc}")
        finally:
            if not stop_event.is_set():
                self.after(0, self._set_audition_status, "Audition finished.")

    def _write_audio_chunks(self, stream, audio, chunk_frames: int, stop_event: threading.Event) -> None:
        position = 0
        while position < audio.shape[0] and not stop_event.is_set():
            stream.write(audio[position:position + chunk_frames])
            position += chunk_frames

    def _crossfaded_loop_cycle(self, start: int, end: int, crossfade: int, mode: str):
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Crossfade audition needs numpy. Run: python -m pip install -r requirements.txt") from exc

        before, after = self._crossfade_halves_for_requested(max(0, int(crossfade)), start, end)
        effective = before + after
        if effective < 1:
            return self.audio[start:end], 0, 0, 0
        tail = self.audio[end - before:end + after]
        head = self.audio[start - before:start + after]
        if mode == "linear":
            fade_out = np.linspace(1.0, 0.0, effective, endpoint=False, dtype="float32")
            fade_in = np.linspace(0.0, 1.0, effective, endpoint=False, dtype="float32")
        else:
            theta = np.linspace(0.0, np.pi / 2.0, effective, endpoint=False, dtype="float32")
            fade_out = np.cos(theta).astype("float32")
            fade_in = np.sin(theta).astype("float32")
        if tail.ndim == 2:
            fade_out = fade_out[:, None]
            fade_in = fade_in[:, None]
        transition = (tail * fade_out + head * fade_in).astype("float32")
        body = self.audio[start + after:end - before]
        if body.size:
            return np.concatenate([transition, body], axis=0).astype("float32"), effective, before, after
        return transition, effective, before, after

    def _has_typed_loop_points(self) -> bool:
        start_text = self.loop_start_var.get().strip()
        end_text = self.loop_end_var.get().strip()
        if not start_text or not end_text:
            return False
        try:
            start = int(float(start_text))
            end = int(float(end_text))
        except ValueError:
            return False
        return 0 <= start < end

    def _apply(self) -> None:
        self._stop_loop_audition()
        if self.loop_enabled_var.get() or self._has_typed_loop_points():
            start, end = self._loop_points()
            self.sample.loop_enabled = True
            self.sample.loop_start = start
            self.sample.loop_end = end
            self.sample.loop_crossfade = max(0.0, min(60000.0, float(self.loop_crossfade_var.get())))
            mode = self.loop_crossfade_mode_var.get()
            self.sample.loop_crossfade_mode = mode if mode in {"linear", "equal_power"} else "equal_power"
        else:
            self.sample.loop_enabled = False
            self.sample.loop_start = None
            self.sample.loop_end = None
            self.sample.loop_crossfade = None
            self.sample.loop_crossfade_mode = None
        self.on_apply(self.sample)
        self.destroy()

    def destroy(self) -> None:
        self._stop_loop_audition()
        super().destroy()


def main() -> None:
    app = SampleSmithApp()
    app.mainloop()
