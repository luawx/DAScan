from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from pathlib import PurePosixPath

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from plotdas_client.config import AppSettings
from plotdas_client.models import ImageRecord, Project
from plotdas_client.services import (
    Annotation,
    AnnotationService,
    HistoryService,
    TransferEvent,
    TransferQueue,
    ViewHistoryEntry,
)
from plotdas_client.transport import CancellationToken, ProgressCallback

from .error_dialog import show_error
from .image_viewer import ImageViewerWidget
from .metadata_widget import MetadataWidget
from .worker import Worker

LOGGER = logging.getLogger(__name__)


class ImagePage(QWidget):
    focus_mode_changed = Signal(bool)

    def __init__(
        self,
        projects: list[Project],
        list_dates: Callable[[Project, str, bool], list[str]],
        list_images: Callable[[Project, str, str], list[dict]],
        fetch_image: Callable[[Project, dict, str, ProgressCallback, CancellationToken], ImageRecord],
        password_provider: Callable[[], str],
        settings: AppSettings,
        annotations: AnnotationService,
        history: HistoryService,
        parent=None,
    ):
        super().__init__(parent)
        self.projects = {project.name: project for project in projects}
        self.list_dates_action = list_dates
        self.list_images_action = list_images
        self.fetch_image_action = fetch_image
        self.password_provider = password_provider
        self.annotations = annotations
        self.history = history
        self._resume_entry = history.last_viewed()
        self._pending_history: ViewHistoryEntry | None = self._resume_entry
        self._prefetch_count = max(0, min(20, settings.prefetch_count))
        self._max_background_transfers = max(1, settings.max_background_transfers)
        self._active_project = settings.active_project
        self._data_source = settings.data_source
        self.pool = QThreadPool.globalInstance()
        self.transfer_queue = self._create_transfer_queue(self._max_background_transfers)
        self.records: list[dict] = []
        self._all_records: list[dict] = []
        self.loaded_records: dict[int, ImageRecord] = {}
        self.failed_prefetch_rows: set[int] = set()
        self.task_context: dict[str, tuple[int, int]] = {}
        self.row_tasks: dict[int, str] = {}
        self.task_rows: dict[str, int] = {}
        self.current_task_id: str | None = None
        self.generation = 0
        self._loaded_once = False
        self._focus_mode = False

        title = QLabel("图片")
        title.setObjectName("pageTitle")
        self.project = QComboBox()
        self.project.addItems(self.projects)
        initial_project = self._resume_entry.project if self._resume_entry else settings.active_project
        if initial_project in self.projects:
            self.project.setCurrentText(initial_project)
        self.refresh_button = QPushButton("刷新服务器图片")
        self.refresh_button.setObjectName("primaryButton")
        self.refresh_button.clicked.connect(lambda: self.refresh_dates(force_refresh=True))
        self.focus_button = QPushButton("专注模式")
        self.focus_button.setCheckable(True)
        self.focus_button.toggled.connect(self._set_focus_mode)
        self.only_favorites = QCheckBox("仅看收藏")
        self.only_favorites.toggled.connect(self._apply_record_filter)
        self.history_button = QToolButton()
        self.history_button.setText("历史记录")
        self.history_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.history_menu = QMenu(self.history_button)
        self.history_menu.aboutToShow.connect(self._rebuild_history_menu)
        self.history_button.setMenu(self.history_menu)
        self.favorites_button = QToolButton()
        self.favorites_button.setText("收藏夹")
        self.favorites_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.favorites_menu = QMenu(self.favorites_button)
        self.favorites_menu.aboutToShow.connect(self._rebuild_favorites_menu)
        self.favorites_button.setMenu(self.favorites_menu)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Project"))
        controls.addWidget(self.project)
        controls.addWidget(self.refresh_button)
        controls.addWidget(self.only_favorites)
        controls.addWidget(self.favorites_button)
        controls.addWidget(self.history_button)
        controls.addStretch()
        controls.addWidget(self.focus_button)

        self.dates = QListWidget()
        self.dates.currentTextChanged.connect(self._load_date)
        self.date_panel = QWidget()
        date_layout = QVBoxLayout(self.date_panel)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.addWidget(QLabel("日期"))
        date_layout.addWidget(self.dates)

        self.images = QListWidget()
        self.images.currentRowChanged.connect(self._load_image)
        self.image_panel = QWidget()
        image_layout = QVBoxLayout(self.image_panel)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.addWidget(QLabel("图片"))
        image_layout.addWidget(self.images)

        self.viewer = ImageViewerWidget()
        self.viewer.previous_requested.connect(lambda: self._move(-1))
        self.viewer.next_requested.connect(lambda: self._move(1))
        self.previous_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self.previous_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.previous_shortcut.activated.connect(lambda: self._move(-1))
        self.next_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.next_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.next_shortcut.activated.connect(lambda: self._move(1))
        self.metadata = MetadataWidget()
        self.metadata.set_visible_sections(settings.metadata_visible_sections)
        viewer_panel = QWidget()
        viewer_layout = QVBoxLayout(viewer_panel)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.addWidget(self.viewer, 1)

        self.metadata_panel = QWidget()
        metadata_layout = QVBoxLayout(self.metadata_panel)
        metadata_layout.setContentsMargins(0, 0, 0, 0)
        metadata_layout.addWidget(QLabel("图片信息"))
        metadata_layout.addWidget(self.metadata, 3)
        metadata_layout.addWidget(QLabel("完整值（点击上方字段查看）"))
        self.metadata_value = QPlainTextEdit()
        self.metadata_value.setReadOnly(True)
        self.metadata_value.setPlaceholderText("选择详情字段后在此显示完整内容")
        self.metadata_value.setMaximumHeight(90)
        self.metadata.currentItemChanged.connect(self._show_metadata_value)
        metadata_layout.addWidget(self.metadata_value)
        self.favorite_button = QPushButton("☆ 收藏")
        self.favorite_button.setCheckable(True)
        self.favorite_button.setEnabled(False)
        self.favorite_button.toggled.connect(self._favorite_changed)
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText("为当前图片添加备注…")
        self.note.setMaximumHeight(100)
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("标签，用逗号分隔，例如：微震, 爆破")
        self.favorite_group = QComboBox()
        self.favorite_group.setEditable(True)
        self.favorite_group.addItem("默认分组")
        self.favorite_group.setToolTip("输入或选择收藏分组，便于分类管理")
        self.save_note_button = QPushButton("保存备注")
        self.save_note_button.setEnabled(False)
        self.save_note_button.clicked.connect(self._save_annotation)
        metadata_layout.addWidget(self.favorite_button)
        metadata_layout.addWidget(QLabel("收藏分组"))
        metadata_layout.addWidget(self.favorite_group)
        metadata_layout.addWidget(QLabel("备注"))
        metadata_layout.addWidget(self.note)
        metadata_layout.addWidget(self.tags)
        metadata_layout.addWidget(self.save_note_button)
        self.metadata_panel.setMinimumWidth(360)
        self.metadata_panel.setMaximumWidth(600)

        browser_panel = QWidget()
        browser_layout = QVBoxLayout(browser_panel)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.addWidget(self.date_panel, 1)
        browser_layout.addWidget(self.image_panel, 3)
        browser_panel.setMinimumWidth(220)
        browser_panel.setMaximumWidth(320)
        self.browser_panel = browser_panel

        splitter = QSplitter()
        splitter.addWidget(browser_panel)
        splitter.addWidget(viewer_panel)
        splitter.addWidget(self.metadata_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([250, 1200, 280])
        self.status = QLabel("进入页面后会自动读取服务器索引。")

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress_detail = QLabel("就绪")
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_current)
        self.queue_button = QPushButton("传输队列")
        self.queue_button.setCheckable(True)
        self.queue_button.setChecked(settings.show_transfer_queue)
        self.queue_button.toggled.connect(self._toggle_queue)
        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.progress_detail)
        progress_row.addWidget(self.cancel_button)
        progress_row.addWidget(self.queue_button)

        self.queue_table = QTableWidget(0, 5)
        self.queue_table.setHorizontalHeaderLabels(["类型", "文件", "状态", "进度", "速度"])
        self.queue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.queue_table.setMaximumHeight(190)
        self.queue_table.setVisible(settings.show_transfer_queue)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(controls)
        layout.addWidget(splitter, 1)
        layout.addLayout(progress_row)
        layout.addWidget(self.queue_table)
        layout.addWidget(self.status)
        self.project.currentTextChanged.connect(lambda _: self.refresh_dates(force_refresh=False))

    def _create_transfer_queue(self, max_workers: int) -> TransferQueue:
        queue = TransferQueue(max_workers=max_workers, parent=self)
        queue.task_updated.connect(self._on_task_updated)
        queue.task_completed.connect(self._on_task_completed)
        queue.task_failed.connect(self._on_task_failed)
        return queue

    def apply_settings(self, settings: AppSettings) -> None:
        self._prefetch_count = max(0, min(20, settings.prefetch_count))
        self._active_project = settings.active_project
        self._data_source = settings.data_source
        self.metadata.set_visible_sections(settings.metadata_visible_sections)
        current = self.images.currentRow()
        if current in self.loaded_records:
            self.metadata.set_metadata(self.loaded_records[current].metadata)
        workers = max(1, settings.max_background_transfers)
        if workers != self._max_background_transfers:
            old_queue = self.transfer_queue
            self.cancel_all_transfers()
            old_queue.close()
            old_queue.deleteLater()
            self._max_background_transfers = workers
            self.transfer_queue = self._create_transfer_queue(workers)
            self.task_context.clear()
            self.row_tasks.clear()
            self.task_rows.clear()
            self.queue_table.setRowCount(0)
            self.current_task_id = None
            self.cancel_button.setEnabled(False)
        self.queue_button.setChecked(settings.show_transfer_queue)
        if settings.active_project in self.projects:
            self.project.setCurrentText(settings.active_project)
        current = self.images.currentRow()
        if current >= 0:
            self._cancel_outside_prefetch_window(current)
            self._schedule_prefetch(current)

    def set_projects(self, projects: list[Project], selected: str | None = None) -> None:
        current = selected or self.project.currentText()
        self.projects = {project.name: project for project in projects}
        self.project.blockSignals(True)
        self.project.clear()
        self.project.addItems(self.projects)
        if current in self.projects:
            self.project.setCurrentText(current)
        self.project.blockSignals(False)
        if self.isVisible() and self.projects:
            self.refresh_dates(force_refresh=False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._loaded_once and self.projects:
            self._loaded_once = True
            self.refresh_dates(force_refresh=False)

    def _current_project(self) -> Project | None:
        project = self.projects.get(self.project.currentText())
        if project and project.name == self._active_project and self._data_source:
            return replace(project, server_output=self._data_source)
        return project

    def refresh_dates(self, force_refresh: bool = False) -> None:
        project = self._current_project()
        if project is None:
            return
        password = self.password_provider()
        self.refresh_button.setEnabled(False)
        self.status.setText(f"正在读取 {project.server_output} …")
        self._set_busy("连接并读取目录…")
        worker = Worker(lambda: self.list_dates_action(project, password, force_refresh))
        worker.signals.succeeded.connect(self._show_dates)
        worker.signals.failed.connect(self._failed)
        worker.signals.finished.connect(lambda: self.refresh_button.setEnabled(True))
        self.pool.start(worker)

    def _show_dates(self, dates: list[str]) -> None:
        self.dates.blockSignals(True)
        self.dates.clear()
        self.dates.addItems(dates)
        self.dates.blockSignals(False)
        self.status.setText(f"发现 {len(dates)} 个日期目录")
        self._set_complete("目录读取完成")
        if dates:
            desired = self._pending_history
            if desired and desired.project == self.project.currentText() and desired.date in dates:
                self.dates.setCurrentRow(dates.index(desired.date))
            else:
                self.dates.setCurrentRow(len(dates) - 1)

    def _load_date(self, date: str) -> None:
        project = self._current_project()
        if project is None or not date:
            return
        password = self.password_provider()
        self.status.setText(f"正在读取 {date}/index.json …")
        self._set_busy("读取图片索引…")
        worker = Worker(lambda: self.list_images_action(project, date, password))
        worker.signals.succeeded.connect(self._show_records)
        worker.signals.failed.connect(self._failed)
        self.pool.start(worker)

    def _show_records(self, records: list[dict]) -> None:
        self._all_records = records
        self._apply_record_filter()

    def _apply_record_filter(self, _checked: bool | None = None) -> None:
        records = self._all_records
        project = self.project.currentText()
        if self.only_favorites.isChecked():
            favorites = {item.image_path for item in self.annotations.list_favorites(project)}
            records = [record for record in records if str(record.get("image_path", "")) in favorites]
        self._display_records(records)

    def _display_records(self, records: list[dict]) -> None:
        for task_id in list(self.task_context):
            self.transfer_queue.cancel(task_id)
        self.task_context.clear()
        self.row_tasks.clear()
        self.generation += 1
        self.records = records
        self.loaded_records.clear()
        self.failed_prefetch_rows.clear()
        self.current_task_id = None
        self.images.blockSignals(True)
        self.images.clear()
        for record in records:
            start = record.get("requested_start_time", record.get("start_time", ""))
            end = record.get("requested_end_time", record.get("end_time", ""))
            channels = f"ch {record.get('channel_start', '?')}–{record.get('channel_end', '?')}"
            self.images.addItem(f"{str(start)[11:19]}–{str(end)[11:19]}  {channels}")
        self.images.blockSignals(False)
        self.status.setText(f"索引中有 {len(records)} 张可查看图片")
        self._set_complete(f"已读取 {len(records)} 条图片记录")
        if records:
            desired_path = self._pending_history.image_path if self._pending_history else ""
            desired_row = next(
                (
                    index
                    for index, record in enumerate(records)
                    if str(record.get("image_path", "")) == desired_path
                ),
                0,
            )
            self._pending_history = None
            self.images.setCurrentRow(desired_row)
        else:
            self._load_annotation(None)

    def _load_image(self, row: int) -> None:
        project = self._current_project()
        if project is None or row < 0 or row >= len(self.records):
            return
        record = self.records[row]
        image_path = str(record.get("image_path", ""))
        self._load_annotation(self.annotations.get(project.name, image_path))
        self.history.record(
            project.name,
            self.dates.currentItem().text() if self.dates.currentItem() else "",
            image_path,
            " · ".join(
                filter(
                    None,
                    (
                        project.name,
                        self.dates.currentItem().text() if self.dates.currentItem() else "",
                        self.images.item(row).text() if self.images.item(row) else "",
                    ),
                )
            ),
        )
        self._cancel_outside_prefetch_window(row)
        if row in self.loaded_records:
            self.current_task_id = None
            self._show_image(row, self.loaded_records[row])
            self._schedule_prefetch(row)
            return
        self.failed_prefetch_rows.discard(row)
        self._start_fetch(row, foreground=True)

    def _start_fetch(self, row: int, foreground: bool) -> None:
        project = self._current_project()
        if project is None or row < 0 or row >= len(self.records):
            return
        generation = self.generation
        if row in self.loaded_records:
            return
        existing_task = self.row_tasks.get(row)
        if existing_task:
            if foreground and self.transfer_queue.promote(existing_task):
                self.current_task_id = existing_task
                self.cancel_button.setEnabled(True)
                self._set_busy("正在提升预取任务…")
                return
            if not foreground:
                return
            # The queue no longer owns this id (usually a cancelled prefetch
            # whose queued signal arrived later). Remove the stale mapping and
            # submit a real foreground task instead of spinning forever.
            self.row_tasks.pop(row, None)
            self.task_context.pop(existing_task, None)
        record = self.records[row]
        password = self.password_provider()
        remote_name = PurePosixPath(str(record.get("image_path", f"image-{row}"))).name
        key = f"{project.name}:{record.get('image_path')}:{record.get('created_at')}"
        if foreground:
            self.status.setText(f"正在同步图片 {row + 1}/{len(self.records)} …")
            self._set_busy("正在排队…")
        task_id = self.transfer_queue.submit(
            key,
            remote_name,
            lambda progress, token: self.fetch_image_action(project, record, password, progress, token),
            foreground,
        )
        self.task_context[task_id] = (generation, row)
        self.row_tasks[row] = task_id
        if foreground:
            self.current_task_id = task_id
            self.cancel_button.setEnabled(True)

    def _show_image(self, row: int, record: ImageRecord) -> None:
        if row != self.images.currentRow() or record.local_image_path is None:
            return
        self.viewer.load_image(record.local_image_path)
        self.metadata.set_metadata(record.metadata)
        self.status.setText(f"{row + 1}/{len(self.records)} · 本地缓存：{record.local_image_path}")

    def _show_metadata_value(self, current, _previous=None) -> None:
        self.metadata_value.setPlainText(current.text(1) if current is not None else "")

    def _prefetch_rows(self, center: int) -> list[int]:
        rows = []
        for distance in range(1, self._prefetch_count + 1):
            following = center + distance
            preceding = center - distance
            if following < len(self.records):
                rows.append(following)
            if preceding >= 0:
                rows.append(preceding)
        return rows

    def _schedule_prefetch(self, center: int) -> None:
        # Keep prefetch gentle: wait for the foreground image and submit only
        # one background transfer at a time. Completion schedules the next one.
        if self.current_task_id is not None:
            return
        if any(row != center for _generation, row in self.task_context.values()):
            return
        for row in self._prefetch_rows(center):
            if row in self.loaded_records or row in self.row_tasks or row in self.failed_prefetch_rows:
                continue
            self._start_fetch(row, foreground=False)
            break

    def _cancel_outside_prefetch_window(self, center: int) -> None:
        lower = max(0, center - self._prefetch_count)
        upper = min(len(self.records) - 1, center + self._prefetch_count)
        for task_id, (generation, row) in list(self.task_context.items()):
            if generation != self.generation or not lower <= row <= upper:
                self.transfer_queue.cancel(task_id)

    def _move(self, offset: int) -> None:
        if not self.records:
            return
        target = max(0, min(len(self.records) - 1, self.images.currentRow() + offset))
        self.images.setCurrentRow(target)

    def _load_annotation(self, annotation: Annotation | None) -> None:
        enabled = annotation is not None
        self.favorite_button.blockSignals(True)
        self.favorite_button.setChecked(bool(annotation and annotation.favorite))
        self.favorite_button.setText("★ 已收藏" if annotation and annotation.favorite else "☆ 收藏")
        self.favorite_button.blockSignals(False)
        self.favorite_button.setEnabled(enabled)
        self.save_note_button.setEnabled(enabled)
        self.note.setEnabled(enabled)
        self.tags.setEnabled(enabled)
        self.favorite_group.setEnabled(enabled)
        self.note.setPlainText(annotation.note if annotation else "")
        self.tags.setText(", ".join(annotation.tags or []) if annotation else "")
        group = annotation.group if annotation and annotation.group else "默认分组"
        if self.favorite_group.findText(group) < 0:
            self.favorite_group.addItem(group)
        self.favorite_group.setCurrentText(group)

    def _current_annotation(self) -> Annotation | None:
        project = self._current_project()
        row = self.images.currentRow()
        if project is None or not 0 <= row < len(self.records):
            return None
        image_path = str(self.records[row].get("image_path", ""))
        annotation = self.annotations.get(project.name, image_path)
        annotation.favorite = self.favorite_button.isChecked()
        annotation.note = self.note.toPlainText().strip()
        annotation.tags = [tag.strip() for tag in self.tags.text().split(",") if tag.strip()]
        annotation.group = self.favorite_group.currentText().strip() or "默认分组"
        record = self.records[row]
        annotation.event_start_time = str(
            record.get("requested_start_time", record.get("start_time", ""))
        )
        annotation.event_end_time = str(record.get("requested_end_time", record.get("end_time", "")))
        return annotation

    def _favorite_changed(self, checked: bool) -> None:
        self.favorite_button.setText("★ 已收藏" if checked else "☆ 收藏")
        self._save_annotation()

    def _save_annotation(self) -> None:
        annotation = self._current_annotation()
        if annotation is None:
            return
        self.annotations.save(annotation)
        self.status.setText("收藏与备注已保存到本机")
        if self.only_favorites.isChecked() and not annotation.favorite:
            self._apply_record_filter()

    def _rebuild_history_menu(self) -> None:
        self.history_menu.clear()
        entries = self.history.list_recent()
        if not entries:
            empty = QAction("暂无浏览记录", self.history_menu)
            empty.setEnabled(False)
            self.history_menu.addAction(empty)
            return
        for entry in entries[:30]:
            action = QAction(entry.display_label, self.history_menu)
            action.setToolTip(entry.image_path)
            action.triggered.connect(lambda _checked=False, item=entry: self._open_history(item))
            self.history_menu.addAction(action)

    def _rebuild_favorites_menu(self) -> None:
        self.favorites_menu.clear()
        favorites = self.annotations.list_favorites()
        if not favorites:
            empty = QAction("暂无收藏", self.favorites_menu)
            empty.setEnabled(False)
            self.favorites_menu.addAction(empty)
            return
        groups: dict[str, list[Annotation]] = {}
        for annotation in favorites:
            groups.setdefault(annotation.group or "默认分组", []).append(annotation)
        for group, group_items in sorted(groups.items()):
            group_menu = self.favorites_menu.addMenu(group)
            for annotation in group_items:
                date = next(
                    (
                        part
                        for part in reversed(PurePosixPath(annotation.image_path).parts)
                        if len(part) == 8 and part.isdigit()
                    ),
                    "",
                )
                name = PurePosixPath(annotation.image_path).name
                note = f" · {annotation.note[:24]}" if annotation.note else ""
                action = QAction(f"{annotation.project} · {date} · {name}{note}", group_menu)
                action.setToolTip(annotation.image_path)
                entry = ViewHistoryEntry(
                    annotation.project,
                    date,
                    annotation.image_path,
                    annotation.updated_at,
                    f"{annotation.project} · {date} · {name}",
                )
                action.triggered.connect(lambda _checked=False, item=entry: self._open_history(item))
                group_menu.addAction(action)

    def _open_history(self, entry: ViewHistoryEntry) -> None:
        if entry.project not in self.projects:
            show_error(self, f"历史记录所属项目已不存在: {entry.project}")
            return
        self._pending_history = entry
        # Do not let removing the favorites filter rebuild the *current* date
        # and consume the pending target before navigation has reached its date.
        self.only_favorites.blockSignals(True)
        self.only_favorites.setChecked(False)
        self.only_favorites.blockSignals(False)
        if self.project.currentText() != entry.project:
            self.project.setCurrentText(entry.project)
        elif entry.date and any(self.dates.item(i).text() == entry.date for i in range(self.dates.count())):
            target_date_row = next(
                i for i in range(self.dates.count()) if self.dates.item(i).text() == entry.date
            )
            if self.dates.currentRow() == target_date_row:
                # setCurrentRow does not emit when the date is already selected.
                # Rebuild from the current complete index so _display_records can
                # select the pending image path deterministically.
                self._apply_record_filter()
            else:
                self.dates.setCurrentRow(target_date_row)
        elif not entry.date:
            self._apply_record_filter()
        else:
            self.refresh_dates(force_refresh=False)

    def _failed(self, message: str, details: str) -> None:
        self.status.setText(message)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_detail.setText("失败")
        self.cancel_button.setEnabled(False)
        show_error(self, message, details)

    def _on_task_updated(self, event: TransferEvent) -> None:
        self._update_queue_row(event)
        if event.state == "cancelled":
            self._release_task(event.task_id)
            if event.task_id != self.current_task_id:
                return
            self.current_task_id = None
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress_detail.setText("已取消")
            self.cancel_button.setEnabled(False)
            return
        if event.foreground and event.state in {"queued", "transferring"}:
            self.current_task_id = event.task_id
            self.cancel_button.setEnabled(True)
        if event.task_id != self.current_task_id:
            return
        progress = event.progress
        if progress is None:
            self._set_busy("正在下载…" if event.state == "transferring" else "正在排队…")
            return
        self.progress.setRange(0, 100)
        self.progress.setValue(round(progress.percent))
        if progress.is_cached:
            self.progress_detail.setText("本地缓存")
        else:
            transferred = self._format_bytes(progress.transferred_bytes)
            total = self._format_bytes(progress.total_bytes) if progress.total_bytes else "未知"
            speed = self._format_bytes(progress.speed_bps) + "/s" if progress.speed_bps else "--"
            eta = f" · 剩余 {progress.eta_seconds:.1f}s" if progress.eta_seconds is not None else ""
            self.progress_detail.setText(f"{transferred}/{total} · {speed}{eta}")

    def _on_task_completed(self, event: TransferEvent) -> None:
        self._update_queue_row(event)
        context = self._release_task(event.task_id)
        if context is None:
            return
        generation, row = context
        if generation != self.generation or not isinstance(event.result, ImageRecord):
            return
        self.loaded_records[row] = event.result
        if row == self.images.currentRow():
            self._set_busy("正在解码图片…")
            self._show_image(row, event.result)
            cached = bool(event.progress and event.progress.is_cached)
            self._set_complete("本地缓存" if cached else "下载完成")
            self.current_task_id = None
            self.cancel_button.setEnabled(False)
        self._schedule_prefetch(self.images.currentRow())

    def _on_task_failed(self, event: TransferEvent) -> None:
        self._update_queue_row(event)
        context = self._release_task(event.task_id)
        if context and context == (self.generation, self.images.currentRow()):
            self.current_task_id = None
            self._failed(event.error, event.details)
        else:
            LOGGER.warning("Image prefetch failed: %s", event.error)
            if context:
                self.failed_prefetch_rows.add(context[1])
            self._schedule_prefetch(self.images.currentRow())

    def _release_task(self, task_id: str) -> tuple[int, int] | None:
        context = self.task_context.pop(task_id, None)
        if context is not None and self.row_tasks.get(context[1]) == task_id:
            self.row_tasks.pop(context[1], None)
        return context

    def _update_queue_row(self, event: TransferEvent) -> None:
        row = self.task_rows.get(event.task_id)
        if row is None:
            row = self.queue_table.rowCount()
            self.queue_table.insertRow(row)
            self.task_rows[event.task_id] = row
        progress = event.progress
        percent = f"{progress.percent:.0f}%" if progress else "--"
        speed = self._format_bytes(progress.speed_bps) + "/s" if progress and progress.speed_bps else "--"
        state_text = {
            "queued": "等待",
            "transferring": "传输中",
            "completed": "完成",
            "failed": "失败",
            "cancelled": "已取消",
        }.get(event.state, event.state)
        values = ["当前" if event.foreground else "预取", event.label, state_text, percent, speed]
        for column, value in enumerate(values):
            self.queue_table.setItem(row, column, QTableWidgetItem(value))
        active = sum(
            1
            for task_row in range(self.queue_table.rowCount())
            if self.queue_table.item(task_row, 2)
            and self.queue_table.item(task_row, 2).text() in {"等待", "传输中"}
        )
        self.queue_button.setText(f"传输队列 ({active})")
        self._trim_queue_rows()

    def _trim_queue_rows(self) -> None:
        while self.queue_table.rowCount() > 100:
            removed_ids = [task_id for task_id, row in self.task_rows.items() if row == 0]
            self.queue_table.removeRow(0)
            for task_id in removed_ids:
                self.task_rows.pop(task_id, None)
                self.task_context.pop(task_id, None)
            self.task_rows = {task_id: row - 1 for task_id, row in self.task_rows.items()}

    def _cancel_current(self) -> None:
        if self.current_task_id:
            self.transfer_queue.cancel(self.current_task_id)

    def _toggle_queue(self, visible: bool) -> None:
        self.queue_table.setVisible(visible)

    def _set_busy(self, text: str) -> None:
        self.progress.setRange(0, 0)
        self.progress_detail.setText(text)

    def _set_complete(self, text: str) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress_detail.setText(text)

    @staticmethod
    def _format_bytes(value: float) -> str:
        amount = float(value)
        for unit in ("B", "KiB", "MiB", "GiB"):
            if amount < 1024 or unit == "GiB":
                return f"{amount:.1f} {unit}"
            amount /= 1024
        return f"{amount:.1f} GiB"

    def close_transfers(self) -> None:
        self.transfer_queue.close()

    def cancel_all_transfers(self) -> None:
        for task_id in list(self.task_context):
            self.transfer_queue.cancel(task_id)

    def _set_focus_mode(self, enabled: bool) -> None:
        self._focus_mode = enabled
        self.browser_panel.setVisible(not enabled)
        self.metadata_panel.setVisible(not enabled)
        self.focus_button.setText("退出专注" if enabled else "专注模式")
        self.focus_mode_changed.emit(enabled)
