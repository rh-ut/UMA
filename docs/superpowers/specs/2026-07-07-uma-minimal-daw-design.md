# UMA — Minimale DAW zum synchronen Zusammenführen von Multitrack-WAVs

**Datum:** 2026-07-07
**Status:** Entwurf genehmigt, bereit für Implementierungsplan

## Zweck

Ein minimaler, fokussierter Multitrack-Editor, der 3–8 parallel aufgenommene
Rohspuren (WAV/FLAC) synchron zu einem Stereomix zusammenführt. Die Spuren
stammen typischerweise aus einem **Soundcraft Ui24R**, der jeden Kanal als
einzelne, unbearbeitete Datei (WAV oder FLAC, 48 kHz) in einen nummerierten
Ordner unter einem `Multitrack`-Elternordner schreibt. Alle Kanäle werden
gleichzeitig aufgenommen und sind damit sample-genau synchron ab Sample 0.

Kein Ersatz für eine große DAW — bewusst schlank: importieren, ansehen,
global trimmen/schneiden, Pegel + Pan setzen, vorhören, exportieren.

## Kernprinzip: Synchronität by-design

Alle Spuren teilen **eine gemeinsame, sample-basierte Zeitachse**. Es gibt
keinen Per-Spur-Zeitversatz und kein Verschieben von Material. Trim und
Aufteilung wirken **global** auf die ganze Session. Dadurch ist ein
Auseinanderdriften strukturell unmöglich — die Mix-Funktion liest für alle
Spuren denselben Sample-Bereich.

## Nicht-Ziele (YAGNI)

- Keine Per-Spur-Zeitverschiebung / kein Alignment-Offset (Annahme: synchron ab Sample 0)
- Keine Effekte (EQ, Kompressor, Hall) außer optionaler Master-Clip-Anzeige
- Keine Automation von Reglern über die Zeit
- Keine unterschiedlichen Sampleraten pro Spur (wird abgefangen/gewarnt, nicht resampelt)
- Kein destruktives Editieren der Quelldateien (Quellen bleiben unangetastet)

## Technologie-Stack

| Aufgabe | Bibliothek | Begründung |
|---|---|---|
| GUI | **PySide6** (Qt) | Offizielles Qt für Python, LGPL |
| WAV/FLAC lesen/schreiben | **soundfile** (libsndfile) | Block-Reads + Seeking → streaming-fähig; liest WAV & FLAC transparent |
| Audio-Ausgabe | **sounddevice** (PortAudio) | Callback-basierte Wiedergabe, plattformübergreifend |
| Numerik/Mixing | **numpy** | Summe, Gain, Pan in Echtzeit |
| MP3-Export (optional) | **lameenc** | LAME-Binding, echte Bitratenkontrolle, kein System-ffmpeg nötig |

**Zwei bewusste Design-Entscheidungen:**

1. **Waveform-Darstellung:** eigenes `QPainter`-Widget mit vorberechneter
   Min/Max-Peak-Pyramide (statt pyqtgraph) — leichtgewichtig, volle Kontrolle,
   keine schwere Extra-Abhängigkeit.
2. **Audio-Engine:** Producer-Thread + Ringpuffer (statt direktem Lesen im
   Audio-Callback) — verhindert Aussetzer beim Streaming langer Dateien.
   Kosten: ~30–50 ms Latenz bei Regleränderungen, beim Vorhören irrelevant.

## Datenmodell

Die reine Datenlogik ist von GUI und Audio-Hardware getrennt (testbar).

**Session** — das Projekt, eine gemeinsame Zeitachse:
- `sample_rate: int`
- `frames: int` — Länge = längste Spur
- `master_gain: float`
- `tracks: list[Track]`
- `in_point: int`, `out_point: int` — globaler Trim in Samples
- `split_markers: list[int]` — Schnittpunkte (Samples), sortiert, zwischen In/Out

**Track** — eine Kanaldatei:
- `path: str`, `name: str`, `color`
- `gain: float`, `pan: float` (−1…+1), `mute: bool`, `solo: bool`
- `frames: int`, Datei-Handle (`soundfile.SoundFile`, für Streaming)
- `peaks` — Min/Max-Peak-Pyramide (mehrere Auflösungsstufen)

**Abschnitte (Segmente):** abgeleitet aus `in_point`, `out_point` und
`split_markers` — die Bereiche zwischen aufeinanderfolgenden Grenzen. Jeder
Abschnitt wird als eigene Datei exportiert. Ohne Splits → ein Abschnitt.

## Fenster-Layout

Ein Hauptfenster, klassischer Multitrack-Aufbau:

```
┌────────────────────────────────────────────────────────────────┐
│  [Import Session…] [Import Dateien…]     [▶ Play] [■ Stop]  ⏱ 00:00 │  Toolbar
├──────────────┬─────────────────────────────────────────────────┤
│ CH 1  Drums  │ Waveform (min/max) ─ gemeinsame Zeitachse         │
│ [M][S] pegel │      │        │              │                    │
│ Gain ──●──   │      ┊        ┊              ┊                    │
│ Pan  ──●──   │     In     Split          Split                Out│
├──────────────┼─────────────────────────────────────────────────┤
│ CH 2 … 3–8 Spuren vertikal gestapelt, gemeinsame Zeitachse …     │
├──────────────┴─────────────────────────────────────────────────┤
│ Master ──●──  Clip●   [Zoom − +]   Abschnitte: 1│2│3  [Export…]   │  Master/Status
└──────────────────────────────────────────────────────────────────┘
              ↑ Playhead läuft synchron über alle Spuren
```

- **Links pro Spur** (feste Breite): Name, Mute/Solo, Gain- und Pan-Regler,
  kleine Pegel-/Clip-Anzeige.
- **Rechts**: Waveforms aller Spuren, vertikal gestapelt, **gemeinsame
  horizontale Zeitachse**. Playhead, In/Out- und Split-Marker sind senkrechte
  Linien über die volle Höhe (weil global).
- **Unten**: Master-Gain mit Clip-LED, Zoom, Abschnittsliste, Export.
- **Interaktion**: In/Out und Splits per Klick/Ziehen auf der Zeitachse;
  Zoom per Buttons/Mausrad.

## Audio-Fluss

**Gemeinsame Mix-Funktion** — Herzstück, von Wiedergabe *und* Export genutzt:

```
mix_block(start_frame, n_frames) -> stereo[n_frames, 2]:
    solo_aktiv = irgendeine Spur auf Solo?
    summe = zeros(n_frames, 2)
    für jede Spur:
        wenn mute, oder (solo_aktiv und nicht solo): überspringen
        block = spur.read(start_frame, n_frames)   # mono, gestreamt; über Ende → Stille
        l, r = pan_gesetz(block * gain, pan)        # gleichläufiges Pan-Gesetz
        summe += [l, r]
    return summe * master_gain
```

Alle Spuren lesen denselben `start_frame`/`n_frames` → sample-genaue
Synchronität per Konstruktion, unabhängig von Reglerstellungen.

**Pan-Gesetz:** gleichläufiges (constant-power) Panning, damit die
wahrgenommene Lautstärke beim Schwenken konstant bleibt.

**Wiedergabe (live, streaming):**

```
Producer-Thread          Ringpuffer          Audio-Callback (sounddevice)
liest & mixt Blöcke  --> [====>    ]  -->     zieht Blöcke, gibt aus
folgt Playhead           (~50 ms Vorlauf)     meldet Playhead an GUI
```

- Regler (Gain/Pan/Mute/Solo/Master) werden **atomar** gelesen → Änderungen
  greifen live beim nächsten Block.
- Play/Stop und Playhead-Verschieben setzen `start_frame` neu und leeren den
  Ringpuffer → sofortiges Springen.
- Playhead-Position wird zur GUI zurückgemeldet (für den laufenden Cursor).

**Export (offline):**

```
für jeden Abschnitt (zwischen In/Out und Splits):
    Ausgabe öffnen (WAV oder MP3)
    in Blöcken über [seg_start … seg_end]:
        stereo = mix_block(...)
        WAV:  soundfile.write-block
        MP3:  lameenc.encode(stereo) -> anfügen
    Datei abschließen
```

Kein Echtzeit-Zwang, kein Ringpuffer. Identische Mix-Logik wie Playback →
**was du hörst, wird exportiert.**

## Clipping-Handling

Master-Regler + **Clip-Warnung** (klassisch, kein automatischer Eingriff):
- Rote Clip-Anzeige pro Spur und am Master, wenn der Pegel 0 dBFS überschreitet.
- Der Nutzer regelt Pegel/Master selbst. Kein Limiter, keine Normalisierung.

## Import

Zwei Wege:
- **Session-Ordner:** Nutzer wählt den nummerierten Ui24R-Aufnahmeordner; App
  listet alle enthaltenen Kanaldateien (WAV + FLAC), sortiert nach
  Kanalnummer/natürlicher Reihenfolge; Nutzer wählt 3–8 aus.
- **Einzelne Dateien:** freie Auswahl beliebiger WAV/FLAC.

**Prüfungen beim Import:**
- Gleiche Samplerate über alle gewählten Spuren? Wenn nicht → Warnung,
  abweichende Datei ablehnen (kein Resampling in v1).
- Unterschiedliche Längen erlaubt: Zeitachse = längste Spur; kürzere Spuren
  gelten danach als Stille.
- Fehlende/beschädigte Dateien → klare Meldung, kein Absturz.

## Waveform-Peaks

- Beim Laden pro Spur einmal eine **Min/Max-Peak-Pyramide** über die Datei
  berechnet (mehrere Auflösungsstufen), gestreamt in Blöcken.
- Das Widget zeichnet für die aktuelle Zoomstufe aus der passenden
  Pyramidenstufe → flüssig auch bei langen Dateien, ohne Rohdaten neu zu lesen.
- Berechnung im Hintergrund-Thread mit Fortschrittsanzeige; GUI friert nicht ein.

## Export-Format

- **WAV** (primär, verlustfrei): 24-bit PCM Default, 16-bit optional.
- **MP3** (optional, via `lameenc`): Bitrate wählbar (z.B. 192/256/320 kbps).
- Samplerate = Session-Rate (z.B. 48 kHz).
- Pro Abschnitt eine Datei. Namensschema: Basisname + fortlaufende Nummer
  (`mix_01.wav`, `mix_02.wav`); bei nur einem Abschnitt eine Datei.

## Fehlerbehandlung

- Import-Prüfung (Samplerate/Format), fehlende/beschädigte Dateien.
- Audio-Gerät nicht verfügbar → klare Meldung statt Absturz; Editieren/Export
  bleibt ohne Wiedergabe möglich.
- Export: Zielpfad/Schreibrechte prüfen, MP3-Encoder verfügbar prüfen.

## Architektur / Modul-Grenzen

Schichten mit klaren Verantwortlichkeiten, damit die DSP-Logik unabhängig von
GUI und Audio-Hardware testbar ist:

- **`model`** — reine Datenklassen (`Session`, `Track`, Abschnitts-Ableitung).
  Keine GUI-, keine I/O-Abhängigkeit.
- **`dsp`** — `mix_block`, Pan-Gesetz, Peak-Pyramiden-Berechnung. Reine
  numpy-Funktionen, vollständig unit-testbar.
- **`io`** — Import (Ordner/Dateien scannen, öffnen, prüfen) und Export
  (WAV/MP3 schreiben). Dünn über `soundfile`/`lameenc`.
- **`engine`** — Producer-Thread + Ringpuffer + sounddevice-Stream für
  synchrone Wiedergabe. Nutzt `dsp.mix_block`.
- **`ui`** — PySide6-Fenster, Spur-Widgets, Waveform-Widget, Regler, Dialoge.
  Dünne Schicht über model/dsp/engine/io.

## Teststrategie

- **Unit-Tests** für `dsp` und `model` mit synthetischen WAVs:
  - `mix_block`: bekannter Sinus/Konstante → geprüfter Summenpegel.
  - Pan-Gesetz: L/R-Verhältnis bei −1 / 0 / +1 geprüft; Constant-Power-Kurve.
  - Peak-Pyramide: Min/Max stimmen mit Rohdaten überein.
  - **Sync-Check:** identischer Sample-Offset über mehrere Spuren nach
    Trim/Split (Kern-Anforderung).
  - Abschnitts-Ableitung aus In/Out + Splits.
- **I/O-Tests:** Roundtrip Import → Export → Reimport, Samplerate-Mismatch-Warnung.
- GUI/Audio-I/O bleiben dünne Schichten und werden manuell/rauchgetestet.

## Offene Punkte für den Implementierungsplan

- Genaues Kanal-Namensschema des Ui24R (Sortierung) — beim Import robust per
  natürlicher Sortierung + optionaler manueller Umsortierung lösen.
- Blockgröße / Ringpuffer-Vorlauf konkret festlegen (Start: 1024 Frames Block,
  ~4–8 Blöcke Vorlauf).
- Peak-Pyramiden-Stufen (z.B. Faktor 8 pro Stufe) und Basis-Bucketgröße.
