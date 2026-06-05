# SampleSmith

SampleSmith is a GUI tool for turning recorded sounds into playable Decent Sampler instruments.

It is built for the practical Reaper / Decent Sampler / Audacity sort of workflow: make a sound, record it, map it sensibly, and get a `.dspreset` plus WAV samples that can be opened in Decent Sampler.

The aim is classic sampler usefulness rather than laboratory purity. If you only record one pitched sample, SampleSmith spreads it across the keyboard. If you record several, it maps them into overlapping ranges so each sample keeps its home note while still giving you the transformed low/high sampler sounds that can be musically useful.

## What it does

SampleSmith currently supports two main workflows:

1. **Pitched instruments** — for voice, whistles, single-note instruments, growls, drones, etc.
   - detect or manually enter the lowest and highest notes
   - build a note list across the range
   - play reference notes
   - record matching samples
   - trim and normalise the WAVs
   - map the recorded samples across the keyboard
   - optionally generate clearly marked provisional bridge WAVs for missing notes between recorded notes
   - generate a Decent Sampler `.dspreset`

2. **Unpitched / pad instruments** — for hits, breaths, mouth noises, objects, scrapes, claps, one-shots, etc.
   - record labelled sounds
   - map each sound to consecutive MIDI notes/pads
   - generate a Decent Sampler `.dspreset`

SampleSmith also saves a `.samplesmith.json` project file so an instrument can be reopened and extended later.

## Install dependencies

SampleSmith uses Tkinter for the GUI. Python often includes it, but if not:

```bash
sudo apt install python3-tk
```

On the machine doing the recording:

```bash
python -m pip install -r requirements.txt
```

That installs `sounddevice`, `soundfile`, and `numpy`. Bridge WAV generation needs `soundfile` and `numpy`.

Optional, for better pitch detection:

```bash
python -m pip install librosa
```

Without `librosa`, SampleSmith uses a simpler built-in autocorrelation pitch detector. That may be fine for clear monophonic sounds, but it will be less reliable for breathy/noisy notes.

## Run SampleSmith

From this folder:

```bash
python samplesmith.py
```

Set the instrument name and output folder, choose **Pitched** or **Unpitched / Pads**, then record. Each recording writes/updates both the `.dspreset` and the `.samplesmith.json` project file automatically; the generate/save buttons are there for manual regeneration.

Use **Open project** to return to an existing SampleSmith project.

Use **Review stray WAVs** if you have copied or recorded WAV files into the instrument/project folders outside SampleSmith. SampleSmith only checks the current project/instrument/sample folders, never the whole filesystem, and it asks before importing anything into the mapping.

Output defaults to:

```text
captured-samplers/<InstrumentName>/
  <InstrumentName>.dspreset
  <InstrumentName>.samplesmith.json
  Samples/
    <InstrumentName>_C3.wav
    ...
```

Open the `.dspreset` in Decent Sampler, including from Reaper.

## Pitched mapping behaviour

Default pitched behaviour is classic sampler spreading: SampleSmith generates a playable instrument from whatever samples have actually been recorded, even one sample.

- One recorded pitched sample maps across the whole keyboard.
- Multiple pitched samples map from the previous recorded root note to the next recorded root note.
- Neighbouring samples overlap between their home notes.
- Use **Generate bridge WAVs** on the Pitched tab to explicitly write provisional blended WAV files under `Samples/generated/` for missing notes between recorded samples. SampleSmith does not generate them as a hidden export side effect. Existing generated bridge WAVs are included in the visible/exported mapping and deliberately marked `[GENERATED provisional]` so they are easy to replace later with proper recorded samples.

For example, recorded C3/C4 maps C3 from MIDI `0–60` and C4 from MIDI `48–127`, giving an overlap/blend zone between them. This can make strange-but-useful transformed sounds, such as very low growls.

Possible later range modes:

- full keyboard — current/default
- captured range only
- custom low/high playable range

## Decent Sampler settings

Decent Sampler export settings live on their own **Decent Sampler** tab so loop, tone, reverb, and playback controls can keep growing without cluttering the recording workflow. That tab now has nested sub-tabs for **Basics / Export**, **Tone**, **Space**, **Shape**, and **Mapping** rather than one long wall of controls.

Current Decent Sampler output parameters:

- **Loop samples** — writes `loopEnabled="true"` on generated sample entries. The visible controls are fallback/default loop settings for the whole project: manual `loopStart` / `loopEnd` sample positions plus `loopCrossfade` and `loopCrossfadeMode` (`equal_power` or `linear`). The Mapping tab also has **Edit selected WAV loop…**, which opens a per-WAV graphical loop editor with a full waveform display, zoomed signed-waveform panes where a click sets the loop start/end, draggable rough loop-start/end handles, numeric fields, crossfade settings, and an individual **Import WAV marker** action. Per-sample loop fields (`loop_enabled`, `loop_start`, `loop_end`, `loop_crossfade`, `loop_crossfade_mode`) are saved in the project and take priority during export. If loop is enabled but no valid manual start/end is entered, SampleSmith leaves the explicit points out so Decent Sampler can still use embedded WAV loop markers when present. The Decent Sampler tab also has a first-pass “Use first WAV marker” helper for importing the first `smpl` loop marker it finds in the recorded WAVs.
- **Amp ADSR envelope** — optional group-level amp envelope export using documented Decent Sampler attributes: `ampEnvEnabled`, `attack`, `decay`, `sustain`, and `release`. When enabled, SampleSmith can also write visible Decent Sampler knobs bound to the documented group amp parameters `ENV_ATTACK`, `ENV_DECAY`, `ENV_SUSTAIN`, and `ENV_RELEASE`.
- **Root offset** — shifts exported `rootNote` values without moving the playable key ranges. Default is `-12` because early tests came out sounding an octave low; set it back to `0` if your setup does not need that correction.
- **Decent Sampler effects** — SampleSmith includes all effect types documented in the current Decent Sampler effects guide: filters (`lowpass`, `lowpass_1pl`, legacy `lowpass_4pl`, `bandpass`, `highpass`), `notch`, `peak`, `gain`, `reverb`, `delay`, `chorus`, `phaser`, `convolution`, `pitch_shift`, `wave_folder`, `wave_shaper`, `stereo_simulator`, and `bit_crusher`. Wave shaper now exposes its documented `highQuality` flag, stereo simulator exposes its documented algorithm/width/delay/modulation export settings, and bit crusher defaults to audible example-style settings (`bitDepth=8`, `sampleRateReduction=4`) rather than the documented clean no-op defaults.
- **Visible DS controls** — when effects are enabled, SampleSmith also writes a simple Decent Sampler `<ui>` tab with visible knobs bound to the correct effect positions where the binding parameter is known. `K` checkboxes decide which main controls appear as DS knobs. If one knob is selected for an effect, it uses the effect title, e.g. Reverb or Delay; if two or more are selected, SampleSmith creates a boxed section with the effect title and parameter labels such as Amount, Room, Damp, Time, and Feedback. Knobs include Decent Sampler `defaultValue` settings, and each SampleSmith effect row has a small defaults button for restoring sensible documented/example defaults. Bit crusher has verified knobs for bit depth, sample-rate reduction, and mix; stereo simulator currently only exposes a DS knob for the documented/verified `FX_WIDTH` binding while exporting the other settings statically.
- **Convolution reverb / IR** — adds a Decent Sampler `<effect type="convolution">` when you provide an IR file path and mix above zero. IR means impulse response; the file path must be valid from the `.dspreset`, e.g. `Samples/long hall.wav`. SampleSmith does not yet copy/manage IR files for you.
- **Version caveat** — newer Decent Sampler effects require a recent Decent Sampler build (for example, `stereo_simulator` was introduced in DS 1.17.0). If an exported effect is ignored by Decent Sampler, first check the installed plug-in/app version.

The **Effective exported sample mapping** table shows which WAV will play on which MIDI keys, including exported root notes, so octave-label differences between Python/Reaper/Decent Sampler do not hide what is actually mapped.

## Current limits / next improvements

SampleSmith is useful now, but still growing.

Likely next steps:

- add a small GUI or single-key controls for keep/redo/skip
- add velocity layers
- add round-robin takes
- improve loop-point detection/preview for sustained notes
- add audition/playback controls to the graphical per-WAV loop editor
- refine Decent Sampler UI controls
- add Reaper-specific helper/export workflow
- support manual note correction more elegantly
- add a review pass for clipped/quiet/too-short samples

## Notes

Pitched detection works best for clear single notes. If the sound is noisy, percussive, growly, breathy, or chord-like, use pad mode.
