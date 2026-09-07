from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThreadPool, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from plotdas_client.models import Job

from .error_dialog import show_error
from .metadata_widget import MetadataWidget
from .worker import Worker

STATUS_LABELS = {
    "pending": "等待中",
    "running": "运行中",
    "completed": "已完成",
    "failed": "失败",
    "cancelled": "已取消",
}


class JobPage(QWidget):
    def __init__(
        self,
        list_jobs: Callable[[str], list[Job]],
        password_provider: Callable[[], str],
        parent=None,
    ):
        super().__init__(parent)
        self.list_jobs_action = list_jobs
        self.password_provider = password_provider
        self.pool = QThreadPool.globalInstance()
        self.jobs: list[Job] = []
        self._refreshing = False
        self._loaded_once = False

        title = QLabel("任务管理")
        title.setObjectName("pageTitle")
        self.refresh_button = QPushButton("刷新任务")
        self.refresh_button.setObjectName("primaryButton")
        self.refresh_button.clicked.connect(self.refresh)
        self.auto_refresh = QCheckBox("运行中每 5 秒自动刷新")
        self.auto_refresh.setChecked(True)
        self.auto_refresh.toggled.connect(self._auto_refresh_changed)
        self.status = QLabel("进入页面后读取服务器 job list")
        actions = QHBoxLayout()
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.auto_refresh)
        actions.addWidget(self.status, 1)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Job ID", "项目", "状态", "进度", "创建时间", "PID", "失败数"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.currentCellChanged.connect(self._show_details)

        detail_panel = QWidget()
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(8, 0, 0, 0)
        detail_layout.addWidget(QLabel("任务详情"))
        self.details = MetadataWidget()
        detail_layout.addWidget(self.details, 1)
        detail_panel.setMinimumWidth(340)

        splitter = QSplitter()
        splitter.addWidget(self.table)
        splitter.addWidget(detail_panel)
        splitter.setSizes([1100, 420])

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(actions)
        layout.addWidget(splitter, 1)

        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._loaded_once:
            self._loaded_once = True
            self.refresh()
        self._update_timer()

    def hideEvent(self, event) -> None:
        self.timer.stop()
        super().hideEvent(event)

    def refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        self.refresh_button.setEnabled(False)
        self.status.setText("正在执行服务器 job list …")
        password = self.password_provider()
        worker = Worker(lambda: self.list_jobs_action(password))
        worker.signals.succeeded.connect(self._show_jobs)
        worker.signals.failed.connect(self._failed)
        worker.signals.finished.connect(self._refresh_finished)
        self.pool.start(worker)

    def _show_jobs(self, jobs: list[Job]) -> None:
        selected_id = None
        if 0 <= self.table.currentRow() < len(self.jobs):
            selected_id = self.jobs[self.table.currentRow()].job_id
        self.jobs = jobs
        self.table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            values = [
                job.job_id,
                job.project or "—",
                STATUS_LABELS.get(job.status, job.status),
                "",
                self._friendly_time(job.created_at),
                str(job.pid) if job.pid is not None else "—",
                str(job.failed),
            ]
            for column, value in enumerate(values):
                if column != 3:
                    self.table.setItem(row, column, QTableWidgetItem(value))
            progress = QProgressBar()
            progress.setRange(0, max(1, job.total))
            progress.setValue(job.completed)
            progress.setFormat(f"{job.completed:,} / {job.total:,}  (%p%)")
            self.table.setCellWidget(row, 3, progress)
        running = sum(job.status == "running" for job in jobs)
        self.status.setText(f"共 {len(jobs)} 个任务 · {running} 个运行中")
        if jobs:
            selected_row = next((index for index, job in enumerate(jobs) if job.job_id == selected_id), 0)
            self.table.setCurrentCell(selected_row, 0)
        else:
            self.details.set_metadata(None)
        self._update_timer()

    def _show_details(self, row: int, _column: int, _old_row: int, _old_column: int) -> None:
        if 0 <= row < len(self.jobs):
            self.details.set_metadata(self.jobs[row].raw)

    def _failed(self, message: str, details: str) -> None:
        self.status.setText(message)
        show_error(self, message, details)

    def _refresh_finished(self) -> None:
        self._refreshing = False
        self.refresh_button.setEnabled(True)

    def _auto_refresh_changed(self, _enabled: bool) -> None:
        self._update_timer()

    def _update_timer(self) -> None:
        should_run = (
            self.isVisible()
            and self.auto_refresh.isChecked()
            and any(job.status == "running" for job in self.jobs)
        )
        if should_run and not self.timer.isActive():
            self.timer.start()
        elif not should_run:
            self.timer.stop()

    @staticmethod
    def _friendly_time(value: str | None) -> str:
        return value.replace("T", " ")[:19] if value else "—"
