"""Small modal dialog to pick the export format."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QDialogButtonBox,
)


class ExportOptions:
    def __init__(self, fmt, subtype, bitrate):
        self.fmt = fmt            # "wav" | "mp3"
        self.subtype = subtype    # "PCM_24" | "PCM_16"
        self.bitrate = bitrate    # kbps for mp3


class ExportDialog(QDialog):
    def __init__(self, num_segments: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export")
        v = QVBoxLayout(self)

        v.addWidget(QLabel(
            f"{num_segments} Abschnitt(e) werden exportiert."
            if num_segments != 1 else "1 Abschnitt wird exportiert."))

        self.fmt = QComboBox()
        self.fmt.addItems(["WAV 24-bit", "WAV 16-bit", "MP3"])
        v.addLayout(self._row("Format", self.fmt))

        self.bitrate = QComboBox()
        self.bitrate.addItems(["320", "256", "192", "128"])
        self.bitrate_row = self._row("MP3-Bitrate (kbps)", self.bitrate)
        v.addLayout(self.bitrate_row)

        self.fmt.currentIndexChanged.connect(self._update_bitrate_visibility)
        self._update_bitrate_visibility()

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        v.addWidget(buttons)

    def _row(self, text, widget):
        h = QHBoxLayout()
        h.addWidget(QLabel(text))
        h.addWidget(widget, 1)
        return h

    def _update_bitrate_visibility(self):
        is_mp3 = self.fmt.currentText() == "MP3"
        for i in range(self.bitrate_row.count()):
            w = self.bitrate_row.itemAt(i).widget()
            if w:
                w.setVisible(is_mp3)

    def options(self) -> ExportOptions:
        text = self.fmt.currentText()
        if text == "MP3":
            return ExportOptions("mp3", "PCM_24", int(self.bitrate.currentText()))
        subtype = "PCM_24" if "24" in text else "PCM_16"
        return ExportOptions("wav", subtype, 320)
