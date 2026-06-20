# SampleSmithSample quick start

SampleSmithSample is a tiny starter instrument for learning SampleSmith. It contains four simple WAV tones (`C3`, `E3`, `G3`, `C4`), a SampleSmith project file, and a generated DecentSampler preset.

## Open it in SampleSmith

1. Start SampleSmith.
2. Click **Open project**.
3. Open `samplesmith-projects/SampleSmithSample/SampleSmithSample.samplesmith.json`.

The **Notes** tab should show a short note list from C3 to C4. The four supplied WAV files are already mapped, so you can inspect the rows before recording anything.

## Try it in DecentSampler

Open this file in DecentSampler:

```text
samplesmith-projects/SampleSmithSample/SampleSmithSample.dspreset
```

Play around the mapped notes. The preset uses the WAV files in the `Samples/` folder and adds a gentle reverb control.

## Build or change the note list

In SampleSmith:

1. Set the low note and high note in **Notes**.
2. Choose a step size. `4` gives C/E/G-style thirds for this demo; `12` gives octaves; `1` gives every semitone.
3. Click the button to build/update the note list.
4. Record or import audio onto the notes you actually have.

You do not need to record every note. SampleSmith spreads the available samples across the keyboard.

## Replace the demo WAVs with your own recordings

Easy route:

1. Select a note row, such as `C3`.
2. Use the **Selected sample** panel to record a new take or import audio.
3. Trim the start/end if needed, then keep the take.
4. SampleSmith updates the `.samplesmith.json` and `.dspreset` files.

Manual route:

1. Put your WAV or FLAC files in the `Samples/` folder.
2. Use filenames with notes when possible, for example `MyBell_C3.wav` or `note72.wav`.
3. In SampleSmith, use **Import audio…**, **Import folder…**, or **Review stray audio**.
4. Check the guessed root notes and save/generate the preset.

## Export a portable DecentSampler bundle

When the project sounds right, click **Export .dsbundle**. SampleSmith creates a movable DecentSampler bundle beside the project folder with its own copied samples and preset.
