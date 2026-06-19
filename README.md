# SampleSmith

SampleSmith is a GUI tool for turning recorded sounds into playable DecentSampler instruments.

It is built for the practical Reaper / DecentSampler / Audacity sort of workflow: make a sound, record it, map it sensibly, and get a `.dspreset` plus audio samples that can be opened in DecentSampler.

The aim is practical playable-instrument usefulness rather than laboratory purity. If you only record one pitched sample, SampleSmith spreads it across the keyboard. If you record several, it maps them into overlapping ranges so each sample keeps its home note while still giving you transformed low/high sounds that can be musically useful.

## What it does

SampleSmith's main workflow is **Notes**: build a keyboard note list, record or import sounds onto those notes, trim/normalise the audio, bridge gaps with generated samples when useful, edit mapping/loops, and generate a DecentSampler `.dspreset`. Pitched notes, drones, growls, one-shots, hits, breaths, scrapes, and odd noises all belong in the same note-based workflow.

SampleSmith also saves a `.samplesmith.json` project file so an instrument can be reopened and extended later.

## Windows app download

For a friend who does not know Python, use the GitHub Actions build artifact:

1. Open the repository's **Actions** tab.
2. Choose **Build Windows app**.
3. Open the latest successful run.
4. Download **SampleSmith-Windows**.
5. Unzip it and run `SampleSmith.exe` inside the `SampleSmith` folder.

Windows may warn that the app is from an unknown publisher because it is not code-signed yet.

## Install dependencies

SampleSmith uses Tkinter for the GUI. Python often includes it, but if not:

```bash
sudo apt install python3-tk
```

On the machine doing the recording:

```bash
python -m pip install -r requirements.txt
```

That installs `sounddevice`, `soundfile`, `numpy`, and `librosa`. Bridge generation uses `librosa` when available for duration-preserving pitch shifts, so high generated notes do not become artificially short and expose loop ghosts. Pitch detection also uses `librosa` when available, with a simpler built-in fallback for constrained machines.

## Run SampleSmith

From this folder:

```bash
python samplesmith.py
```

Set the instrument name and output folder, then work in **Notes**. By default, single recordings start immediately; enable **Confirm before recording** if you want a ready-check prompt. Recordings can also play a reference tone first, controlled by **Play reference before pitched recording**. The right-hand **Selected sample** panel is the working area for the selected note: play the reference tone, record the selected sample, see the waveform, choose sample start/end, play the full take or selected region, keep the selection, record another take, or reset edited audio from its original backup. Click an existing note row to load its audio into the same panel for playback, waveform trimming, re-recording, or reset. Before SampleSmith overwrites an existing audio file from this panel, it keeps the original under `.samplesmith-backups/`. Starting another recording silently replaces the pending take; backup/reset covers existing audio-file mistakes. Each kept recording writes/updates both the `.dspreset` and the `.samplesmith.json` project file automatically; the generate/save buttons are there for manual regeneration.

Use **New project** to clear the current app state and start a blank unsaved project; it does not delete saved projects or audio files. If the current project has unsaved changes, SampleSmith asks whether to save, discard, or cancel first. New projects also avoid reusing an existing default project folder blindly. Use **Open project** to return to an existing SampleSmith project; it has the same save/discard/cancel guard.

Use **Import audio…** to bring selected WAV/FLAC files into the current instrument, or **Import folder…** to import the WAV/FLAC files directly inside a folder. SampleSmith copies imported files into the instrument's `Samples/` folder, guesses root notes from filenames where it can (`Piano_C4.wav`, `note72.flac`, etc.), asks for the root note for each file, then updates the Notes table, project file, and `.dspreset`.

Use **Review stray audio** if you have already copied or recorded audio files into the current instrument/project folders outside SampleSmith. SampleSmith checks only the current instrument folder, its `Samples/` folder, and the project file's own folder one level deep; it does not recurse into neighbouring project folders, guesses root notes from filenames where it can, and asks before importing anything into the mapping.

Output defaults to:

```text
samplesmith-projects/<InstrumentName>/
  <InstrumentName>.dspreset
  <InstrumentName>.samplesmith.json
  Samples/
    <InstrumentName>_C3.wav
    ...
```

Use **Export .dsbundle** to create a portable DecentSampler bundle beside the project folder:

```text
samplesmith-projects/<InstrumentName>.dsbundle/
  <InstrumentName>.dspreset
  Samples/
    <InstrumentName>_C3.wav
    ...
```

The `.dsbundle` export copies the mapped audio into its own `Samples/` folder and writes relative sample paths, so the bundle can be moved as one folder. Open the `.dspreset` or `.dsbundle` in DecentSampler, including from Reaper.

## Compare the SampleSmith UI preview with DecentSampler

For visual/layout polishing, SampleSmith includes a repeatable capture harness that generates a tiny test instrument, captures SampleSmith's 812×375 DecentSampler preview, optionally loads the generated `.dspreset` in DecentSampler, and writes a PNG/HTML comparison report.

In the UI preview tab, drag the instrument title, knobs, or group boxes to reposition them. Use **Title −/+** to change title text size and **Title W−/W+** to change its title box width. The layout is saved with the project and exported into the `.dspreset`.

On a headless Linux machine with Xvfb, ImageMagick, DecentSampler, and the optional dev dependencies installed:

```bash
python -m pip install -r requirements-dev.txt
xvfb-run -a --server-args='-screen 0 1280x1024x24' \
  python tools/capture_ui_comparison.py \
  --decent-sampler /path/to/DecentSampler
```

By default the output goes to `ui-comparison-output/`, which is ignored by Git.

## Build a DecentSampler effects test pack

To audibly check DecentSampler effect support on a local machine with audio, generate the listening pack:

```bash
python tools/make_effects_test_pack.py
```

This recreates `effects-test-pack/` with one shared `Samples/` folder, a dry control preset, one exaggerated `.dspreset` per supported effect/filter, and `LISTENING_CHECKLIST.md`. Open the checklist, then open each preset in DecentSampler and play around the on-screen C4 key. The generated pack is ignored by Git.

To confirm DecentSampler standalone's octave/key numbering, generate the octave diagnostic pack:

```bash
python tools/make_octave_diagnostic_pack.py
```

This recreates `octave-diagnostic-pack/` with one generated middle-C/C4 tone sample plus two presets: one rooted at key 60 and one rooted at key 72. In DecentSampler standalone, the C4 screen key should play the key-72 preset unshifted. The generated pack is ignored by Git.

## Notes mapping behaviour

Default pitched behaviour is classic sample spreading: SampleSmith generates a playable instrument from whatever samples have actually been recorded, even one sample.

- One recorded pitched sample maps across the whole keyboard.
- Multiple pitched samples map from the previous recorded root note to the next recorded root note.
- Neighbouring samples overlap between their home notes.
- Use **Bridge gap** in the Notes tab note list to explicitly write generated bridge files under `Samples/generated/`. A single missing note can be bridged, or a whole visible gap/range can be bridged at once. When there are recorded samples on both sides, SampleSmith blends retuned versions of both neighbours; when there is only one usable neighbour, it creates a retuned generated copy from the nearest source recording. SampleSmith does not generate these files as a hidden export side effect. Existing generated bridge files are included in the visible/exported mapping and deliberately marked `[GENERATED]` so they are easy to replace later with proper recorded samples.

For example, recorded C3/C4 maps C3 from DS keys `0–72` and C4 from DS keys `60–127`, giving an overlap/blend zone between them. This can make strange-but-useful transformed sounds, such as very low growls.

Possible later range modes:

- full keyboard — current/default
- captured range only
- custom low/high playable range

## DecentSampler settings

DecentSampler export settings live on their own **DecentSampler** tab so tone, reverb, playback, and generated UI controls can keep growing without cluttering the recording workflow. That tab now has nested sub-tabs for **Basics / Export**, **Tone**, **Space**, **Shape**, and **UI Preview** rather than one long wall of controls. Sample mapping lives directly in the **Notes** tab.

Current DecentSampler output parameters:

- **Loop samples** — writes `loopEnabled="true"` on generated sample entries. The visible controls are fallback/default loop settings for the whole project: manual `loopStart` / `loopEnd` sample positions plus `loopCrossfade` and `loopCrossfadeMode` (`equal_power` or `linear`). The **Notes** table shows per-audio-file loop status; double-click the **Loop** column to open the graphical loop editor with a full waveform display, shaded loop region, visible crossfade-in/crossfade-out zones, adjustable-zoom signed-waveform panes where a click sets the loop start/end and the mouse wheel changes close-up zoom, draggable rough loop-start/end handles, numeric fields, crossfade settings, raw and crossfade loop audition/stop controls that restart automatically after loop/crossfade edits while audition is active, and an individual **Import WAV marker** action. Per-sample loop fields (`loop_enabled`, `loop_start`, `loop_end`, `loop_crossfade`, `loop_crossfade_mode`) are saved in the project and take priority during export. If loop is enabled but no valid manual start/end is entered, SampleSmith leaves the explicit points out so DecentSampler can still use embedded WAV loop markers when present. The DecentSampler tab also has a first-pass “Use first WAV marker” helper for importing the first `smpl` loop marker it finds in the recorded samples.
- **Amp ADSR envelope** — optional DecentSampler amp envelope export using documented `<groups>` attributes: `ampEnvEnabled`, `attack`, `decay`, `sustain`, and `release`. When enabled, SampleSmith can also write visible DecentSampler vertical bar controls bound to the official-template-style instrument amp parameters `ENV_ATTACK`, `ENV_DECAY`, `ENV_SUSTAIN`, and `ENV_RELEASE`.
- **DecentSampler note convention** — SampleSmith follows DecentSampler's screen-key numbering because it exists to make `.dspreset` patches. In this convention C4 is key/root number 72, while the generated/reference tone for C4 is still actual middle C (~261.63 Hz).
- **DecentSampler effects** — SampleSmith includes all effect types documented in the current DecentSampler effects guide: filters (`lowpass`, `lowpass_1pl`, legacy `lowpass_4pl`, `bandpass`, `highpass`), `notch`, `peak`, `gain`, `reverb`, `delay`, `chorus`, `phaser`, `convolution`, `pitch_shift`, `wave_folder`, `wave_shaper`, `stereo_simulator`, and `bit_crusher`. Wave shaper now exposes its documented `highQuality` flag, stereo simulator exposes its documented algorithm/width/delay/modulation export settings, and bit crusher defaults to audible example-style settings (`bitDepth=8`, `sampleRateReduction=4`) rather than the documented clean no-op defaults.
- **Visible DS controls** — when effects are enabled, SampleSmith also writes a simple documented-size `812x375` DecentSampler `<ui>` tab with visible knobs bound to the correct effect positions where the binding parameter is known. `K` checkboxes decide which main controls appear as DS knobs. If one knob is selected for an effect, it uses the effect title, e.g. Reverb or Delay; if two or more are selected, SampleSmith creates a boxed section with the effect title and parameter labels such as Amount, Room, Damp, Time, and Feedback. Knobs use visual defaults from DecentSampler’s official boilerplate template, include DecentSampler `defaultValue` settings, and each SampleSmith effect row has a small defaults button for restoring sensible documented/example defaults. The main Tone knob now uses the official boilerplate frequency translation table. Bit crusher has verified knobs for bit depth, sample-rate reduction, and mix; stereo simulator currently only exposes a DS knob for the documented/verified `FX_WIDTH` binding while exporting the other settings statically.
- **Convolution reverb / IR** — adds a DecentSampler `<effect type="convolution">` when you provide an IR file path and mix above zero. IR means impulse response; the file path must be valid from the `.dspreset`, e.g. `Samples/long hall.wav`. SampleSmith does not yet copy/manage IR files for you.
- **Version caveat** — newer DecentSampler effects require a recent DecentSampler build (for example, `stereo_simulator` was introduced in DS 1.17.0). If an exported effect is ignored by DecentSampler, first check the installed plug-in/app version.

The **Notes** table is the effective exported sample mapping. It shows each note, which keys it plays on, the DecentSampler root note, the audio file, status (`Recorded`, `Generated`, or `Covered`), loop status, and available actions such as **Bridge gap**. Double-click **Plays on keys**, **Root note**, or **Audio file** to edit key mapping.

## Current limits / next improvements

SampleSmith is useful now, but still growing. The broader wishlist lives in [ROADMAP.md](ROADMAP.md).

Likely next steps:

- sharpen audio recording/review handling, including waveform selection, original backups/reset, round-robin takes, and quality checks
- add round-robin takes so one note can have multiple natural-sounding sample variants
- keep improving waveform loop visualisation beyond the first-pass loop/crossfade display
- add more precise waveform zoom, marker dragging, nudging, and auditioning
- add velocity layers
- refine DecentSampler UI controls
- add Reaper-specific helper/export workflow
- support manual note correction more elegantly

## Notes

`samplesmith_app/assets/official-boilerplate.dspreset` stores a cleaned-name copy of DecentSampler’s official boilerplate template as a reference for generated UI/binding conventions.

Pitch detection works best for clear single notes. If the sound is noisy, percussive, growly, breathy, or chord-like, enter the note manually.
