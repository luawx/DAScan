from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .ui import MainWindow


def application_root() -> Path:
    override = os.environ.get("PLOTDAS_CLIENT_HOME")
    return Path(override).resolve() if override else Path(__file__).resolve().parents[2]


def configure_logging(root: Path) -> None:
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_dir / "client.log", encoding="utf-8")],
    )


STYLE = """
QMainWindow { background: #f5f7fa; }
#navigation { background: #172033; color: #dbe4f3; border: none; padding-top: 18px; }
#navigation::item { height: 46px; margin: 3px 10px; border-radius: 6px; }
#navigation::item:selected { background: #2d5bff; color: white; }
QWidget { font-size: 14px; color: #202939; }
QStackedWidget > QWidget { background: #f8fafc; }
QGroupBox { font-weight: 600; margin-top: 12px; padding-top: 14px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QTimeEdit, QTextEdit,
QPlainTextEdit, QTreeWidget, QTableWidget {
  background: white; border: 1px solid #d5dce8; border-radius: 5px; padding: 6px;
}
QPushButton { background: white; border: 1px solid #ccd5e3; border-radius: 5px; padding: 7px 14px; }
QPushButton:hover { border-color: #2d5bff; }
QPushButton:disabled { color: #929bad; background: #eef1f5; }
QProgressBar { background: #e5eaf2; border: none; border-radius: 5px; height: 12px; text-align: center; }
QProgressBar::chunk { background: #2d5bff; border-radius: 5px; }
#primaryButton { background: #2d5bff; color: white; border-color: #2d5bff; }
#pageTitle { font-size: 24px; font-weight: 700; padding: 8px 0; }
"""


def main() -> int:
    root = application_root()
    configure_logging(root)
    app = QApplication(sys.argv)
    app.setApplicationName("PlotDas Desktop")
    app.setStyleSheet(STYLE)
    window = MainWindow(root)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
