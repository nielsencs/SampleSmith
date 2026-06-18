# SampleSmith roadmap and wishlist

SampleSmith is already useful as a small DecentSampler instrument builder. This document collects the next ideas before they get lost. It is intentionally broader than the current implementation plan: some items are tiny polish tasks, some are proper feature projects, and some may turn out not to be worth doing.

## Current direction

The goal is practical DecentSampler instrument building for ordinary musicians and sound-tinkerers:

- record or import sounds quickly
- map them sensibly without needing to hand-write `.dspreset` XML
- keep DecentSampler output readable and portable
- help people make playable instruments from imperfect real-world recordings
- stay focused on the graphical app rather than adding a separate command-line workflow
- cooperate with DAWs/audio editors when useful, but never become a DAW itself

## Near-term priorities

### 1. Sharpen recording and file handling

- continue reducing unnecessary preamble/friction for straightforward single-sample recording
- refine keep / waveform trim / record-another-take / reset-from-backup review after recording a note into a right-hand selected-sample panel
- make it easier to record several takes for the same note
- review samples for clipping, very low level, silence, and too-short recordings
- show basic audio-file facts in the GUI: duration, sample rate, channels, peak level, RMS-ish loudness
- make normalise/trim behaviour waveform-based, visible, and less surprising
- keep improving original-recording preservation now that edited audio files get `.samplesmith-backups/` reset copies
- support FLAC as well as WAV where DecentSampler/project workflow allows it
- improve stray-file review so imported audio files can be assigned to notes, velocity layers, or round-robin takes
- support replacing one recorded audio file without disturbing the rest of the instrument

### 2. Round-robin takes

Real sampled instruments often use multiple samples for the same note so repeated notes do not sound mechanically identical.

Wishlist:

- allow each note to hold multiple audio takes
- export multiple `<sample>` entries for the same key/root/range with DecentSampler round-robin behaviour
- show takes clearly in the mapping table
- support add/remove/reorder takes
- support naming takes, e.g. `soft`, `normal`, `bright`, `growly`, or `take 1/2/3`
- decide how round-robin interacts with generated bridge samples
- decide how round-robin interacts with velocity layers
- optionally allow random or sequential playback mode if DecentSampler supports both well enough

### 3. Waveform loop visualisation

Loop controls need to be visible before they can become precise.

Wishlist:

- draw loop start and loop end markers over the waveform
- shade the loop region
- improve the first-pass crossfade display so crossfade length is even clearer near the loop boundary
- make invalid loop/crossfade settings obvious
- show imported WAV loop markers separately from SampleSmith's edited loop points
- show sample positions and time values while hovering/dragging
- include a compact whole-sample overview plus a zoomed editing view

### 4. More precise waveform editing

Once loop visualisation is clear, improve the editor.

Wishlist:

- refine zoom controls around loop start and loop end, including possible independent start/end zoom levels and preferred wheel direction defaults
- pan through a zoomed waveform
- drag handles for sample start/end, loop start/end, and crossfade length
- nudge selected marker by one sample / small time increment / larger time increment
- snap markers to zero crossings when helpful
- optional auto-find nearby zero crossing
- audition raw loop and crossfaded loop from inside the editor
- refine loop audition restart behaviour after edits, including status messages and edge cases when edits temporarily make the loop invalid
- keyboard shortcuts for play/stop, zoom, nudge, and marker selection
- undo/redo for loop edits

## Medium-term instrument features

### Velocity layers

- allow quiet/medium/loud samples for the same note
- export velocity-specific sample entries
- show velocity ranges in the mapping table
- allow round-robin takes within a velocity layer
- provide a simple default, e.g. one layer means full velocity range

### Mapping modes

- keep current classic full-keyboard spreading as the default
- add captured-range-only mode
- add custom playable low/high range
- allow manual override of a sample's key range
- make overlap/blend zones easier to understand visually
- provide a warning when mappings overlap in a surprising way

### Bridge samples

- keep bridge audio generation optional and explicit, not a hidden export side effect
- allow bridge generation for one selected missing note
- allow bridge generation for a selected range of missing notes
- make generated bridge files clearly generated and easy to replace with real recordings later

### Import-first workflow

SampleSmith should support audio that was recorded or rendered elsewhere without becoming a DAW. The app's job is still instrument assembly: review, map, bridge, loop, check, and export.

- add **Import audio folder…** for `.flac` / `.wav` files
- import a folder of audio files and infer notes from filenames where possible
- refine stray-audio note/root filename guessing and show confidence before accepting inferred mappings
- support common filename patterns like `Instrument_C3_01.wav`, `C#4_rr2.wav`, `note60_vel90.wav`, or `root_72_take_2.flac`
- recognise take/round-robin hints like `_take2`, `_rr2`, `_soft`, `_loud`, or `_vel90` when those features exist
- offer a review screen before accepting inferred mappings, with editable guessed note/root/status columns
- allow drag/drop of audio files if Tkinter support is practical
- show what will be copied/linked/ignored before committing the import
- keep folder import as a normal Notes workflow, not a separate “DAW mode”

### Naming convention helper

Predictable names make import, debugging, and hand inspection easier, but SampleSmith should help rather than enforce.

- prefer simple generated recording names like `Instrument_Note.flac`
- use clear take names when takes exist, e.g. `Instrument_Note_take2.flac`
- use clear generated names under `Samples/generated/`, e.g. `Instrument_Note_generated.flac`
- offer a “suggest tidy names” or “rename imported files” review step before changing anything
- warn when two files look like they describe the same note/take
- document filename patterns that SampleSmith understands

### Better note and pitch handling

- show detected pitch confidence
- allow manual correction of detected note/root more elegantly
- support non-standard tuning reference, e.g. A4 not exactly 440 Hz
- support detune/cents correction in exported samples if DecentSampler handles it cleanly
- keep DecentSampler's C4/key-72 convention clearly documented

## DecentSampler export polish

- keep generated `.dspreset` XML readable and stable in diffs
- continue testing effect parameter bindings against DecentSampler itself
- manage/copy convolution IR files into the exported instrument folder
- consider a simple DecentSampler UI theme/layout choice
- support more visible controls for sample start, loop, tone, envelope, and effects where bindings are verified
- document which exported features need newer DecentSampler versions

### Export summary and XML confidence view

Before or after export, SampleSmith should give a reassuring plain-English summary rather than forcing users to read XML.

- show counts: audio files, note rows, recorded samples, generated samples, covered notes, loops, visible DS controls
- show mapping summary: lowest/highest key, root-note convention, overlaps, uncovered notes
- show loop summary: custom loops, fallback/default loop settings, invalid or suspicious loops
- show export paths for `.dspreset`, `.dsbundle`, `Samples/`, and copied IR files
- provide a **View XML** button for debugging/confidence, but keep it read-only by default
- optionally add “copy XML snippet” for reporting/export debugging later

## Instrument checks and diagnostics

Add a **Check instrument** button/panel that catches common DecentSampler and SampleSmith problems before export.

Possible checks:

- missing audio files
- generated file referenced by the project but missing on disk
- note has no own audio and is not covered by any mapped sample
- surprising overlapping key ranges
- root note outside its playable key range
- impossible loop: end before start, loop outside file length, or crossfade longer than the loop
- loop points on very short files or almost-silent regions
- filename suggests one note but the project root note says another
- suspicious audio: silence, clipping, extremely low level, very short duration, odd sample rate/channel count
- export folder contains stray audio not in the project
- duplicate-looking files or duplicate-looking note/take mappings

Presentation idea:

- ✅ OK items stay quiet unless expanded
- ⚠️ warnings for things that may be intentional, such as a covered note with no own recording
- ❌ errors for things likely to break export/playback, such as missing files
- each warning should offer a relevant action where possible: select note, open loop editor, review stray audio, locate file, generate bridge sample

## Working alongside other audio tools

SampleSmith should be comfortable in a Reaper/Audacity/TextPad-style workflow, but it should not become a DAW.

- add a short “record elsewhere, assemble here” guide
- add a Reaper-friendly recording/rendering note if it genuinely helps Carl's process
- add a reference-note playback mode that is easy to record against
- make it easy to open the output folder after export
- maybe add a `build test pack` button for diagnostic instruments
- avoid timeline editing, multitrack recording, plugin hosting, mixing, or DAW-style transport features

## Quality checks and tests

- automated export smoke tests for `.dspreset` structure
- tests for mapping ranges and DecentSampler key convention
- tests for project save/load compatibility
- tests for WAV marker parsing
- tests for round-robin and velocity-layer export once implemented
- keep generated diagnostic packs ignored by Git

## Community / project polish

- add screenshots or a short demo GIF/video
- add a clearer first-run guide
- add example instruments or a tiny demo pack if licensing is clean
- add a CONTRIBUTING guide once outside contributions are realistic
- add issue templates for bugs and feature ideas
- document supported platforms honestly, especially audio-device quirks
- keep the README practical rather than pretending the app is more finished than it is

## Open questions

- Should round-robin be attached to notes from the first implementation?
- Should velocity layers come before or after round-robin?
- Should original audio files and processed audio files both be kept, or is that too much clutter for early versions?
- How much waveform editing should SampleSmith own, versus expecting Audacity/Reaper for heavy editing?
- Should bridge audio remain a visible/manual feature only, or eventually become a more guided workflow?
- How should SampleSmith present DecentSampler features that are version-dependent or only partly documented?
