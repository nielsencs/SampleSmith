"""DecentSampler UI preview/editor widget for SampleSmith."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Protocol

from .dspreset import (
    DECENT_SAMPLER_UI_HEIGHT,
    DECENT_SAMPLER_UI_WIDTH,
    UI_KNOB_COLUMNS,
    UI_KNOB_MAX_X,
    UI_KNOB_MAX_Y,
    UI_KNOB_WIDTH,
    ui_layout_position,
)


class UiPreviewOwner(Protocol):
    ui_layout: dict[str, dict[str, int]]
    name_var: tk.StringVar
    amp_env_enabled_var: tk.BooleanVar
    ds_knob_amp_env_var: tk.BooleanVar
    lowpass_enabled_var: tk.BooleanVar
    ds_knob_tone_var: tk.BooleanVar
    filter_type_var: tk.StringVar
    ds_knob_filter_resonance_var: tk.BooleanVar
    notch_enabled_var: tk.BooleanVar
    ds_knob_notch_frequency_var: tk.BooleanVar
    ds_knob_notch_q_var: tk.BooleanVar
    peak_enabled_var: tk.BooleanVar
    ds_knob_peak_frequency_var: tk.BooleanVar
    ds_knob_peak_q_var: tk.BooleanVar
    ds_knob_peak_gain_var: tk.BooleanVar
    gain_enabled_var: tk.BooleanVar
    ds_knob_gain_level_var: tk.BooleanVar
    reverb_enabled_var: tk.BooleanVar
    ds_knob_reverb_wet_var: tk.BooleanVar
    ds_knob_reverb_room_var: tk.BooleanVar
    ds_knob_reverb_damping_var: tk.BooleanVar
    delay_enabled_var: tk.BooleanVar
    ds_knob_delay_wet_var: tk.BooleanVar
    ds_knob_delay_time_var: tk.BooleanVar
    ds_knob_delay_stereo_offset_var: tk.BooleanVar
    ds_knob_delay_feedback_var: tk.BooleanVar
    chorus_enabled_var: tk.BooleanVar
    ds_knob_chorus_mix_var: tk.BooleanVar
    ds_knob_chorus_depth_var: tk.BooleanVar
    ds_knob_chorus_rate_var: tk.BooleanVar
    phaser_enabled_var: tk.BooleanVar
    ds_knob_phaser_mix_var: tk.BooleanVar
    ds_knob_phaser_depth_var: tk.BooleanVar
    ds_knob_phaser_rate_var: tk.BooleanVar
    ds_knob_phaser_frequency_var: tk.BooleanVar
    ds_knob_phaser_feedback_var: tk.BooleanVar
    convolution_enabled_var: tk.BooleanVar
    ds_knob_convolution_mix_var: tk.BooleanVar
    pitch_shift_enabled_var: tk.BooleanVar
    ds_knob_pitch_shift_var: tk.BooleanVar
    ds_knob_pitch_shift_mix_var: tk.BooleanVar
    wave_folder_enabled_var: tk.BooleanVar
    ds_knob_wave_folder_drive_var: tk.BooleanVar
    ds_knob_wave_folder_threshold_var: tk.BooleanVar
    wave_shaper_enabled_var: tk.BooleanVar
    ds_knob_wave_shaper_drive_var: tk.BooleanVar
    ds_knob_wave_shaper_boost_var: tk.BooleanVar
    ds_knob_wave_shaper_output_var: tk.BooleanVar
    stereo_simulator_enabled_var: tk.BooleanVar
    ds_knob_stereo_width_var: tk.BooleanVar
    bit_crusher_enabled_var: tk.BooleanVar
    ds_knob_bit_depth_var: tk.BooleanVar
    ds_knob_bit_crusher_rate_var: tk.BooleanVar
    ds_knob_bit_crusher_mix_var: tk.BooleanVar

    def _auto_save_project(self) -> None: ...
    def _on_output_parameter_changed(self) -> None: ...


def normalise_ui_layout(raw_layout: object) -> dict[str, dict[str, int]]:
    if not isinstance(raw_layout, dict):
        return {}
    layout: dict[str, dict[str, int]] = {}
    for control_id, raw_pos in raw_layout.items():
        if not isinstance(control_id, str) or not isinstance(raw_pos, dict):
            continue
        try:
            x = int(float(raw_pos.get("x", 0)))
            y = int(float(raw_pos.get("y", 0)))
        except (TypeError, ValueError):
            continue
        layout[control_id] = {
            "x": max(0, min(UI_KNOB_MAX_X, x)),
            "y": max(0, min(UI_KNOB_MAX_Y, y)),
        }
    return layout


class DecentSamplerUiPreview:
    def __init__(self, parent: ttk.Frame, owner: UiPreviewOwner) -> None:
        self.owner = owner
        self.canvas_items: dict[str, list[int]] = {}
        self.drag: dict[str, int | str] | None = None

        tools = ttk.Frame(parent)
        tools.pack(fill="x", pady=(0, 6))
        ttk.Label(
            tools,
            text="Drag knobs in the 812×375 DecentSampler panel. Positions save with the project and export to the .dspreset.",
        ).pack(side="left")
        ttk.Button(tools, text="Reset layout", command=self.reset_layout).pack(side="right", padx=(6, 0))
        ttk.Button(tools, text="Refresh", command=self.redraw).pack(side="right")
        self.canvas = tk.Canvas(
            parent,
            width=DECENT_SAMPLER_UI_WIDTH,
            height=DECENT_SAMPLER_UI_HEIGHT,
            background="#f6f0e6",
            highlightthickness=1,
            highlightbackground="#999999",
        )
        self.canvas.pack(anchor="nw")
        self.status_var = tk.StringVar(value="No visible knobs yet. Enable effects and K boxes to add controls.")
        ttk.Label(parent, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))
        self.redraw()

    def visible_controls(self) -> list[dict[str, object]]:
        controls: list[dict[str, object]] = []
        index = 0
        owner = self.owner

        def add_group(title: str, specs: list[tuple[bool, str, str]]) -> None:
            nonlocal index
            included = [(control_id, label) for include, control_id, label in specs if include]
            if not included:
                return
            if (index % UI_KNOB_COLUMNS) + len(included) > UI_KNOB_COLUMNS:
                index += UI_KNOB_COLUMNS - (index % UI_KNOB_COLUMNS)
            for control_id, label in included:
                x, y = ui_layout_position(control_id, index, owner.ui_layout)
                controls.append({"id": control_id, "label": label, "group": title, "index": index, "x": x, "y": y})
                index += 1

        add_group(
            "Envelope",
            [
                (owner.amp_env_enabled_var.get() and owner.ds_knob_amp_env_var.get(), "amp_attack", "Attack"),
                (owner.amp_env_enabled_var.get() and owner.ds_knob_amp_env_var.get(), "amp_decay", "Decay"),
                (owner.amp_env_enabled_var.get() and owner.ds_knob_amp_env_var.get(), "amp_sustain", "Sustain"),
                (owner.amp_env_enabled_var.get() and owner.ds_knob_amp_env_var.get(), "amp_release", "Release"),
            ],
        )
        add_group(
            "Tone",
            [
                (owner.lowpass_enabled_var.get() and owner.ds_knob_tone_var.get(), "filter_tone", "Tone"),
                (owner.lowpass_enabled_var.get() and owner.filter_type_var.get() != "lowpass_1pl" and owner.ds_knob_filter_resonance_var.get(), "filter_resonance", "Res"),
            ],
        )
        add_group("Notch", [(owner.notch_enabled_var.get() and owner.ds_knob_notch_frequency_var.get(), "notch_frequency", "Frequency"), (owner.notch_enabled_var.get() and owner.ds_knob_notch_q_var.get(), "notch_q", "Q")])
        add_group("Peak", [(owner.peak_enabled_var.get() and owner.ds_knob_peak_frequency_var.get(), "peak_frequency", "Frequency"), (owner.peak_enabled_var.get() and owner.ds_knob_peak_q_var.get(), "peak_q", "Q"), (owner.peak_enabled_var.get() and owner.ds_knob_peak_gain_var.get(), "peak_gain", "Gain")])
        add_group("Gain", [(owner.gain_enabled_var.get() and owner.ds_knob_gain_level_var.get(), "gain_level", "Level")])
        add_group("Reverb", [(owner.reverb_enabled_var.get() and owner.ds_knob_reverb_wet_var.get(), "reverb_wet", "Amount"), (owner.reverb_enabled_var.get() and owner.ds_knob_reverb_room_var.get(), "reverb_room", "Room"), (owner.reverb_enabled_var.get() and owner.ds_knob_reverb_damping_var.get(), "reverb_damping", "Damp")])
        add_group("Delay", [(owner.delay_enabled_var.get() and owner.ds_knob_delay_wet_var.get(), "delay_wet", "Amount"), (owner.delay_enabled_var.get() and owner.ds_knob_delay_time_var.get(), "delay_time", "Time"), (owner.delay_enabled_var.get() and owner.ds_knob_delay_stereo_offset_var.get(), "delay_offset", "Offset"), (owner.delay_enabled_var.get() and owner.ds_knob_delay_feedback_var.get(), "delay_feedback", "Feedback")])
        add_group("Chorus", [(owner.chorus_enabled_var.get() and owner.ds_knob_chorus_mix_var.get(), "chorus_mix", "Amount"), (owner.chorus_enabled_var.get() and owner.ds_knob_chorus_depth_var.get(), "chorus_depth", "Depth"), (owner.chorus_enabled_var.get() and owner.ds_knob_chorus_rate_var.get(), "chorus_rate", "Rate")])
        add_group("Phaser", [(owner.phaser_enabled_var.get() and owner.ds_knob_phaser_mix_var.get(), "phaser_mix", "Amount"), (owner.phaser_enabled_var.get() and owner.ds_knob_phaser_depth_var.get(), "phaser_depth", "Depth"), (owner.phaser_enabled_var.get() and owner.ds_knob_phaser_rate_var.get(), "phaser_rate", "Rate"), (owner.phaser_enabled_var.get() and owner.ds_knob_phaser_frequency_var.get(), "phaser_frequency", "Freq"), (owner.phaser_enabled_var.get() and owner.ds_knob_phaser_feedback_var.get(), "phaser_feedback", "Feedback")])
        add_group("IR Verb", [(owner.convolution_enabled_var.get() and owner.ds_knob_convolution_mix_var.get(), "convolution_mix", "Amount")])
        add_group("Pitch", [(owner.pitch_shift_enabled_var.get() and owner.ds_knob_pitch_shift_var.get(), "pitch_shift", "Semitones"), (owner.pitch_shift_enabled_var.get() and owner.ds_knob_pitch_shift_mix_var.get(), "pitch_shift_mix", "Mix")])
        add_group("Folder", [(owner.wave_folder_enabled_var.get() and owner.ds_knob_wave_folder_drive_var.get(), "wave_folder_drive", "Drive"), (owner.wave_folder_enabled_var.get() and owner.ds_knob_wave_folder_threshold_var.get(), "wave_folder_threshold", "Threshold")])
        add_group("Shaper", [(owner.wave_shaper_enabled_var.get() and owner.ds_knob_wave_shaper_drive_var.get(), "wave_shaper_drive", "Drive"), (owner.wave_shaper_enabled_var.get() and owner.ds_knob_wave_shaper_boost_var.get(), "wave_shaper_boost", "Boost"), (owner.wave_shaper_enabled_var.get() and owner.ds_knob_wave_shaper_output_var.get(), "wave_shaper_output", "Out")])
        add_group("Stereo", [(owner.stereo_simulator_enabled_var.get() and owner.ds_knob_stereo_width_var.get(), "stereo_width", "Width")])
        add_group("Bits", [(owner.bit_crusher_enabled_var.get() and owner.ds_knob_bit_depth_var.get(), "bit_depth", "Depth"), (owner.bit_crusher_enabled_var.get() and owner.ds_knob_bit_crusher_rate_var.get(), "bit_rate", "Rate"), (owner.bit_crusher_enabled_var.get() and owner.ds_knob_bit_crusher_mix_var.get(), "bit_mix", "Mix")])
        return controls

    def redraw(self) -> None:
        self.canvas.delete("all")
        self.canvas_items = {}
        self.canvas.create_rectangle(0, 0, DECENT_SAMPLER_UI_WIDTH, DECENT_SAMPLER_UI_HEIGHT, fill="#f6f0e6", outline="#999999")
        self.canvas.create_text(
            DECENT_SAMPLER_UI_WIDTH // 2,
            26,
            text=self.owner.name_var.get(),
            fill="#330033",
            font=("TkDefaultFont", 18, "bold"),
        )
        controls = self.visible_controls()
        for control in controls:
            self._draw_knob(str(control["id"]), str(control["label"]), str(control["group"]), int(control["x"]), int(control["y"]))
        if controls:
            self.status_var.set(f"{len(controls)} visible DecentSampler knob(s). Drag knobs to adjust exported positions.")
        else:
            self.status_var.set("No visible knobs yet. Enable effects and K boxes to add controls.")

    def _draw_knob(self, control_id: str, label: str, group: str, x: int, y: int) -> None:
        tag = f"ui:{control_id}"
        items = [
            self.canvas.create_text(x + UI_KNOB_WIDTH // 2, y - 8, text=group, fill="#664466", font=("TkDefaultFont", 9), tags=(tag, "ui-knob")),
            self.canvas.create_oval(x + 10, y + 4, x + UI_KNOB_WIDTH - 10, y + UI_KNOB_WIDTH - 16, fill="#d9d2c8", outline="#330033", width=2, tags=(tag, "ui-knob")),
            self.canvas.create_line(x + UI_KNOB_WIDTH // 2, y + 14, x + UI_KNOB_WIDTH // 2, y + 28, fill="#330033", width=2, tags=(tag, "ui-knob")),
            self.canvas.create_text(x + UI_KNOB_WIDTH // 2, y + UI_KNOB_WIDTH - 4, text=label, fill="#330033", font=("TkDefaultFont", 10), tags=(tag, "ui-knob")),
        ]
        self.canvas_items[control_id] = items
        self.canvas.tag_bind(tag, "<ButtonPress-1>", self._start_drag)
        self.canvas.tag_bind(tag, "<B1-Motion>", self._drag_knob)
        self.canvas.tag_bind(tag, "<ButtonRelease-1>", self._end_drag)

    def _control_id_from_event(self) -> str | None:
        current = self.canvas.find_withtag("current")
        if not current:
            return None
        for tag in self.canvas.gettags(current[0]):
            if tag.startswith("ui:"):
                return tag[3:]
        return None

    def _start_drag(self, event) -> None:
        control_id = self._control_id_from_event()
        if not control_id:
            return
        items = self.canvas_items.get(control_id, [])
        bbox = self.canvas.bbox(*items) if items else None
        if not bbox:
            return
        self.drag = {"id": control_id, "x": int(event.x), "y": int(event.y)}

    def _drag_knob(self, event) -> None:
        if not self.drag:
            return
        control_id = str(self.drag["id"])
        current = self.owner.ui_layout.get(control_id)
        if current is None:
            controls = {str(control["id"]): control for control in self.visible_controls()}
            control = controls.get(control_id)
            if control is None:
                return
            current = {"x": int(control["x"]), "y": int(control["y"])}
        new_x = max(0, min(UI_KNOB_MAX_X, current["x"] + int(event.x) - int(self.drag["x"])))
        new_y = max(16, min(UI_KNOB_MAX_Y, current["y"] + int(event.y) - int(self.drag["y"])))
        dx = new_x - current["x"]
        dy = new_y - current["y"]
        if dx == 0 and dy == 0:
            return
        for item in self.canvas_items.get(control_id, []):
            self.canvas.move(item, dx, dy)
        self.owner.ui_layout[control_id] = {"x": new_x, "y": new_y}
        self.drag["x"] = int(event.x)
        self.drag["y"] = int(event.y)

    def _end_drag(self, _event) -> None:
        if self.drag:
            self.drag = None
            self.owner._auto_save_project()
            self.owner._on_output_parameter_changed()

    def reset_layout(self) -> None:
        self.owner.ui_layout = {}
        self.redraw()
        self.owner._auto_save_project()
        self.owner._on_output_parameter_changed()
