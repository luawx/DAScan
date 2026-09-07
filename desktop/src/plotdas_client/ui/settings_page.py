from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from plotdas_client.cache import CacheManager
from plotdas_client.config import AppSettings, SettingsStore
from plotdas_client.models import Project
from plotdas_client.services import AnnotationService, ConnectionReport

from .error_dialog import show_error
from .worker import Worker


class SettingsPage(QWidget):
    connection_changed = Signal(bool)
    settings_saved = Signal(object)

    def __init__(
        self,
        store: SettingsStore,
        connection_test: Callable[[AppSettings, str], ConnectionReport],
        projects: list[Project],
        annotations: AnnotationService,
        cache_manager: CacheManager,
        parent=None,
    ):
        super().__init__(parent)
        self.store = store
        self.connection_test = connection_test
        self.projects = {project.name: project for project in projects}
        self.annotations = annotations
        self.cache_manager = cache_manager
        self.pool = QThreadPool.globalInstance()
        settings = store.load()

        title = QLabel("设置")
        title.setObjectName("pageTitle")
        self.host = QLineEdit(settings.server_host)
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(settings.ssh_port)
        self.username = QLineEdit(settings.username)
        self.project_path = QLineEdit(settings.project_path)
        self.cli_command = QLineEdit(settings.cli_command)
        self.key_path = QLineEdit(settings.private_key_path)
        self.key_path.setPlaceholderText("留空时使用 SSH Agent / 默认密钥")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("仅保存在内存中，不写入配置或日志")
        self.connect_timeout = QSpinBox()
        self.connect_timeout.setRange(3, 120)
        self.connect_timeout.setValue(settings.connect_timeout)
        self.connect_timeout.setSuffix(" 秒")
        self.keepalive_interval = QSpinBox()
        self.keepalive_interval.setRange(0, 600)
        self.keepalive_interval.setValue(settings.keepalive_interval)
        self.keepalive_interval.setSuffix(" 秒")
        self.keepalive_interval.setSpecialValueText("关闭")
        self.reconnect_attempts = QSpinBox()
        self.reconnect_attempts.setRange(0, 10)
        self.reconnect_attempts.setValue(settings.reconnect_attempts)
        self.max_background_transfers = QSpinBox()
        self.max_background_transfers.setRange(1, 8)
        self.max_background_transfers.setValue(settings.max_background_transfers)
        self.prefetch_count = QSpinBox()
        self.prefetch_count.setRange(0, 20)
        self.prefetch_count.setValue(settings.prefetch_count)
        self.prefetch_count.setSuffix(" 张")
        self.show_transfer_queue = QCheckBox("进入图片页时显示传输队列")
        self.show_transfer_queue.setChecked(settings.show_transfer_queue)
        self.cache_limit_gb = QDoubleSpinBox()
        self.cache_limit_gb.setRange(0.1, 1000.0)
        self.cache_limit_gb.setDecimals(1)
        self.cache_limit_gb.setSingleStep(0.5)
        self.cache_limit_gb.setSuffix(" GB / 项目")
        self.cache_limit_gb.setValue(settings.cache_limit_gb)
        self.active_project = QComboBox()
        self.active_project.addItems(self.projects)
        self.active_project.setCurrentText(settings.active_project)
        self.data_source = QLineEdit(settings.data_source)
        self.data_source.setPlaceholderText("服务器图片输出目录，例如 …/output/xinjing")
        self.active_project.currentTextChanged.connect(self._project_changed)
        self.metadata_sections: dict[str, QCheckBox] = {}
        for section in ("基本信息", "数据范围", "处理参数", "文件与版本", "其他信息"):
            checkbox = QCheckBox(section)
            checkbox.setChecked(section in settings.metadata_visible_sections)
            self.metadata_sections[section] = checkbox

        form = QFormLayout()
        form.addRow("Server Host", self.host)
        form.addRow("SSH Port", self.port)
        form.addRow("Username", self.username)
        form.addRow("PlotDas Project Path", self.project_path)
        form.addRow("PlotDas CLI", self.cli_command)
        form.addRow("SSH Key", self.key_path)
        form.addRow("Password", self.password)
        group = QGroupBox("服务器连接")
        group.setLayout(form)

        connection_form = QFormLayout()
        connection_form.addRow("连接超时", self.connect_timeout)
        connection_form.addRow("Keepalive", self.keepalive_interval)
        connection_form.addRow("自动重连次数", self.reconnect_attempts)
        connection_group = QGroupBox("连接策略")
        connection_group.setLayout(connection_form)

        behavior_form = QFormLayout()
        behavior_form.addRow("后台传输并发", self.max_background_transfers)
        behavior_form.addRow("前后缓存 K", self.prefetch_count)
        behavior_form.addRow("队列显示", self.show_transfer_queue)
        behavior_form.addRow("当前项目", self.active_project)
        behavior_form.addRow("图片数据源", self.data_source)
        metadata_options = QWidget()
        metadata_options.setObjectName("metadataOptions")
        metadata_grid = QGridLayout(metadata_options)
        metadata_grid.setContentsMargins(0, 0, 0, 0)
        metadata_grid.setHorizontalSpacing(16)
        metadata_grid.setVerticalSpacing(4)
        for index, checkbox in enumerate(self.metadata_sections.values()):
            metadata_grid.addWidget(
                checkbox,
                index // 3,
                index % 3,
                alignment=Qt.AlignmentFlag.AlignLeft,
            )
        metadata_grid.setColumnStretch(3, 1)
        behavior_form.addRow("详情展示内容", metadata_options)
        behavior_group = QGroupBox("传输与图片浏览")
        behavior_group.setLayout(behavior_form)

        self.clear_cache_button = QPushButton("一键清空全部缓存")
        self.clear_cache_button.clicked.connect(self._clear_cache)
        self.export_button = QPushButton("一键导出收藏")
        self.export_button.clicked.connect(self._export_favorites)
        storage_form = QFormLayout()
        storage_form.addRow("磁盘缓存上限", self.cache_limit_gb)
        storage_actions = QHBoxLayout()
        storage_actions.addWidget(self.clear_cache_button)
        storage_actions.addWidget(self.export_button)
        storage_actions.addStretch()
        storage_form.addRow("缓存与收藏", storage_actions)
        storage_group = QGroupBox("本地存储")
        storage_group.setLayout(storage_form)

        self.save_button = QPushButton("保存设置")
        self.save_button.clicked.connect(self._save)
        self.test_button = QPushButton("测试连接")
        self.test_button.clicked.connect(self._test)
        self.status = QLabel("尚未测试")
        actions = QHBoxLayout()
        actions.addWidget(self.save_button)
        actions.addWidget(self.test_button)
        actions.addWidget(self.status, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        settings_grid = QGridLayout()
        settings_grid.setHorizontalSpacing(12)
        settings_grid.setVerticalSpacing(10)
        settings_grid.addWidget(group, 0, 0)
        settings_grid.addWidget(connection_group, 0, 1)
        settings_grid.addWidget(behavior_group, 1, 0)
        settings_grid.addWidget(storage_group, 1, 1)
        settings_grid.setColumnStretch(0, 3)
        settings_grid.setColumnStretch(1, 2)
        layout.addLayout(settings_grid)
        layout.addLayout(actions)
        layout.addStretch()

    def current_settings(self) -> AppSettings:
        return AppSettings(
            server_host=self.host.text().strip(),
            ssh_port=self.port.value(),
            username=self.username.text().strip(),
            project_path=self.project_path.text().strip(),
            cli_command=self.cli_command.text().strip(),
            private_key_path=self.key_path.text().strip(),
            connect_timeout=self.connect_timeout.value(),
            keepalive_interval=self.keepalive_interval.value(),
            reconnect_attempts=self.reconnect_attempts.value(),
            max_background_transfers=self.max_background_transfers.value(),
            prefetch_count=self.prefetch_count.value(),
            show_transfer_queue=self.show_transfer_queue.isChecked(),
            cache_limit_gb=self.cache_limit_gb.value(),
            active_project=self.active_project.currentText(),
            data_source=self.data_source.text().strip(),
            metadata_visible_sections=[
                name for name, checkbox in self.metadata_sections.items() if checkbox.isChecked()
            ],
        )

    def _export_favorites(self) -> None:
        destination = QFileDialog.getExistingDirectory(self, "选择收藏导出目录")
        if not destination:
            return
        files = self.annotations.export_favorites(Path(destination))
        self.status.setText(f"已导出 {len(files)} 个收藏分组文件")
        self.status.setStyleSheet("color: #16803c")

    def _clear_cache(self) -> None:
        removed = self.cache_manager.clear()
        self.status.setText(f"已清空本地缓存，共删除 {removed} 个文件")
        self.status.setStyleSheet("color: #16803c")

    def set_projects(self, projects: list[Project]) -> None:
        current = self.active_project.currentText()
        self.projects = {project.name: project for project in projects}
        self.active_project.blockSignals(True)
        self.active_project.clear()
        self.active_project.addItems(self.projects)
        if current in self.projects:
            self.active_project.setCurrentText(current)
        elif projects:
            self.active_project.setCurrentText(projects[0].name)
            self.data_source.setText(projects[0].server_output)
        self.active_project.blockSignals(False)

    def _project_changed(self, name: str) -> None:
        project = self.projects.get(name)
        if project is not None:
            self.data_source.setText(project.server_output)

    def _save(self) -> None:
        settings = self.current_settings()
        self.store.save(settings)
        self.settings_saved.emit(settings)
        self.status.setText("设置已保存")
        self.status.setStyleSheet("color: #16803c")

    def _test(self) -> None:
        settings = self.current_settings()
        password = self.password.text()
        self.store.save(settings)
        self.settings_saved.emit(settings)
        self.test_button.setEnabled(False)
        self.status.setText("正在连接…")
        worker = Worker(lambda: self.connection_test(settings, password))
        worker.signals.succeeded.connect(self._connected)
        worker.signals.failed.connect(self._failed)
        worker.signals.finished.connect(lambda: self.test_button.setEnabled(True))
        self.pool.start(worker)

    def _connected(self, report: ConnectionReport) -> None:
        self.status.setText("服务器连接成功 · PlotDas 目录存在 · CLI 可用")
        self.status.setStyleSheet("color: #16803c")
        self.connection_changed.emit(True)

    def _failed(self, message: str, details: str) -> None:
        self.status.setText(message)
        self.status.setStyleSheet("color: #b42318")
        self.connection_changed.emit(False)
        show_error(self, message, details)
