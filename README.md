# UMA — Minimal Multitrack Mixer

A small, focused desktop tool to merge 3–8 synchronously-recorded raw tracks
(WAV/FLAC — e.g. a **Soundcraft Ui24R** multitrack USB recording) into a stereo
mix. All tracks share one sample-based timeline, so they stay
sample-accurately synchronous by construction — no drift is possible.

## Features

- **Import** a Ui24R session folder (auto-lists channel files, natural-sorted,
  pick the channels you want) or choose individual files. WAV and FLAC.
- **Waveform display** of every track, stacked on a shared timeline, drawn from
  a min/max peak pyramid with per-pixel envelope aggregation — smooth at any
  zoom, responsive even on long recordings.
- **Global trim** (In/Out) and **split markers** that divide the session into
  segments, each exported as its own file. Set them from the toolbar or edit
  them directly with the mouse.
- **Per-track level (gain) and pan** (constant-power), plus **mute/solo**.
- **Synchronous playback** of all tracks (producer thread + ring buffer) with a
  master gain and a clip indicator.
- **Export** each segment to stereo **WAV** (24/16-bit) or **MP3** (192–320 kbps).

## Usage

Workflow: **Import → trim/split → set levels & pan → preview → Export**.

| Action | How |
|---|---|
| Load a Ui24R recording | *Import Session…* → pick the session folder → tick the channels |
| Load arbitrary files | *Import Dateien…* |
| Move the playhead / seek | Left-click on a waveform |
| Set trim In / Out at the playhead | *In hier* / *Out hier* toolbar buttons |
| Add / remove a split at the playhead | *+ Split* / *− Split* toolbar buttons |
| **Move any marker** (In, Out, split) | **Drag it** on the waveform (cursor turns ↔) |
| **Add a split** | **Double-click** on the waveform |
| **Remove a split** | **Right-click** the split |
| Zoom | *Zoom + / −* or *Fit* buttons, or **Ctrl + mouse wheel** |
| Scroll along time | horizontal scrollbar under the tracks |
| Level / pan / mute / solo | the per-track controls on the left |
| Play / Stop | toolbar; playback follows In→Out |
| Export | *Export…* → choose WAV/MP3; one file per segment |

The bottom bar shows the master gain, a **CLIP** indicator (lights red if the
mix exceeds 0 dBFS — lower the master or track gains), the playhead time, and
the session summary (track count · sample rate · length).

## Windows (standalone, no X server)

UMA runs natively on Windows — Qt uses native windows, so **no X server is
needed**, and the `sounddevice` Windows package bundles PortAudio, so **live
playback works with no extra install**.

**Prebuilt executables** (produced by the build below):

- `dist\uma.exe` — single self-contained file, portable anywhere; first launch
  takes a few seconds while it unpacks.
- `dist_onedir\uma\uma.exe` — starts instantly, but it is a folder: keep the
  `uma` folder together (make a desktop *shortcut* to the exe, don't move it
  out alone).

**Build them yourself** — with Python 3.10+ for Windows on PATH:

```powershell
powershell -ExecutionPolicy Bypass -File build_windows.ps1
```

This creates a venv, installs dependencies, runs the tests, and produces both
`dist\uma.exe` and `dist_onedir\uma\uma.exe`.

**Run from source on Windows** (no packaging):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py -m uma
```

If Windows SmartScreen warns about the unsigned exe: *More info → Run anyway*.

## Install (Linux/macOS)

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt        # or: pip install -e .
```

**Live playback** needs the PortAudio system library:

```bash
sudo apt-get install -y libportaudio2   # Debian/Ubuntu/WSL
```

Without it the app still runs — import, edit and export all work; only
monitoring is disabled (with a clear notice). On Windows and macOS PortAudio
comes bundled with the `sounddevice` wheel, so no extra step is needed.

## Run

```bash
python -m uma            # or: uma   (after pip install -e .)
```

## Architecture

Clear layers so the DSP logic is testable independent of GUI and audio hardware.
Everything is sample-based on one shared timeline, which is what guarantees
synchronicity — there is no per-track time offset that could drift.

| Module | Responsibility |
|---|---|
| `uma/model.py` | `Session`/`Track` on a shared timeline; segment derivation |
| `uma/dsp.py` | constant-power pan law, `mix_block` (shared by playback + export) |
| `uma/peaks.py` | min/max peak pyramid + per-pixel `pixel_envelope` for drawing |
| `uma/io_audio.py` | streaming WAV/FLAC import, session scan, WAV/MP3 export |
| `uma/engine.py` | producer-thread + ring-buffer synchronous playback |
| `uma/ui/viewport.py` | frame↔pixel mapping, zoom, marker hit-testing |
| `uma/ui/` | PySide6 window, waveform lanes, track controls, export dialog |

`mix_block` is deliberately shared between the live engine and the offline
exporter, so **what you hear is exactly what you export**.

## Tests

```bash
python -m pytest                                                  # unit tests
QT_QPA_PLATFORM=offscreen PYTHONPATH=. python tools/smoke_gui.py  # headless GUI smoke test
```

The unit tests (52) cover the pure DSP / model / peaks / IO / viewport logic,
including mixing, panning, segment derivation, the waveform envelope and marker
hit-testing. The GUI and audio I/O are thin layers over that logic; the
offscreen smoke test exercises the full import → waveform → marker-editing →
WAV/MP3 export path without a display. Live audio playback is verified manually
(devices are detected via PortAudio; the mix path itself is unit-tested).
