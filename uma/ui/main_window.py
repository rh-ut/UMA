"""Main application window: assembles toolbar, track rows, transport, export."""
from __future__ import annotations

import os

import numpy as np
import soundfile as sf
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QToolBar, QFileDialog, QMessageBox, QScrollBar, QSlider, QDialog,
    QListWidget, QListWidgetItem, QDialogButtonBox, QProgressDialog,
)
from PySide6.QtGui import QAction

from ..model import Session, Track, TRACK_COLORS
from ..io_audio import open_source, scan_session_folder, export_segment
from ..engine import PlaybackEngine, MixState, audio_available
from .viewport import ViewState
from .track_row import TrackRow, CONTROL_WIDTH
from .peak_worker import PeakWorker
from .export_dialog import ExportDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UMA — Minimal Multitrack Mixer")
        self.resize(1100, 640)

        self.session: Session | None = None
        self.sources: list = []
        self.rows: list[TrackRow] = []
        self.workers: list[PeakWorker] = []
        self.state = MixState()
        self.engine: PlaybackEngine | None = None
        self.view = ViewState(0, 1000.0, 48000)
        self.play_pos = 0

        self._build_toolbar()
        self._build_body()

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._refresh_transport)
        self._timer.start()

        self._audio_ok, self._audio_reason = audio_available()
        if not self._audio_ok:
            self.status.setText(
                f"⚠ Wiedergabe deaktiviert (PortAudio fehlt: {self._audio_reason}). "
                "Import/Bearbeiten/Export funktionieren.")

    # ---- construction --------------------------------------------------
    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)

        def act(text, slot):
            a = QAction(text, self)
            a.triggered.connect(slot)
            tb.addAction(a)
            return a

        act("Import Session…", self.import_session)
        act("Import Dateien…", self.import_files)
        tb.addSeparator()
        self.play_action = act("▶ Play", self.toggle_play)
        act("■ Stop", self.stop)
        tb.addSeparator()
        act("In hier", self.set_in)
        act("Out hier", self.set_out)
        act("＋ Split", self.add_split)
        act("－ Split", self.remove_split)
        tb.addSeparator()
        act("Zoom +", lambda: self.zoom(0.5))
        act("Zoom −", lambda: self.zoom(2.0))
        act("Fit", self.fit_view)
        tb.addSeparator()
        act("Export…", self.export)

    def _build_body(self):
        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # stacked track rows
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(1)
        self.rows_layout.addStretch(1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.rows_container)
        v.addWidget(self.scroll, 1)

        # horizontal timeline scrollbar
        self.hbar = QScrollBar(Qt.Horizontal)
        self.hbar.valueChanged.connect(self._on_hscroll)
        v.addWidget(self.hbar)

        # master / status bar
        bottom = QHBoxLayout()
        bottom.setContentsMargins(8, 4, 8, 4)
        bottom.addWidget(QLabel("Master"))
        self.master = QSlider(Qt.Horizontal)
        self.master.setFixedWidth(160)
        self.master.setRange(0, 150); self.master.setValue(100)
        self.master.valueChanged.connect(
            lambda x: setattr(self.state, "master_gain", x / 100.0))
        bottom.addWidget(self.master)
        self.clip = QLabel("CLIP")
        self.clip.setStyleSheet("color:#555; font-weight:bold;")
        bottom.addWidget(self.clip)
        self.time_label = QLabel("00:00.000")
        bottom.addWidget(self.time_label)
        bottom.addStretch(1)
        self.status = QLabel("")
        bottom.addWidget(self.status)
        holder = QWidget(); holder.setLayout(bottom)
        holder.setStyleSheet("background:#222; color:#ddd;")
        v.addWidget(holder)

    # ---- import --------------------------------------------------------
    def import_session(self):
        folder = QFileDialog.getExistingDirectory(self, "Ui24R Session-Ordner wählen")
        if not folder:
            return
        paths = scan_session_folder(folder)
        if not paths:
            QMessageBox.warning(self, "Leer", "Keine Audiodateien in diesem Ordner.")
            return
        chosen = self._choose_files(paths)
        if chosen:
            self._load_tracks(chosen)

    def import_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Spuren wählen", "",
            "Audio (*.wav *.flac *.aif *.aiff)")
        if paths:
            self._load_tracks(paths)

    def _choose_files(self, paths) -> list[str]:
        dlg = QDialog(self)
        dlg.setWindowTitle("Spuren auswählen")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Kanäle für den Mix (empfohlen 3–8):"))
        lst = QListWidget()
        for p in paths:
            it = QListWidgetItem(os.path.basename(p))
            it.setData(Qt.UserRole, p)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            lst.addItem(it)
        v.addWidget(lst)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec() != QDialog.Accepted:
            return []
        return [lst.item(i).data(Qt.UserRole) for i in range(lst.count())
                if lst.item(i).checkState() == Qt.Checked]

    def _load_tracks(self, paths):
        self.stop()
        self._clear_tracks()

        # validate consistent sample rate
        infos = [(p, sf.info(p)) for p in paths]
        rate = infos[0][1].samplerate
        bad = [os.path.basename(p) for p, i in infos if i.samplerate != rate]
        if bad:
            QMessageBox.warning(
                self, "Samplerate weicht ab",
                "Diese Dateien haben eine andere Samplerate und werden "
                "übersprungen:\n" + "\n".join(bad))
        good = [p for p, i in infos if i.samplerate == rate]
        if not good:
            return

        tracks = []
        for idx, p in enumerate(good):
            src = open_source(p)
            self.sources.append(src)
            name = os.path.splitext(os.path.basename(p))[0]
            color = TRACK_COLORS[idx % len(TRACK_COLORS)]
            tracks.append(Track(path=p, name=name, frames=src.frames, color=color))

        self.session = Session(sample_rate=rate, tracks=tracks)
        self.session.out_point = self.session.frames
        self.state = MixState.for_tracks(tracks)
        self.view = ViewState(0, 1000.0, rate)
        self.play_pos = 0

        for idx, t in enumerate(tracks):
            row = TrackRow(idx, t.name, t.color)
            row.gain_changed.connect(self._on_gain)
            row.pan_changed.connect(self._on_pan)
            row.mute_toggled.connect(self._on_mute)
            row.solo_toggled.connect(self._on_solo)
            row.seek_requested.connect(self.seek)
            row.lane.frames = self.session.frames
            row.lane.set_view(self.view)
            self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
            self.rows.append(row)

            worker = PeakWorker(idx, t.path)
            worker.ready.connect(self._on_peaks_ready)
            self.workers.append(worker)
            worker.start()

        self.fit_view()
        self.status.setText(
            f"{len(tracks)} Spuren · {rate} Hz · "
            f"{self._fmt_time(self.session.frames)}")

    def _clear_tracks(self):
        for w in self.workers:
            w.quit(); w.wait(200)
        self.workers.clear()
        for row in self.rows:
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self.rows.clear()
        for s in self.sources:
            s.close()
        self.sources.clear()

    def _on_peaks_ready(self, index, pyramid):
        if 0 <= index < len(self.rows):
            self.rows[index].lane.pyramid = pyramid
            self.rows[index].lane.update()

    # ---- mix parameter callbacks --------------------------------------
    def _on_gain(self, idx, v): self.state.gains[idx] = v
    def _on_pan(self, idx, v): self.state.pans[idx] = v
    def _on_mute(self, idx, on): self.state.mutes[idx] = on
    def _on_solo(self, idx, on): self.state.solos[idx] = on

    # ---- transport -----------------------------------------------------
    def toggle_play(self):
        if self.engine and self.engine.is_playing:
            self.stop()
        else:
            self.play()

    def play(self):
        if not self.session or not self.session.tracks:
            return
        if not self._audio_ok:
            QMessageBox.information(
                self, "Keine Wiedergabe",
                f"PortAudio ist nicht verfügbar:\n{self._audio_reason}\n\n"
                "Installiere es mit:  sudo apt-get install -y libportaudio2")
            return
        self.engine = PlaybackEngine(
            self.sources, self.state, self.session.sample_rate,
            end_frame=self.session.effective_out,
            on_position=self._on_engine_pos)
        start = self.play_pos
        if start >= self.session.effective_out or start < self.session.in_point:
            start = self.session.in_point
        self.engine.play(start, self.session.effective_out)
        self.play_action.setText("⏸ Pause")

    def stop(self):
        if self.engine:
            self.engine.close()
            self.engine = None
        self.play_action.setText("▶ Play")

    def seek(self, frame):
        self.play_pos = int(frame)
        if self.engine and self.engine.is_playing:
            self.engine.set_position(self.play_pos)
        self._update_markers()

    def _on_engine_pos(self, frame):
        self.play_pos = int(frame)   # atomic; read by the GUI timer

    # ---- markers -------------------------------------------------------
    def set_in(self):
        if self.session:
            self.session.in_point = min(self.play_pos, self.session.effective_out)
            self._update_markers()

    def set_out(self):
        if self.session:
            self.session.out_point = max(self.play_pos, self.session.in_point)
            self._update_markers()

    def add_split(self):
        if self.session and self.session.in_point < self.play_pos < self.session.effective_out:
            if self.play_pos not in self.session.split_markers:
                self.session.split_markers.append(self.play_pos)
                self._update_markers()

    def remove_split(self):
        if not self.session or not self.session.split_markers:
            return
        # remove the split nearest the playhead
        nearest = min(self.session.split_markers, key=lambda s: abs(s - self.play_pos))
        self.session.split_markers.remove(nearest)
        self._update_markers()

    def _update_markers(self):
        if not self.session:
            return
        s = self.session
        for row in self.rows:
            row.lane.set_markers(s.in_point, s.effective_out,
                                 list(s.split_markers), self.play_pos)

    # ---- view / zoom / scroll -----------------------------------------
    def _lane_width(self) -> int:
        return max(100, self.width() - CONTROL_WIDTH - 30)

    def fit_view(self):
        if self.session and self.session.frames:
            self.view.fit(self.session.frames, self._lane_width())
        self._apply_view()

    def zoom(self, factor):
        self.view.zoom(factor, self._lane_width() / 2)
        self._apply_view()

    def _apply_view(self):
        for row in self.rows:
            row.lane.set_view(self.view)
        self._sync_scrollbar()
        self._update_markers()

    def _sync_scrollbar(self):
        if not self.session:
            return
        visible = int(self._lane_width() * self.view.samples_per_pixel)
        total = self.session.frames
        self.hbar.blockSignals(True)
        self.hbar.setRange(0, max(0, total - visible))
        self.hbar.setPageStep(max(1, visible))
        self.hbar.setValue(int(self.view.start_frame))
        self.hbar.blockSignals(False)

    def _on_hscroll(self, value):
        self.view.start_frame = value
        for row in self.rows:
            row.lane.set_view(self.view)
        self._update_markers()

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            self.zoom(0.8 if ev.angleDelta().y() > 0 else 1.25)
        else:
            super().wheelEvent(ev)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._sync_scrollbar()

    # ---- transport refresh (GUI thread) --------------------------------
    def _refresh_transport(self):
        if self.session:
            self.time_label.setText(self._fmt_time(self.play_pos))
            self._update_markers()
            if self.engine and self.engine.last_peak >= 1.0:
                self.clip.setStyleSheet("color:#ff3333; font-weight:bold;")
            else:
                self.clip.setStyleSheet("color:#555; font-weight:bold;")
            if self.engine and not self.engine.is_playing:
                self.stop()

    # ---- export --------------------------------------------------------
    def export(self):
        if not self.session or not self.session.tracks:
            return
        segments = self.session.segments()
        if not segments:
            QMessageBox.warning(self, "Nichts zu exportieren",
                                "Der In/Out-Bereich ist leer.")
            return
        dlg = ExportDialog(len(segments), self)
        if dlg.exec() != QDialog.Accepted:
            return
        opts = dlg.options()
        ext = "mp3" if opts.fmt == "mp3" else "wav"

        if len(segments) == 1:
            path, _ = QFileDialog.getSaveFileName(
                self, "Export", f"mix.{ext}", f"*.{ext}")
            if not path:
                return
            targets = [(segments[0], path)]
        else:
            folder = QFileDialog.getExistingDirectory(self, "Zielordner")
            if not folder:
                return
            targets = [(seg, os.path.join(folder, f"mix_{i+1:02d}.{ext}"))
                       for i, seg in enumerate(segments)]

        self._run_export(targets, opts)

    def _run_export(self, targets, opts):
        st = self.state
        prog = QProgressDialog("Exportiere…", "Abbrechen", 0, len(targets), self)
        prog.setWindowModality(Qt.WindowModal)
        try:
            for i, (seg, path) in enumerate(targets):
                prog.setValue(i)
                if prog.wasCanceled():
                    break
                export_segment(
                    self.sources, st.gains, st.pans, st.mutes, st.solos,
                    st.master_gain, seg, self.session.sample_rate, path,
                    fmt=opts.fmt, subtype=opts.subtype, bitrate=opts.bitrate)
            prog.setValue(len(targets))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export-Fehler", str(exc))
            return
        self.status.setText(f"Export fertig: {len(targets)} Datei(en).")

    # ---- helpers -------------------------------------------------------
    def _fmt_time(self, frame) -> str:
        sr = self.session.sample_rate if self.session else 48000
        secs = frame / sr
        m = int(secs // 60)
        s = secs - m * 60
        return f"{m:02d}:{s:06.3f}"

    def closeEvent(self, ev):
        self.stop()
        self._clear_tracks()
        super().closeEvent(ev)
