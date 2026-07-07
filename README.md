# UMA — Minimal Multitrack Mixer

A small, focused desktop tool to merge 3–8 synchronously-recorded raw tracks
(WAV/FLAC — e.g. a **Soundcraft Ui24R** multitrack USB recording) into a stereo
mix. All tracks share one sample-based timeline, so they stay
sample-accurately synchronous by construction — no drift possible.

## Features

- **Import** a Ui24R session folder (auto-lists channel files, natural-sorted)
  or pick individual files. WAV and FLAC.
- **Waveform display** of every track, stacked on a shared timeline, with a
  min/max peak pyramid so long recordings stay responsive.
- **Global trim** (In/Out) and **split markers** that divide the session into
  segments, each exported as its own file.
- **Per-track level (gain) and pan** (constant-power), plus **mute/solo**.
- **Synchronous playback** of all tracks (producer thread + ring buffer) with a
  master gain and a clip indicator.
- **Export** each segment to stereo **WAV** (24/16-bit) or **MP3** (192–320 kbps).

## Install

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
monitoring is disabled (with a clear notice).

## Run

```bash
python -m uma            # or: uma   (after pip install -e .)
```

## Architecture

Clear layers so the DSP logic is testable independent of GUI and audio hardware:

| Module | Responsibility |
|---|---|
| `uma/model.py` | `Session`/`Track` on a shared timeline; segment derivation |
| `uma/dsp.py` | constant-power pan law, `mix_block` (shared by playback + export) |
| `uma/peaks.py` | min/max envelope + resolution pyramid for waveform drawing |
| `uma/io_audio.py` | streaming WAV/FLAC import, session scan, WAV/MP3 export |
| `uma/engine.py` | producer-thread + ring-buffer synchronous playback |
| `uma/ui/` | PySide6 window, waveform lanes, controls, export dialog |

## Tests

```bash
python -m pytest                                            # unit tests (pure logic)
QT_QPA_PLATFORM=offscreen PYTHONPATH=. python tools/smoke_gui.py   # headless GUI smoke test
```

The unit tests cover the pure DSP/model/IO/viewport logic. The GUI and audio
I/O are thin layers over that logic; the offscreen smoke test exercises the
full import → waveform → markers → export path without a display, and live
playback is verified manually once PortAudio is installed.
