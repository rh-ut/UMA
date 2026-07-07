"""Entry point: `python -m uma` or the `uma` console script."""
from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPalette, QColor
    from PySide6.QtCore import Qt

    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # dark palette suited to waveform work
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#2b2b2b"))
    pal.setColor(QPalette.WindowText, Qt.white)
    pal.setColor(QPalette.Base, QColor("#1b1b1b"))
    pal.setColor(QPalette.Text, Qt.white)
    pal.setColor(QPalette.Button, QColor("#3b3b3b"))
    pal.setColor(QPalette.ButtonText, Qt.white)
    pal.setColor(QPalette.Highlight, QColor("#3465a4"))
    pal.setColor(QPalette.HighlightedText, Qt.white)
    app.setPalette(pal)

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
