from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget, QWidget

from plotdas_client.cache import CacheManager
from plotdas_client.config import AppSettings, SettingsStore
from plotdas_client.models import PlotRequest
from plotdas_client.services import (
    AnnotationService,
    HistoryService,
    ImageService,
    JobService,
    PlotDasRemoteClient,
    PlotService,
    ProjectService,
)
from plotdas_client.transport import CancellationToken, ProgressCallback, SessionManager, SSHTransport

from .image_page import ImagePage
from .job_page import JobPage
from .plot_page import PlotPage
from .project_page import ProjectPage
from .settings_page import SettingsPage

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, app_root: Path, parent=None):
        super().__init__(parent)
        self.app_root = app_root
        self.settings_store = SettingsStore(app_root)
        self._session_lock = Lock()
        self._session_manager: SessionManager | None = None
        self._session_settings: AppSettings | None = None
        self._session_password = ""
        self.project_service = ProjectService(app_root / "config" / "projects.yaml")
        projects = self.project_service.list_projects()
        client_settings = self.settings_store.load()
        self.cache_manager = CacheManager(
            app_root / "cache", int(client_settings.cache_limit_gb * 1024**3)
        )

        annotations = AnnotationService(app_root / "data" / "annotations.json")
        self.setWindowTitle("DAScan")
        self.resize(1600, 950)
        self.navigation = QListWidget()
        self.navigation.setFixedWidth(170)
        self.navigation.setObjectName("navigation")
        self.stack = QStackedWidget()

        self.settings_page = SettingsPage(
            self.settings_store,
            self._test_connection,
            projects,
            annotations,
            self.cache_manager,
            self._clear_image_cache,
        )
        self.project_page = ProjectPage(self.project_service)
        self.plot_page = PlotPage(projects, self._preview, self.settings_page.password.text)
        self.plot_page.set_projects(projects, client_settings.active_project)
        self.job_page = JobPage(self._list_jobs, self.settings_page.password.text)
        self.image_page = ImagePage(
            projects,
            self._list_dates,
            self._list_images,
            self._fetch_image,
            self.settings_page.password.text,
            client_settings,
            annotations,
            HistoryService(app_root / "data" / "view_history.json", limit=100),
        )
        pages = [
            ("项目", self.project_page),
            ("绘图", self.plot_page),
            ("任务", self.job_page),
            ("图片", self.image_page),
            ("设置", self.settings_page),
        ]
        for label, page in pages:
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setSizeHint(
                item.sizeHint().expandedTo(self.navigation.sizeHint()).boundedTo(item.sizeHint())
            )
            self.navigation.addItem(item)
            self.stack.addWidget(page)
        self.navigation.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navigation.setCurrentRow(3)

        body = QWidget()
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.navigation)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(body)
        self.statusBar().showMessage("Server: Disconnected  ·  Project: xinjing")
        self.settings_page.connection_changed.connect(self._connection_changed)
        self.settings_page.settings_saved.connect(self._settings_saved)
        self.project_page.projects_changed.connect(self._projects_changed)
        self.image_page.focus_mode_changed.connect(lambda enabled: self.navigation.setVisible(not enabled))
        self.plot_page.preview_completed.connect(
            lambda path: self.statusBar().showMessage(f"Server: Connected  ·  Preview: {path}")
        )

    def _transport(self, settings: AppSettings | None = None, password: str = "") -> SSHTransport:
        return SSHTransport(settings or self.settings_store.load(), password)

    def _test_connection(self, settings: AppSettings, password: str):
        transport = self._transport(settings, password)
        try:
            LOGGER.info("Testing PlotDas connection to %s:%s", settings.server_host, settings.ssh_port)
            report = PlotDasRemoteClient(transport, settings).test_connection()
            LOGGER.info("PlotDas connection test succeeded")
            return report
        except Exception:
            LOGGER.exception("PlotDas connection test failed")
            raise
        finally:
            transport.close()

    def _preview(self, request: PlotRequest, password: str):
        settings = self.settings_store.load()
        transport = self._session(password)
        try:
            LOGGER.info(
                "Starting preview project=%s start=%s end=%s channels=%s:%s filter=%s dpi=%s",
                request.project,
                request.start_time,
                request.end_time,
                request.channel_start,
                request.channel_end,
                request.filter_type,
                request.dpi,
            )
            remote = PlotDasRemoteClient(transport, settings)
            images = ImageService(transport, self.cache_manager)
            result = PlotService(remote, images).preview(request)
            transport.invalidate(f"{settings.project_path}/output")
            LOGGER.info("Preview cached at %s", result.local_image_path)
            return result
        except Exception:
            LOGGER.exception("Preview failed")
            raise

    def _connection_changed(self, connected: bool) -> None:
        state = "Connected" if connected else "Disconnected"
        self.statusBar().showMessage(f"Server: {state}  ·  Project: xinjing")

    def _session(self, password: str) -> SessionManager:
        settings = self.settings_store.load()
        with self._session_lock:
            if (
                self._session_manager is None
                or self._session_settings != settings
                or self._session_password != password
            ):
                if self._session_manager is not None:
                    self._session_manager.close()
                self._session_manager = SessionManager(settings, password)
                self._session_settings = settings
                self._session_password = password
            return self._session_manager

    def _reset_session_manager(self) -> None:
        with self._session_lock:
            if self._session_manager is not None:
                self._session_manager.close()
            self._session_manager = None
            self._session_settings = None
            self._session_password = ""

    def _settings_saved(self, settings: AppSettings) -> None:
        self.cache_manager.set_limit_gb(settings.cache_limit_gb)
        for project in self.project_service.list_projects():
            self.cache_manager.enforce_limit(project.name)
        self.image_page.apply_settings(settings)
        self.plot_page.set_projects(self.project_service.list_projects(), settings.active_project)
        if self._session_settings is not None and self._session_settings != settings:
            self._reset_session_manager()

    def _projects_changed(self, projects) -> None:
        settings = self.settings_store.load()
        names = {project.name for project in projects}
        if settings.active_project not in names and projects:
            settings.active_project = projects[0].name
            settings.data_source = projects[0].server_output
            self.settings_store.save(settings)
        self.settings_page.set_projects(projects)
        self.plot_page.set_projects(projects, settings.active_project)
        self.image_page.set_projects(projects, settings.active_project)

    def _list_jobs(self, password: str):
        settings = self.settings_store.load()
        transport = self._session(password)
        remote = PlotDasRemoteClient(transport, settings)
        return JobService(remote).list_jobs()

    def _list_dates(self, project, password: str, force_refresh: bool = False):
        settings = self.settings_store.load()
        transport = self._session(password)
        if force_refresh:
            transport.invalidate(project.server_output)
        return PlotDasRemoteClient(transport, settings).list_dates(project.server_output)

    def _list_images(self, project, date: str, password: str):
        settings = self.settings_store.load()
        transport = self._session(password)
        return PlotDasRemoteClient(transport, settings).list_images(project.server_output, date)

    def _fetch_image(
        self,
        project,
        record: dict,
        password: str,
        progress_callback: ProgressCallback,
        cancel_token: CancellationToken,
    ):
        transport = self._session(password)
        images = ImageService(transport, self.cache_manager)
        return images.fetch_index_record(
            project.name,
            project.server_output,
            record,
            progress_callback,
            cancel_token,
        )

    def _clear_image_cache(self) -> int:
        if hasattr(self, "image_page"):
            self.image_page.cancel_all_transfers()
        return self.cache_manager.clear()

    def closeEvent(self, event) -> None:
        self.image_page.close_transfers()
        self._reset_session_manager()
        super().closeEvent(event)
