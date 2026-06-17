"""DecentSampler UI preview/editor widget for SampleSmith."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Protocol

from .dspreset import (
    DECENT_SAMPLER_UI_HEIGHT,
    DECENT_SAMPLER_UI_WIDTH,
    UI_KNOB_COLUMNS,
    UI_KNOB_MIN_Y,
    UI_KNOB_MAX_X,
    UI_KNOB_MAX_Y,
    UI_KNOB_WIDTH,
    ui_layout_position,
)

BARE_LAYOUT_IMAGE = Path(__file__).resolve().parent / "assets" / "decent_sampler_bare_layout.png"
PREVIEW_ORIGIN_X = 0
PREVIEW_ORIGIN_Y = 51


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
            "y": max(UI_KNOB_MIN_Y, min(UI_KNOB_MAX_Y, y)),
        }
    return layout


class DecentSamplerUiPreview:
    def __init__(self, parent: ttk.Frame, owner: UiPreviewOwner) -> None:
        self.owner = owner
        self.canvas_items: dict[str, list[int]] = {}
        self.panel_items: dict[str, list[int]] = {}
        self.panel_controls: dict[str, list[str]] = {}
        self.panel_tags: dict[str, str] = {}
        self.drag: dict[str, int | str] | None = None
        self.background_image: tk.PhotoImage | None = None
        if BARE_LAYOUT_IMAGE.exists():
            self.background_image = tk.PhotoImage(file=str(BARE_LAYOUT_IMAGE))

        tools = ttk.Frame(parent)
        tools.pack(fill="x", pady=(0, 6))
        ttk.Label(
            tools,
            text="Drag knobs in the 812×375 DecentSampler panel. Positions save with the project and export to the .dspreset.",
        ).pack(side="left")
        ttk.Button(tools, text="Reset layout", command=self.reset_layout).pack(side="right", padx=(6, 0))
        ttk.Button(tools, text="Tidy groups", command=self.tidy_groups).pack(side="right", padx=(6, 0))
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
        self.panel_items = {}
        self.panel_controls = {}
        self.panel_tags = {}
        if self.background_image is not None:
            self.canvas.create_image(0, 0, anchor="nw", image=self.background_image)
        else:
            self.canvas.create_rectangle(0, 0, DECENT_SAMPLER_UI_WIDTH, DECENT_SAMPLER_UI_HEIGHT, fill="#f6f0e6", outline="#999999")
            self.canvas.create_text(
                DECENT_SAMPLER_UI_WIDTH // 2,
                26,
                text=self.owner.name_var.get(),
                fill="#330033",
                font=("TkDefaultFont", 18, "bold"),
            )
        controls = self.visible_controls()
        self._draw_group_panels(controls)
        for control in controls:
            self._draw_knob(str(control["id"]), str(control["label"]), str(control["group"]), int(control["x"]), int(control["y"]))
        if controls:
            self.status_var.set(f"{len(controls)} visible DecentSampler knob(s). Drag knobs/groups, or double-click a group rectangle to tidy it.")
        else:
            self.status_var.set("No visible knobs yet. Enable effects and K boxes to add controls.")

    def _draw_group_panels(self, controls: list[dict[str, object]]) -> None:
        groups: dict[str, list[dict[str, object]]] = {}
        for control in controls:
            groups.setdefault(str(control["group"]), []).append(control)
        for panel_index, (title, group_controls) in enumerate(groups.items()):
            panel_tag = f"ui-panel:{panel_index}"
            self.panel_tags[panel_tag] = title
            self.panel_controls[title] = [str(control["id"]) for control in group_controls]
            left = min(int(control["x"]) + PREVIEW_ORIGIN_X for control in group_controls)
            top = min(int(control["y"]) + PREVIEW_ORIGIN_Y for control in group_controls)
            right = max(int(control["x"]) + PREVIEW_ORIGIN_X + UI_KNOB_WIDTH for control in group_controls)
            bottom = max(int(control["y"]) + PREVIEW_ORIGIN_Y + UI_KNOB_WIDTH for control in group_controls)
            x1 = max(0, left - 10)
            y1 = max(0, top - 28)
            x2 = min(DECENT_SAMPLER_UI_WIDTH, right + 10)
            y2 = min(DECENT_SAMPLER_UI_HEIGHT, bottom + 8)
            rectangle = self.canvas.create_rectangle(x1, y1, x2, y2, fill="#eee6dc", outline="#8a6a82", stipple="gray25", tags=(panel_tag, "ui-panel"))
            label = self.canvas.create_text(
                x1 + (x2 - x1) // 2,
                y1 + 12,
                text=title,
                fill="#330033",
                font=("TkDefaultFont", 10),
                tags=(panel_tag, "ui-panel"),
            )
            self.panel_items[title] = [rectangle, label]
            self.canvas.tag_bind(panel_tag, "<ButtonPress-1>", self._start_panel_drag)
            self.canvas.tag_bind(panel_tag, "<B1-Motion>", self._drag_panel)
            self.canvas.tag_bind(panel_tag, "<ButtonRelease-1>", self._end_drag)
            self.canvas.tag_bind(panel_tag, "<Double-Button-1>", self._tidy_panel_from_event)

    def _draw_knob(self, control_id: str, label: str, group: str, x: int, y: int) -> None:
        tag = f"ui:{control_id}"
        canvas_x = x + PREVIEW_ORIGIN_X
        canvas_y = y + PREVIEW_ORIGIN_Y
        knob_left = canvas_x + 18
        knob_top = canvas_y + 18
        knob_right = canvas_x + UI_KNOB_WIDTH - 18
        knob_bottom = canvas_y + UI_KNOB_WIDTH - 22
        items = [
            self.canvas.create_rectangle(canvas_x, canvas_y, canvas_x + UI_KNOB_WIDTH, canvas_y + UI_KNOB_WIDTH, outline="#c8b9c5", dash=(2, 2), tags=(tag, "ui-knob")),
            self.canvas.create_text(canvas_x + UI_KNOB_WIDTH // 2, canvas_y + 10, text=label, fill="#330033", font=("TkDefaultFont", 10), tags=(tag, "ui-knob")),
            self.canvas.create_oval(knob_left, knob_top, knob_right, knob_bottom, fill="#d9d2c8", outline="#330033", width=2, tags=(tag, "ui-knob")),
            self.canvas.create_line(canvas_x + UI_KNOB_WIDTH // 2, knob_top + 8, canvas_x + UI_KNOB_WIDTH // 2, knob_top + 25, fill="#330033", width=2, tags=(tag, "ui-knob")),
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

    def _panel_title_from_event(self) -> str | None:
        current = self.canvas.find_withtag("current")
        if not current:
            return None
        for tag in self.canvas.gettags(current[0]):
            if tag in self.panel_tags:
                return self.panel_tags[tag]
        return None

    def _current_control_positions(self) -> dict[str, dict[str, int]]:
        controls = {str(control["id"]): control for control in self.visible_controls()}
        positions: dict[str, dict[str, int]] = {}
        for control_id, control in controls.items():
            current = self.owner.ui_layout.get(control_id)
            if current is None:
                positions[control_id] = {"x": int(control["x"]), "y": int(control["y"])}
            else:
                positions[control_id] = {"x": int(current["x"]), "y": int(current["y"])}
        return positions

    def _controls_by_group(self) -> dict[str, list[dict[str, object]]]:
        groups: dict[str, list[dict[str, object]]] = {}
        for control in self.visible_controls():
            groups.setdefault(str(control["group"]), []).append(control)
        for group_controls in groups.values():
            group_controls.sort(key=lambda control: int(control["index"]))
        return groups

    def _start_drag(self, event) -> None:
        control_id = self._control_id_from_event()
        if not control_id:
            return
        items = self.canvas_items.get(control_id, [])
        bbox = self.canvas.bbox(*items) if items else None
        if not bbox:
            return
        self.drag = {"id": control_id, "x": int(event.x), "y": int(event.y)}

    def _start_panel_drag(self, event) -> None:
        title = self._panel_title_from_event()
        if not title:
            return
        items = self.panel_items.get(title, [])
        bbox = self.canvas.bbox(*items) if items else None
        if not bbox:
            return
        self.drag = {"kind": "panel", "group": title, "x": int(event.x), "y": int(event.y)}

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
        new_y = max(UI_KNOB_MIN_Y, min(UI_KNOB_MAX_Y, current["y"] + int(event.y) - int(self.drag["y"])))
        dx = new_x - current["x"]
        dy = new_y - current["y"]
        if dx == 0 and dy == 0:
            return
        for item in self.canvas_items.get(control_id, []):
            self.canvas.move(item, dx, dy)
        self.owner.ui_layout[control_id] = {"x": new_x, "y": new_y}
        self.drag["x"] = int(event.x)
        self.drag["y"] = int(event.y)

    def _drag_panel(self, event) -> None:
        if not self.drag or self.drag.get("kind") != "panel":
            return
        title = str(self.drag["group"])
        control_ids = self.panel_controls.get(title, [])
        positions = self._current_control_positions()
        current_positions = [positions[control_id] for control_id in control_ids if control_id in positions]
        if not current_positions:
            return
        requested_dx = int(event.x) - int(self.drag["x"])
        requested_dy = int(event.y) - int(self.drag["y"])
        min_x = min(pos["x"] for pos in current_positions)
        max_x = max(pos["x"] for pos in current_positions)
        min_y = min(pos["y"] for pos in current_positions)
        max_y = max(pos["y"] for pos in current_positions)
        dx = max(-min_x, min(UI_KNOB_MAX_X - max_x, requested_dx))
        dy = max(UI_KNOB_MIN_Y - min_y, min(UI_KNOB_MAX_Y - max_y, requested_dy))
        if dx == 0 and dy == 0:
            return
        for item in self.panel_items.get(title, []):
            self.canvas.move(item, dx, dy)
        for control_id in control_ids:
            current = positions.get(control_id)
            if current is None:
                continue
            for item in self.canvas_items.get(control_id, []):
                self.canvas.move(item, dx, dy)
            self.owner.ui_layout[control_id] = {"x": current["x"] + dx, "y": current["y"] + dy}
        self.drag["x"] = int(event.x)
        self.drag["y"] = int(event.y)

    def _tidy_panel_from_event(self, _event) -> None:
        title = self._panel_title_from_event()
        if title:
            self.tidy_groups(title)

    def _end_drag(self, _event) -> None:
        if self.drag:
            self.drag = None
            self.owner._auto_save_project()
            self.owner._on_output_parameter_changed()

    def tidy_groups(self, only_group: str | None = None) -> None:
        changed = False
        positions = self._current_control_positions()
        for title, controls in self._controls_by_group().items():
            if only_group is not None and title != only_group:
                continue
            control_ids = [str(control["id"]) for control in controls]
            current_positions = [positions[control_id] for control_id in control_ids if control_id in positions]
            if not current_positions:
                continue
            start_x = min(pos["x"] for pos in current_positions)
            y = max(UI_KNOB_MIN_Y, min(UI_KNOB_MAX_Y, min(pos["y"] for pos in current_positions)))
            if len(control_ids) == 1:
                new_positions = [(start_x, y)]
            else:
                step = min(70, UI_KNOB_MAX_X // (len(control_ids) - 1))
                width = step * (len(control_ids) - 1)
                start_x = max(0, min(UI_KNOB_MAX_X - width, start_x))
                new_positions = [(start_x + index * step, y) for index in range(len(control_ids))]
            for control_id, (x, new_y) in zip(control_ids, new_positions):
                current = positions.get(control_id)
                if current is None or current == {"x": x, "y": new_y}:
                    continue
                self.owner.ui_layout[control_id] = {"x": x, "y": new_y}
                changed = True
        if changed:
            self.redraw()
            self.owner._auto_save_project()
            self.owner._on_output_parameter_changed()

    def reset_layout(self) -> None:
        self.owner.ui_layout = {}
        self.redraw()
        self.owner._auto_save_project()
        self.owner._on_output_parameter_changed()
