#!/usr/bin/env python3
"""Capture a repeatable SampleSmith-vs-DecentSampler UI comparison.

Run under Xvfb on headless machines, for example:

    xvfb-run -a --server-args='-screen 0 1280x1024x24' \
        python tools/capture_ui_comparison.py \
        --decent-sampler /path/to/DecentSampler

The script creates a tiny self-contained test instrument, captures SampleSmith's
812x375 preview, optionally loads the generated .dspreset in DecentSampler, and
writes PNG/JSON/HTML artifacts for measured visual comparison.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import shutil
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Iterable

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from samplesmith_app.app import SampleSmithApp  # noqa: E402
from samplesmith_app.models import SampleInfo  # noqa: E402

UI_WIDTH = 812
UI_HEIGHT = 375
SCREEN = "1280x1024x24"

OFF_EFFECTS = [
    "lowpass",
    "notch",
    "peak",
    "gain",
    "reverb",
    "delay",
    "chorus",
    "phaser",
    "convolution",
    "pitch_shift",
    "wave_folder",
    "wave_shaper",
    "stereo_simulator",
    "bit_crusher",
]
OFF_KNOBS = [
    "tone",
    "filter_resonance",
    "notch_frequency",
    "notch_q",
    "peak_frequency",
    "peak_q",
    "peak_gain",
    "gain_level",
    "reverb_wet",
    "reverb_room",
    "reverb_damping",
    "delay_wet",
    "delay_time",
    "delay_stereo_offset",
    "delay_feedback",
    "chorus_mix",
    "chorus_depth",
    "chorus_rate",
    "phaser_mix",
    "phaser_depth",
    "phaser_rate",
    "phaser_frequency",
    "phaser_feedback",
    "convolution_mix",
    "pitch_shift",
    "pitch_shift_mix",
    "wave_folder_drive",
    "wave_folder_threshold",
    "wave_shaper_drive",
    "wave_shaper_boost",
    "wave_shaper_output",
    "stereo_width",
    "bit_depth",
    "bit_crusher_rate",
    "bit_crusher_mix",
]
ON_EFFECTS = ["amp_env", "reverb", "delay", "chorus", "phaser"]
ON_KNOBS = [
    "amp_env",
    "reverb_wet",
    "reverb_room",
    "reverb_damping",
    "delay_wet",
    "delay_time",
    "delay_stereo_offset",
    "delay_feedback",
    "chorus_mix",
    "chorus_depth",
    "chorus_rate",
    "phaser_mix",
    "phaser_depth",
    "phaser_rate",
    "phaser_frequency",
    "phaser_feedback",
]


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, **kwargs)


def require_program(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Required program not found: {name}")


def make_tone_wav(path: Path, freq: float = 261.63, seconds: float = 0.35, sample_rate: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        for index in range(frames):
            fade = min(1.0, index / 400, (frames - index) / 400)
            value = int(11000 * fade * math.sin(2 * math.pi * freq * index / sample_rate))
            handle.writeframes(struct.pack("<h", value))


def set_booleans(app: SampleSmithApp, names: Iterable[str], suffix: str, value: bool) -> None:
    for name in names:
        getattr(app, f"{name}_{suffix}").set(value)


def select_tab_by_text(root, text: str) -> bool:
    stack = [root]
    while stack:
        widget = stack.pop()
        try:
            if widget.winfo_class() == "TNotebook":
                for tab_id in widget.tabs():
                    if widget.tab(tab_id, "text") == text:
                        widget.select(tab_id)
                        return True
        except Exception:
            pass
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass
    return False


def cancel_scheduled_output(app: SampleSmithApp) -> None:
    if app._output_update_after_id is not None:
        app.after_cancel(app._output_update_after_id)
        app._output_update_after_id = None


def capture_samplesmith(output_dir: Path, instrument_name: str) -> dict[str, object]:
    app = SampleSmithApp()
    app.geometry("1000x900+20+20")
    # Let the app finish its startup/default idle work first; otherwise it can
    # restore defaults over the measured test state.
    app.update_idletasks()
    cancel_scheduled_output(app)

    project_root = output_dir / instrument_name
    sample_path = project_root / "Samples" / "test_C4.wav"
    make_tone_wav(sample_path)

    app.name_var.set(instrument_name)
    app.output_var.set(str(output_dir))
    app.samples = [SampleInfo(path=sample_path, root_note=72, lo_note=72, hi_note=72, label="C4")]

    set_booleans(app, OFF_EFFECTS, "enabled_var", False)
    for name in OFF_KNOBS:
        getattr(app, f"ds_knob_{name}_var").set(False)
    for name in ON_EFFECTS:
        getattr(app, f"{name}_enabled_var").set(True)
    for name in ON_KNOBS:
        getattr(app, f"ds_knob_{name}_var").set(True)

    cancel_scheduled_output(app)
    preset = app._write_preset()
    app.ui_preview.redraw()
    select_tab_by_text(app, "DecentSampler")
    select_tab_by_text(app, "UI Preview")
    app.geometry("1000x900+20+20")
    cancel_scheduled_output(app)
    app.update()

    canvas = app.ui_preview.canvas
    coords = {
        "x": canvas.winfo_rootx(),
        "y": canvas.winfo_rooty(),
        "width": canvas.winfo_width(),
        "height": canvas.winfo_height(),
        "preset": str(preset),
    }
    (output_dir / "samplesmith_canvas_coords.json").write_text(json.dumps(coords, indent=2))
    window_png = output_dir / "samplesmith_window.png"
    preview_png = output_dir / "samplesmith_preview_812x375.png"
    run(["import", "-window", "root", str(window_png)])
    crop_x = int(coords["x"]) + (1 if int(coords["width"]) >= UI_WIDTH + 2 else 0)
    crop_y = int(coords["y"]) + (1 if int(coords["height"]) >= UI_HEIGHT + 2 else 0)
    run(["convert", str(window_png), "-crop", f"{UI_WIDTH}x{UI_HEIGHT}+{crop_x}+{crop_y}", str(preview_png)])
    app.destroy()
    return coords


def capture_decent_sampler(output_dir: Path, decent_sampler: Path, preset: Path) -> bool:
    try:
        import pyautogui
    except Exception as exc:  # pragma: no cover - optional local automation dependency
        print(f"Skipping DecentSampler capture; pyautogui is unavailable: {exc}")
        return False

    log = (output_dir / "decent_sampler_capture.log").open("wb")
    process = subprocess.Popen([str(decent_sampler)], stdout=log, stderr=subprocess.STDOUT)
    try:
        time.sleep(6)
        # Coordinates are for the 1280x1024 Xvfb screen used in this tool.
        pyautogui.click(1000, 366)  # FILE...
        time.sleep(0.25)
        pyautogui.click(995, 405)  # Load...
        time.sleep(1.5)
        pyautogui.click(650, 713)  # JUCE file field
        pyautogui.hotkey("ctrl", "a")
        pyautogui.write(str(preset), interval=0)
        pyautogui.press("tab")
        pyautogui.press("enter")
        time.sleep(4)
        window_png = output_dir / "decent_sampler_window.png"
        actual_png = output_dir / "decent_sampler_actual_812x375.png"
        run(["import", "-window", "root", str(window_png)])
        # Measured DecentSampler surface in this Xvfb geometry.
        run(["convert", str(window_png), "-crop", f"{UI_WIDTH}x{UI_HEIGHT}+237+342", str(actual_png)])
        return True
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


def compare_images(output_dir: Path) -> dict[str, object]:
    preview = output_dir / "samplesmith_preview_812x375.png"
    actual = output_dir / "decent_sampler_actual_812x375.png"
    diff = output_dir / "preview_vs_decent_sampler_diff.png"
    contact = output_dir / "comparison_contact_sheet.png"
    metric = subprocess.run(
        ["compare", "-metric", "RMSE", str(preview), str(actual), str(diff)],
        check=False,
        stderr=subprocess.PIPE,
        text=True,
    ).stderr.strip()
    run(["convert", str(preview), str(actual), str(diff), "+append", str(contact)])
    return {"rmse": metric, "diff": str(diff), "contact_sheet": str(contact)}


def write_report(output_dir: Path, data: dict[str, object]) -> None:
    report = output_dir / "comparison_report.html"
    images = [
        "samplesmith_preview_812x375.png",
        "decent_sampler_actual_812x375.png",
        "preview_vs_decent_sampler_diff.png",
        "comparison_contact_sheet.png",
    ]
    body = ["<h1>SampleSmith vs DecentSampler UI comparison</h1>"]
    body.append(f"<pre>{html.escape(json.dumps(data, indent=2))}</pre>")
    for image in images:
        if (output_dir / image).exists():
            body.append(f"<h2>{html.escape(image)}</h2><img src='{html.escape(image)}' style='max-width:100%; image-rendering:auto'>")
    report.write_text("<!doctype html><meta charset='utf-8'>" + "\n".join(body))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO / "ui-comparison-output")
    parser.add_argument("--instrument-name", default="TitleBandTest")
    parser.add_argument("--decent-sampler", type=Path, help="Path to DecentSampler standalone binary")
    parser.add_argument("--skip-decent-sampler", action="store_true", help="Only capture SampleSmith preview and generated preset")
    args = parser.parse_args()

    require_program("import")
    require_program("convert")
    require_program("compare")
    args.output.mkdir(parents=True, exist_ok=True)

    coords = capture_samplesmith(args.output, args.instrument_name)
    data: dict[str, object] = {"output": str(args.output), "samplesmith_canvas": coords}

    if not args.skip_decent_sampler and args.decent_sampler:
        preset = Path(str(coords["preset"]))
        data["decent_sampler_capture"] = capture_decent_sampler(args.output, args.decent_sampler, preset)
        if data["decent_sampler_capture"]:
            data["comparison"] = compare_images(args.output)
    else:
        data["decent_sampler_capture"] = False

    (args.output / "comparison_summary.json").write_text(json.dumps(data, indent=2))
    write_report(args.output, data)
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
