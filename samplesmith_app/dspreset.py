"""Decent Sampler .dspreset generation for SampleSmith."""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

from .models import SampleInfo, clamp_float, clamp_midi_note, slugify, valid_loop_points

def generate_dspreset(
    instrument_name: str,
    output_dir: Path,
    samples: list[SampleInfo],
    loop_enabled: bool = False,
    loop_start: int | None = None,
    loop_end: int | None = None,
    loop_crossfade: float = 0.0,
    loop_crossfade_mode: str = "equal_power",
    amp_env_enabled: bool = False,
    amp_attack: float = 0.01,
    amp_decay: float = 0.0,
    amp_sustain: float = 1.0,
    amp_release: float = 0.8,
    ds_knob_amp_env: bool = True,
    root_note_offset: int = 0,
    delay_enabled: bool = False,
    delay_time: float = 0.7,
    delay_stereo_offset: float = 0.0,
    delay_feedback: float = 0.2,
    delay_wet_level: float = 0.5,
    lowpass_enabled: bool = False,
    filter_type: str = "lowpass_4pl",
    lowpass_frequency: float = 22000.0,
    filter_resonance: float = 0.7,
    notch_enabled: bool = False,
    notch_frequency: float = 10000.0,
    notch_q: float = 0.7,
    peak_enabled: bool = False,
    peak_frequency: float = 10000.0,
    peak_q: float = 0.7,
    peak_gain: float = 1.0,
    gain_enabled: bool = False,
    gain_level: float = 0.0,
    reverb_enabled: bool = False,
    reverb_room_size: float = 0.7,
    reverb_damping: float = 0.3,
    reverb_wet_level: float = 0.5,
    chorus_enabled: bool = False,
    chorus_mix: float = 0.5,
    chorus_mod_depth: float = 0.2,
    chorus_mod_rate: float = 0.2,
    phaser_enabled: bool = False,
    phaser_mix: float = 0.5,
    phaser_mod_depth: float = 0.2,
    phaser_mod_rate: float = 0.2,
    phaser_center_frequency: float = 400.0,
    phaser_feedback: float = 0.7,
    convolution_enabled: bool = False,
    reverb_ir_file: str = "",
    reverb_mix: float = 0.0,
    pitch_shift_enabled: bool = False,
    pitch_shift: float = 0.0,
    pitch_shift_mix: float = 0.5,
    wave_folder_enabled: bool = False,
    wave_folder_drive: float = 1.0,
    wave_folder_threshold: float = 0.25,
    wave_shaper_enabled: bool = False,
    wave_shaper_drive: float = 1.0,
    wave_shaper_drive_boost: float = 1.0,
    wave_shaper_output_level: float = 0.1,
    stereo_simulator_enabled: bool = False,
    stereo_simulator_algorithm: str = "adt",
    stereo_simulator_width: float = 0.5,
    stereo_simulator_delay_time: float = 0.005,
    stereo_simulator_mod_rate: float = 0.5,
    stereo_simulator_mod_depth: float = 0.3,
    bit_crusher_enabled: bool = False,
    bit_crusher_bit_depth: int = 24,
    bit_crusher_sample_rate_reduction: int = 1,
    bit_crusher_mix: float = 1.0,
    ds_knob_tone: bool = True,
    ds_knob_filter_resonance: bool = False,
    ds_knob_notch_frequency: bool = False,
    ds_knob_notch_q: bool = False,
    ds_knob_peak_frequency: bool = False,
    ds_knob_peak_q: bool = False,
    ds_knob_peak_gain: bool = False,
    ds_knob_gain_level: bool = False,
    ds_knob_reverb_wet: bool = True,
    ds_knob_reverb_room: bool = False,
    ds_knob_reverb_damping: bool = False,
    ds_knob_delay_wet: bool = True,
    ds_knob_delay_time: bool = False,
    ds_knob_delay_stereo_offset: bool = False,
    ds_knob_delay_feedback: bool = False,
    ds_knob_chorus_mix: bool = True,
    ds_knob_chorus_depth: bool = False,
    ds_knob_chorus_rate: bool = False,
    ds_knob_phaser_mix: bool = False,
    ds_knob_phaser_depth: bool = False,
    ds_knob_phaser_rate: bool = False,
    ds_knob_phaser_frequency: bool = False,
    ds_knob_phaser_feedback: bool = False,
    ds_knob_convolution_mix: bool = False,
    ds_knob_pitch_shift: bool = False,
    ds_knob_pitch_shift_mix: bool = False,
    ds_knob_wave_folder_drive: bool = False,
    ds_knob_wave_folder_threshold: bool = False,
    ds_knob_wave_shaper_drive: bool = False,
    ds_knob_wave_shaper_boost: bool = False,
    ds_knob_wave_shaper_output: bool = False,
    ds_knob_stereo_width: bool = False,
    ds_knob_bit_depth: bool = False,
    ds_knob_bit_crusher_mix: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
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
        attrs = {"frequency": f"{lowpass_frequency:.1f}"}
        if filter_type != "lowpass_1pl":
            attrs["resonance"] = f"{filter_resonance:.3f}"
        effects_to_write.append((filter_type, attrs))
    if notch_enabled:
        effects_to_write.append(("notch", {"frequency": f"{notch_frequency:.1f}", "q": f"{notch_q:.3f}"}))
    if peak_enabled:
        effects_to_write.append(("peak", {"frequency": f"{peak_frequency:.1f}", "q": f"{peak_q:.3f}", "gain": f"{peak_gain:.3f}"}))
    if gain_enabled:
        effects_to_write.append(("gain", {"level": f"{gain_level:.1f}"}))
    if reverb_enabled:
        effects_to_write.append(("reverb", {"roomSize": f"{reverb_room_size:.3f}", "damping": f"{reverb_damping:.3f}", "wetLevel": f"{reverb_wet_level:.3f}"}))
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
    if phaser_enabled:
        effects_to_write.append(("phaser", {"mix": f"{phaser_mix:.3f}", "modDepth": f"{phaser_mod_depth:.3f}", "modRate": f"{phaser_mod_rate:.3f}", "centerFrequency": f"{phaser_center_frequency:.1f}", "feedback": f"{phaser_feedback:.3f}"}))
    if convolution_enabled and reverb_ir_file.strip() and reverb_mix > 0:
        effects_to_write.append(("convolution", {"mix": f"{max(0.0, min(1.0, reverb_mix)):.3f}", "irFile": reverb_ir_file.strip()}))
    if pitch_shift_enabled:
        effects_to_write.append(("pitch_shift", {"pitchShift": f"{pitch_shift:.3f}", "mix": f"{pitch_shift_mix:.3f}"}))
    if wave_folder_enabled:
        effects_to_write.append(("wave_folder", {"drive": f"{wave_folder_drive:.3f}", "threshold": f"{wave_folder_threshold:.3f}"}))
    if wave_shaper_enabled:
        effects_to_write.append(("wave_shaper", {"drive": f"{wave_shaper_drive:.3f}", "driveBoost": f"{wave_shaper_drive_boost:.3f}", "outputLevel": f"{wave_shaper_output_level:.3f}"}))
    if stereo_simulator_enabled:
        effects_to_write.append(("stereo_simulator", {"algorithm": stereo_simulator_algorithm, "width": f"{stereo_simulator_width:.3f}", "delayTime": f"{stereo_simulator_delay_time:.3f}", "modRate": f"{stereo_simulator_mod_rate:.3f}", "modDepth": f"{stereo_simulator_mod_depth:.3f}"}))
    if bit_crusher_enabled:
        effects_to_write.append(("bit_crusher", {"bitDepth": str(bit_crusher_bit_depth), "sampleRateReduction": str(bit_crusher_sample_rate_reduction), "mix": f"{bit_crusher_mix:.3f}"}))

    loop_start, loop_end = valid_loop_points(loop_start, loop_end)
    loop_crossfade = clamp_float(loop_crossfade, 0.0, 60000.0)
    if loop_crossfade_mode not in {"linear", "equal_power"}:
        loop_crossfade_mode = "equal_power"
    amp_attack = clamp_float(amp_attack, 0.0, 10.0)
    amp_decay = clamp_float(amp_decay, 0.0, 25.0)
    amp_sustain = clamp_float(amp_sustain, 0.0, 1.0)
    amp_release = clamp_float(amp_release, 0.0, 25.0)

    root = ET.Element("DecentSampler", {"pluginVersion": "1"})
    has_amp_env_knobs = amp_env_enabled and ds_knob_amp_env
    if effects_to_write or has_amp_env_knobs:
        ui = ET.SubElement(root, "ui", {"width": "812", "height": "475"})
        tab = ET.SubElement(ui, "tab", {"name": "main"})
        ET.SubElement(
            tab,
            "label",
            {
                "x": "30",
                "y": "12",
                "width": "752",
                "height": "28",
                "text": instrument_name,
                "textColor": "DD330033",
                "textSize": "22",
                "hAlign": "center",
            },
        )
        effect_positions = {effect_type: position for position, (effect_type, _attrs) in enumerate(effects_to_write)}
        filter_effect_types = {"lowpass", "lowpass_1pl", "lowpass_4pl", "bandpass", "highpass"}
        filter_effect_type = next((effect_type for effect_type in effect_positions if effect_type in filter_effect_types), "lowpass")
        knob_groups = [
            (
                "Tone",
                [
                    (ds_knob_tone and filter_effect_type in effect_positions, filter_effect_type, "Frequency", "FX_FILTER_FREQUENCY", "60", "22000", f"{lowpass_frequency:.1f}", "22000.0"),
                    (ds_knob_filter_resonance and filter_effect_type in effect_positions and filter_effect_type != "lowpass_1pl", filter_effect_type, "Res", "FX_FILTER_RESONANCE", "0", "5", f"{filter_resonance:.3f}", "0.700"),
                ],
            ),
            (
                "Notch",
                [
                    (ds_knob_notch_frequency and "notch" in effect_positions, "notch", "Frequency", "FX_FILTER_FREQUENCY", "60", "22000", f"{notch_frequency:.1f}", "10000.0"),
                    (ds_knob_notch_q and "notch" in effect_positions, "notch", "Q", "FX_FILTER_Q", "0.01", "18", f"{notch_q:.3f}", "0.700"),
                ],
            ),
            (
                "Peak",
                [
                    (ds_knob_peak_frequency and "peak" in effect_positions, "peak", "Frequency", "FX_FILTER_FREQUENCY", "60", "22000", f"{peak_frequency:.1f}", "10000.0"),
                    (ds_knob_peak_q and "peak" in effect_positions, "peak", "Q", "FX_FILTER_Q", "0.01", "18", f"{peak_q:.3f}", "0.700"),
                    (ds_knob_peak_gain and "peak" in effect_positions, "peak", "Gain", "FX_FILTER_GAIN", "0", "10", f"{peak_gain:.3f}", "1.000"),
                ],
            ),
            ("Gain", [(ds_knob_gain_level and "gain" in effect_positions, "gain", "Level", "LEVEL", "-99", "24", f"{gain_level:.1f}", "0.0")]),
            (
                "Reverb",
                [
                    (ds_knob_reverb_wet and "reverb" in effect_positions, "reverb", "Amount", "FX_REVERB_WET_LEVEL", "0", "1", f"{reverb_wet_level:.3f}", "0.500"),
                    (ds_knob_reverb_room and "reverb" in effect_positions, "reverb", "Room", "FX_REVERB_ROOM_SIZE", "0", "1", f"{reverb_room_size:.3f}", "0.700"),
                    (ds_knob_reverb_damping and "reverb" in effect_positions, "reverb", "Damp", "FX_REVERB_DAMPING", "0", "1", f"{reverb_damping:.3f}", "0.300"),
                ],
            ),
            (
                "Delay",
                [
                    (ds_knob_delay_wet and "delay" in effect_positions, "delay", "Amount", "FX_WET_LEVEL", "0", "1", f"{delay_wet_level:.3f}", "0.500"),
                    (ds_knob_delay_time and "delay" in effect_positions, "delay", "Time", "FX_DELAY_TIME", "0", "20", f"{delay_time:.3f}", "0.700"),
                    (ds_knob_delay_stereo_offset and "delay" in effect_positions, "delay", "Offset", "FX_STEREO_OFFSET", "0", "1", f"{delay_stereo_offset:.3f}", "0.000"),
                    (ds_knob_delay_feedback and "delay" in effect_positions, "delay", "Feedback", "FX_FEEDBACK", "0", "1", f"{delay_feedback:.3f}", "0.200"),
                ],
            ),
            (
                "Chorus",
                [
                    (ds_knob_chorus_mix and "chorus" in effect_positions, "chorus", "Amount", "FX_MIX", "0", "1", f"{chorus_mix:.3f}", "0.500"),
                    (ds_knob_chorus_depth and "chorus" in effect_positions, "chorus", "Depth", "FX_MOD_DEPTH", "0", "1", f"{chorus_mod_depth:.3f}", "0.200"),
                    (ds_knob_chorus_rate and "chorus" in effect_positions, "chorus", "Rate", "FX_MOD_RATE", "0", "10", f"{chorus_mod_rate:.3f}", "0.200"),
                ],
            ),
            (
                "Phaser",
                [
                    (ds_knob_phaser_mix and "phaser" in effect_positions, "phaser", "Amount", "FX_MIX", "0", "1", f"{phaser_mix:.3f}", "0.500"),
                    (ds_knob_phaser_depth and "phaser" in effect_positions, "phaser", "Depth", "FX_MOD_DEPTH", "0", "1", f"{phaser_mod_depth:.3f}", "0.200"),
                    (ds_knob_phaser_rate and "phaser" in effect_positions, "phaser", "Rate", "FX_MOD_RATE", "0", "10", f"{phaser_mod_rate:.3f}", "0.200"),
                    (ds_knob_phaser_frequency and "phaser" in effect_positions, "phaser", "Freq", "FX_CENTER_FREQUENCY", "0", "22000", f"{phaser_center_frequency:.1f}", "400.0"),
                    (ds_knob_phaser_feedback and "phaser" in effect_positions, "phaser", "Feedback", "FX_FEEDBACK", "0", "1", f"{phaser_feedback:.3f}", "0.700"),
                ],
            ),
            ("IR Verb", [(ds_knob_convolution_mix and "convolution" in effect_positions, "convolution", "Amount", "FX_MIX", "0", "1", f"{reverb_mix:.3f}", "0.500")]),
            (
                "Pitch",
                [
                    (ds_knob_pitch_shift and "pitch_shift" in effect_positions, "pitch_shift", "Semitones", "FX_PITCH_SHIFT", "-24", "24", f"{pitch_shift:.3f}", "0.000"),
                    (ds_knob_pitch_shift_mix and "pitch_shift" in effect_positions, "pitch_shift", "Mix", "FX_MIX", "0", "1", f"{pitch_shift_mix:.3f}", "0.500"),
                ],
            ),
            (
                "Folder",
                [
                    (ds_knob_wave_folder_drive and "wave_folder" in effect_positions, "wave_folder", "Drive", "FX_DRIVE", "1", "100", f"{wave_folder_drive:.3f}", "1.000"),
                    (ds_knob_wave_folder_threshold and "wave_folder" in effect_positions, "wave_folder", "Threshold", "FX_THRESHOLD", "0", "10", f"{wave_folder_threshold:.3f}", "0.250"),
                ],
            ),
            (
                "Shaper",
                [
                    (ds_knob_wave_shaper_drive and "wave_shaper" in effect_positions, "wave_shaper", "Drive", "FX_DRIVE", "1", "1000", f"{wave_shaper_drive:.3f}", "1.000"),
                    (ds_knob_wave_shaper_boost and "wave_shaper" in effect_positions, "wave_shaper", "Boost", "FX_DRIVE_BOOST", "0", "1", f"{wave_shaper_drive_boost:.3f}", "1.000"),
                    (ds_knob_wave_shaper_output and "wave_shaper" in effect_positions, "wave_shaper", "Out", "FX_OUTPUT_LEVEL", "0", "8", f"{wave_shaper_output_level:.3f}", "0.100"),
                ],
            ),
            ("Stereo", [(ds_knob_stereo_width and "stereo_simulator" in effect_positions, "stereo_simulator", "Width", "FX_WIDTH", "0", "1", f"{stereo_simulator_width:.3f}", "0.500")]),
            (
                "Bits",
                [
                    (ds_knob_bit_depth and "bit_crusher" in effect_positions, "bit_crusher", "Depth", "FX_BIT_DEPTH", "1", "24", str(bit_crusher_bit_depth), "24"),
                    (ds_knob_bit_crusher_mix and "bit_crusher" in effect_positions, "bit_crusher", "Mix", "FX_MIX", "0", "1", f"{bit_crusher_mix:.3f}", "1.000"),
                ],
            ),
        ]
        visible_control_index = 0
        knob_columns = 8
        knob_step_x = 94
        knob_step_y = 98
        knob_width = 76
        knob_start_x = 34
        knob_start_y = 78
        group_title_height = 20

        def knob_position(index: int) -> tuple[int, int]:
            return knob_start_x + (index % knob_columns) * knob_step_x, knob_start_y + (index // knob_columns) * knob_step_y

        def add_effect_knob(effect_type: str, label: str, parameter: str, min_value: str, max_value: str, value: str, default_value: str) -> None:
            nonlocal visible_control_index
            position = effect_positions[effect_type]
            x_pos, y_pos = knob_position(visible_control_index)
            visible_control_index += 1
            knob = ET.SubElement(
                tab,
                "labeled-knob",
                {
                    "x": str(x_pos),
                    "y": str(y_pos),
                    "width": str(knob_width),
                    "label": label,
                    "parameterName": label,
                    "type": "float",
                    "minValue": min_value,
                    "maxValue": max_value,
                    "value": value,
                    "defaultValue": default_value,
                    "textColor": "DD330033",
                    "textSize": "14",
                    "style": "rotary",
                    "trackForegroundColor": "EEFFFFFF",
                    "trackBackgroundColor": "77330033",
                },
            )
            ET.SubElement(
                knob,
                "binding",
                {
                    "type": "effect",
                    "level": "instrument",
                    "position": str(position),
                    "parameter": parameter,
                },
            )

        def add_amp_knob(label: str, parameter: str, min_value: str, max_value: str, value: str, default_value: str) -> None:
            nonlocal visible_control_index
            x_pos, y_pos = knob_position(visible_control_index)
            visible_control_index += 1
            knob = ET.SubElement(
                tab,
                "labeled-knob",
                {
                    "x": str(x_pos),
                    "y": str(y_pos),
                    "width": str(knob_width),
                    "label": label,
                    "parameterName": label,
                    "type": "float",
                    "minValue": min_value,
                    "maxValue": max_value,
                    "value": value,
                    "defaultValue": default_value,
                    "textColor": "DD330033",
                    "textSize": "14",
                    "style": "rotary",
                    "trackForegroundColor": "EEFFFFFF",
                    "trackBackgroundColor": "77330033",
                },
            )
            ET.SubElement(
                knob,
                "binding",
                {
                    "type": "amp",
                    "level": "group",
                    "position": "0",
                    "parameter": parameter,
                },
            )

        def add_amp_env_knobs() -> None:
            if not has_amp_env_knobs:
                return
            for label, parameter, min_value, max_value, value, default_value in [
                ("Attack", "ENV_ATTACK", "0", "10", f"{amp_attack:.3f}", "0.010"),
                ("Decay", "ENV_DECAY", "0", "25", f"{amp_decay:.3f}", "0.000"),
                ("Sustain", "ENV_SUSTAIN", "0", "1", f"{amp_sustain:.3f}", "1.000"),
                ("Release", "ENV_RELEASE", "0", "25", f"{amp_release:.3f}", "0.800"),
            ]:
                add_amp_knob(label, parameter, min_value, max_value, value, default_value)

        def add_knob_group(title: str, specs: list[tuple[bool, str, str, str, str, str, str, str]]) -> None:
            nonlocal visible_control_index
            included_specs = [spec for spec in specs if spec[0]]
            if not included_specs:
                return
            if len(included_specs) == 1:
                _include, effect_type, _label, parameter, min_value, max_value, value, default_value = included_specs[0]
                add_effect_knob(effect_type, title, parameter, min_value, max_value, value, default_value)
                return
            if (visible_control_index % knob_columns) + len(included_specs) > knob_columns:
                visible_control_index += knob_columns - (visible_control_index % knob_columns)
            first_x, first_y = knob_position(visible_control_index)
            group_x = first_x - 10
            group_y = first_y - group_title_height - 8
            group_width = knob_step_x * len(included_specs) - 8
            ET.SubElement(
                tab,
                "rectangle",
                {
                    "x": str(group_x),
                    "y": str(group_y),
                    "width": str(group_width),
                    "height": "104",
                    "fillColor": "#0D330033",
                    "borderColor": "#55330033",
                    "borderThickness": "1",
                },
            )
            ET.SubElement(
                tab,
                "label",
                {
                    "x": str(group_x + 10),
                    "y": str(group_y + 4),
                    "width": str(group_width - 20),
                    "height": "18",
                    "text": title,
                    "textColor": "DD330033",
                    "textSize": "14",
                    "hAlign": "center",
                },
            )
            for _include, effect_type, label, parameter, min_value, max_value, value, default_value in included_specs:
                add_effect_knob(effect_type, label, parameter, min_value, max_value, value, default_value)

        add_amp_env_knobs()
        for title, specs in knob_groups:
            add_knob_group(title, specs)

    groups = ET.SubElement(root, "groups")
    group_attrs = {"attack": f"{amp_attack:.3f}", "release": f"{amp_release:.3f}"}
    if amp_env_enabled:
        group_attrs.update(
            {
                "ampEnvEnabled": "true",
                "decay": f"{amp_decay:.3f}",
                "sustain": f"{amp_sustain:.3f}",
            }
        )
    group = ET.SubElement(groups, "group", group_attrs)
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
            if loop_start is not None and loop_end is not None:
                attrs["loopStart"] = str(loop_start)
                attrs["loopEnd"] = str(loop_end)
                if loop_crossfade > 0:
                    attrs["loopCrossfade"] = f"{loop_crossfade:.1f}"
                    attrs["loopCrossfadeMode"] = loop_crossfade_mode
        ET.SubElement(group, "sample", attrs)
    if effects_to_write:
        effects = ET.SubElement(root, "effects")
        for effect_type, attrs in effects_to_write:
            ET.SubElement(effects, "effect", {"type": effect_type, **attrs})
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    preset_path = output_dir / f"{slugify(instrument_name)}.dspreset"
    tree.write(preset_path, encoding="utf-8", xml_declaration=True)
    return preset_path
