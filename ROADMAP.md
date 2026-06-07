# SampleSmith roadmap and wishlist

SampleSmith is already useful as a small DecentSampler instrument builder. This document collects the next ideas before they get lost. It is intentionally broader than the current implementation plan: some items are tiny polish tasks, some are proper feature projects, and some may turn out not to be worth doing.

## Current direction

The goal is practical DecentSampler instrument building for ordinary musicians and sound-tinkerers:

- record or import sounds quickly
- map them sensibly without needing to hand-write `.dspreset` XML
- keep DecentSampler output readable and portable
- help people make playable instruments from imperfect real-world recordings
- stay focused on the graphical app rather than adding a separate command-line workflow

## Near-term priorities

### 1. Sharpen recording and file handling

- continue reducing unnecessary preamble/friction for straightforward single-sample recording
- refine keep / trim / redo / clear review after recording a note or pad into a right-hand selected-sample panel
- make it easier to record several takes for the same note
- review samples for clipping, very low level, silence, and too-short recordings
- show basic audio-file facts in the GUI: duration, sample rate, channels, peak level, RMS-ish loudness
- make normalise/trim behaviour waveform-based, visible, and less surprising
- preserve original recordings where useful, with processed/export-ready copies clearly marked
- support FLAC as well as WAV where DecentSampler/project workflow allows it
- improve stray-file review so imported audio files can be assigned to notes, pads, velocity layers, or round-robin takes
- support replacing one recorded audio file without disturbing the rest of the instrument

### 2. Round-robin takes

Real sampled instruments often use multiple samples for the same note so repeated notes do not sound mechanically identical.

Wishlist:

- allow each note/pad to hold multiple WAV takes
- export multiple `<sample>` entries for the same key/root/range with DecentSampler round-robin behaviour
- show takes clearly in the mapping table
- support add/remove/reorder takes
- support naming takes, e.g. `soft`, `normal`, `bright`, `growly`, or `take 1/2/3`
- decide how round-robin interacts with generated bridge WAVs
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
- make generated bridge files clearly provisional and easy to replace with real recordings later

### Import-first workflow

- import a folder of WAV/FLAC files and infer notes from filenames where possible
- refine stray-audio note/root filename guessing and show confidence before accepting inferred mappings
- support common filename patterns like `Instrument_C3_01.wav`, `C#4_rr2.wav`, `note60_vel90.wav`, or `root_72_take_2.flac`
- offer a review screen before accepting inferred mappings
- allow drag/drop of audio files if Tkinter support is practical

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
- add an export summary: samples, mappings, loops, effects, visible controls

## Reaper / DAW workflow ideas

- add a Reaper-friendly recording workflow note or helper
- maybe generate a Reaper project/template for stepping through notes
- add a reference-note playback mode that is easy to record against
- make it easy to open the output folder after export
- maybe add a `build test pack` button for diagnostic instruments

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

- Should round-robin be attached to pitched notes, pads, or both from the first implementation?
- Should velocity layers come before or after round-robin?
- Should original WAVs and processed WAVs both be kept, or is that too much clutter for early versions?
- How much waveform editing should SampleSmith own, versus expecting Audacity/Reaper for heavy editing?
- Should bridge audio remain a visible/manual feature only, or eventually become a more guided workflow?
- How should SampleSmith present DecentSampler features that are version-dependent or only partly documented?
