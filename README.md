# Sample Smith

A first-pass Python helper for building Decent Sampler instruments from sounds you can make.

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

On the machine doing the recording:

```bash
python -m pip install sounddevice soundfile numpy
```

Optional, for better pitch detection:

```bash
python -m pip install librosa
```

Without `librosa`, the script uses a simpler built-in autocorrelation pitch detector. That may be fine for clear monophonic sounds, but it will be less reliable for breathy/noisy notes.

## Run

From this folder:

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
