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
python -m pip install sounddevice soundfile numpy
```

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

For example, recorded C3/C4 maps C3 from MIDI `0–60` and C4 from MIDI `48–127`, giving an overlap/blend zone between them. This can make strange-but-useful transformed sounds, such as very low growls.

Possible later range modes:

- full keyboard — current/default
- captured range only
- custom low/high playable range

## Decent Sampler settings

Decent Sampler export settings live on their own **Decent Sampler** tab so loop, tone, reverb, and playback controls can keep growing without cluttering the recording workflow.

Current Decent Sampler output parameters:

- **Loop samples** — writes `loopEnabled="true"` on generated sample entries. Proper loop start/end editing is still a later feature.
- **Root offset** — shifts exported `rootNote` values without moving the playable key ranges. Default is `-12` because early tests came out sounding an octave low; set it back to `0` if your setup does not need that correction.
- **Decent Sampler effects** — SampleSmith includes the documented DS effect types: filters (`lowpass`, `lowpass_1pl`, legacy `lowpass_4pl`, `bandpass`, `highpass`), `notch`, `peak`, `gain`, `reverb`, `delay`, `chorus`, `phaser`, `convolution`, `pitch_shift`, `wave_folder`, `wave_shaper`, `stereo_simulator`, and `bit_crusher`.
- **Visible DS controls** — when effects are enabled, SampleSmith also writes a simple Decent Sampler `<ui>` tab with visible knobs bound to the correct effect positions where the binding parameter is known. `K` checkboxes decide which main controls appear as DS knobs. If one knob is selected for an effect, it uses the effect title, e.g. Reverb or Delay; if two or more are selected, SampleSmith creates a boxed section with the effect title and parameter labels such as Amount, Room, Damp, Time, and Feedback. Knobs include Decent Sampler `defaultValue` settings, and each SampleSmith effect row has a small defaults button for restoring sensible documented/example defaults.
- **Convolution reverb / IR** — adds a Decent Sampler `<effect type="convolution">` when you provide an IR file path and mix above zero. IR means impulse response; the file path must be valid from the `.dspreset`, e.g. `Samples/long hall.wav`. SampleSmith does not yet copy/manage IR files for you.

The **Effective exported sample mapping** table shows which WAV will play on which MIDI keys, including exported root notes, so octave-label differences between Python/Reaper/Decent Sampler do not hide what is actually mapped.

## Current limits / next improvements

SampleSmith is useful now, but still growing.

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
