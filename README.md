# SampleSmith

A first-pass helper for building Decent Sampler instruments from sounds you can make.

It now has two entry points:

- `samplesmith.py` — GUI prototype. This is the main Carl-friendly route.
- `sampler_capture.py` — original CLI prototype, still useful for dry-runs and automation.

It is designed for two workflows:

1. **Pitched mode** — for voice, whistles, single-note instruments, etc.
   - asks for an instrument name
   - records the lowest usable note and detects the pitch
   - records the highest usable note and detects the pitch
   - plays each reference note in the range
   - records you copying that note
   - trims/normalises the WAV
   - creates a basic Decent Sampler `.dspreset`

2. **Unpitched / pad mode** — for hits, breaths, mouth noises, objects, scrapes, claps, etc.
   - asks for a kit/instrument name
   - records labelled sounds
   - maps each sound to consecutive MIDI notes/pads
   - creates a basic Decent Sampler `.dspreset`

## Install dependencies

SampleSmith uses Tkinter for the GUI. Python often includes it, but if not:

```bash
sudo apt install python3-tk
```

On the machine doing the recording:

```bash
python -m pip install sounddevice soundfile numpy
```

Optional, for better pitch detection:

```bash
python -m pip install librosa
```

Without `librosa`, the script uses a simpler built-in autocorrelation pitch detector. That may be fine for clear monophonic sounds, but it will be less reliable for breathy/noisy notes.

## Run the GUI

From this folder:

```bash
python samplesmith.py
```

The GUI is the intended everyday route: set the name/output folder, choose pitched or pads, then record. Each recording now writes/updates both the `.dspreset` and a `.samplesmith.json` project file automatically; the generate/save buttons are there for manual regeneration. Use **Open project** to return to an existing SampleSmith project. Decent Sampler export settings live on their own **Decent Sampler** tab so loop and playback controls can grow there.

In pitched mode you can either record-detect the lowest/highest notes or type them manually, e.g. `C2`, `F#3`, or a MIDI number. It shows the key mapping for each recorded note, including MIDI numbers, so octave-label differences between Python/Reaper/Decent Sampler do not hide what is actually mapped.

Current Decent Sampler output parameters:

- **Loop samples** — writes `loopEnabled="true"` on generated sample entries. Proper loop start/end editing is still a later feature.
- **Root offset** — shifts exported `rootNote` values without moving the playable key ranges. Default is `-12` because Carl's first tests came out sounding an octave low; set it back to `0` if your setup does not need that correction.
- **Built-in effects** — delay, lowpass, and chorus controls write ordinary Decent Sampler `<effect>` entries, e.g. `<effect type="delay" ... />`, `<effect type="lowpass" />`, and `<effect type="chorus" ... />`.
- **Advanced convolution reverb / IR** — adds a Decent Sampler `<effect type="convolution">` when you provide an IR file path and mix above zero. IR means impulse response; the file path must be valid from the `.dspreset`, e.g. `Samples/long hall.wav`. SampleSmith does not yet copy/manage IR files for you.

## Run the CLI

```bash
python sampler_capture.py
```

Or choose a mode directly:

```bash
python sampler_capture.py --mode pitched --name VoiceAh
python sampler_capture.py --mode pads --name MouthPercussion
```

Output defaults to:

```text
captured-samplers/<InstrumentName>/
  <InstrumentName>.dspreset
  Samples/
    <InstrumentName>_C3.wav
    ...
```

Open the `.dspreset` in Decent Sampler, including from Reaper.

## Mapping behaviour

Default pitched behaviour is classic sampler spreading: SampleSmith generates a playable instrument from whatever samples have actually been recorded, even one sample. One recorded pitched sample maps across the whole keyboard. With multiple pitched samples, each recording maps from the previous recorded root note to the next recorded root note, so neighbouring samples overlap between their home notes. For example, recorded C3/C4 maps C3 from MIDI 0–60 and C4 from MIDI 48–127, giving an overlap/blend zone between them. This can make strange-but-useful transformed sounds, such as very low growls.

Possible later range modes:

- full keyboard — current/default
- captured range only
- custom low/high playable range

## Test without audio hardware

This creates silent dummy WAVs and a preset, useful for checking the flow:

```bash
python sampler_capture.py --mode pads --name TestPads --dry-run
```

For the dry-run pad test, enter one or two labels, then blank to finish.

## Current limits / next improvements

This is an MVP, not the finished musical tool.

Likely next steps:

- add a small GUI or single-key controls for keep/redo/skip
- add velocity layers
- add round-robin takes
- add loop-point detection for sustained notes
- improve Decent Sampler UI controls
- add Reaper-specific helper/export workflow
- support manual note correction more elegantly
- add a review pass for clipped/quiet/too-short samples

## Notes

Pitched detection works best for clear single notes. If the sound is noisy, percussive, growly, breathy, or chord-like, use pad mode.
