from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QDate, QThreadPool, QTime, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from plotdas_client.models import ImageRecord, PlotRequest, Project

from .error_dialog import show_error
from .image_viewer import ImageViewerWidget
from .worker import Worker


class PlotPage(QWidget):
    preview_completed = Signal(str)

    def __init__(
        self,
        projects: list[Project],
        preview: Callable[[PlotRequest, str], ImageRecord],
        password_provider: Callable[[], str],
        parent=None,
    ):
        super().__init__(parent)
        self.preview_action = preview
        self.password_provider = password_provider
        self.pool = QThreadPool.globalInstance()

        title = QLabel("绘图")
        title.setObjectName("pageTitle")
        self.project = QComboBox()
        self.project.addItems([item.name for item in projects])
        self.date = QDateEdit(QDate(2023, 3, 8))
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd")
        self.start_time = QTimeEdit(QTime(12, 0, 0))
        self.start_time.setDisplayFormat("HH:mm:ss")
        self.end_time = QTimeEdit(QTime(12, 1, 0))
        self.end_time.setDisplayFormat("HH:mm:ss")
        self.channel_start = QSpinBox()
        self.channel_start.setRange(0, 1_000_000)
        self.channel_start.setValue(390)
        self.channel_end = QSpinBox()
        self.channel_end.setRange(1, 1_000_001)
        self.channel_end.setValue(882)
        self.filter_type = QComboBox()
        self.filter_type.addItems(["none", "bandpass", "lowpass", "highpass"])
        self.lowcut = QDoubleSpinBox()
        self.lowcut.setRange(0.001, 100_000)
        self.lowcut.setValue(2.0)
        self.highcut = QDoubleSpinBox()
        self.highcut.setRange(0.001, 100_000)
        self.highcut.setValue(40.0)
        self.dpi = QSpinBox()
        self.dpi.setRange(50, 1200)
        self.dpi.setValue(200)
        self.window_length = QComboBox()
        self.window_length.addItems(["10", "30", "60", "300"])
        self.window_length.setCurrentText("60")

        form = QFormLayout()
        for label, widget in (
            ("Project", self.project),
            ("Date", self.date),
            ("Start Time", self.start_time),
            ("End Time", self.end_time),
            ("Channel Start", self.channel_start),
            ("Channel End", self.channel_end),
            ("Filter Type", self.filter_type),
            ("Lowcut (Hz)", self.lowcut),
            ("Highcut (Hz)", self.highcut),
            ("DPI", self.dpi),
            ("Window Length (s)", self.window_length),
        ):
            form.addRow(label, widget)
        parameters = QGroupBox("预览参数")
        parameters.setLayout(form)

        self.preview_button = QPushButton("预览")
        self.preview_button.setObjectName("primaryButton")
        self.preview_button.clicked.connect(self._preview)
        batch = QPushButton("开始批量绘图")
        batch.setEnabled(False)
        batch.setToolTip("将在下一阶段 Job Manager 中启用")
        actions = QHBoxLayout()
        actions.addWidget(self.preview_button)
        actions.addWidget(batch)

        left_layout = QVBoxLayout()
        left_layout.addWidget(parameters)
        left_layout.addLayout(actions)
        left_layout.addStretch()
        left = QWidget()
        left.setLayout(left_layout)

        self.viewer = ImageViewerWidget()
        self.metadata = QTextEdit()
        self.metadata.setReadOnly(True)
        self.metadata.setPlaceholderText("完成预览后显示服务器 metadata")
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.viewer, 4)
        right_layout.addWidget(QLabel("Metadata"))
        right_layout.addWidget(self.metadata, 1)
        right = QWidget()
        right.setLayout(right_layout)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([330, 900])
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(splitter, 1)
        self.filter_type.currentTextChanged.connect(self._update_filter_fields)
        self._update_filter_fields("none")

    def set_projects(self, projects: list[Project], selected: str | None = None) -> None:
        current = selected or self.project.currentText()
        self.project.clear()
        self.project.addItems([item.name for item in projects])
        if current:
            self.project.setCurrentText(current)

    def _update_filter_fields(self, kind: str) -> None:
        self.lowcut.setEnabled(kind in {"bandpass", "highpass"})
        self.highcut.setEnabled(kind in {"bandpass", "lowpass"})

    def request(self) -> PlotRequest:
        selected_date = self.date.date().toPython()
        start = datetime.combine(selected_date, self.start_time.time().toPython())
        end = datetime.combine(selected_date, self.end_time.time().toPython())
        kind = self.filter_type.currentText()
        return PlotRequest(
            project=self.project.currentText(),
            start_time=start,
            end_time=end,
            channel_start=self.channel_start.value(),
            channel_end=self.channel_end.value(),
            filter_type=kind,
            lowcut=self.lowcut.value() if kind in {"bandpass", "highpass"} else None,
            highcut=self.highcut.value() if kind in {"bandpass", "lowpass"} else None,
            dpi=self.dpi.value(),
            window_length=int(self.window_length.currentText()),
        )

    def _preview(self) -> None:
        try:
            request = self.request()
            request.validate()
        except ValueError as exc:
            show_error(self, str(exc))
            return
        self.preview_button.setEnabled(False)
        self.preview_button.setText("服务器绘图中…")
        password = self.password_provider()
        worker = Worker(lambda: self.preview_action(request, password))
        worker.signals.succeeded.connect(self._show_result)
        worker.signals.failed.connect(lambda message, detail: show_error(self, message, detail))
        worker.signals.finished.connect(self._preview_finished)
        self.pool.start(worker)

    def _show_result(self, record: ImageRecord) -> None:
        if record.local_image_path is None:
            show_error(self, "预览已返回，但本地图片路径为空")
            return
        self.viewer.load_image(record.local_image_path)
        import json

        self.metadata.setPlainText(json.dumps(record.metadata, ensure_ascii=False, indent=2))
        self.preview_completed.emit(str(record.local_image_path))

    def _preview_finished(self) -> None:
        self.preview_button.setEnabled(True)
        self.preview_button.setText("预览")
