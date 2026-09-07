from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from plotdas_client.models import Project
from plotdas_client.services import ProjectService

from .error_dialog import show_error


class ProjectPage(QWidget):
    projects_changed = Signal(object)

    def __init__(self, service: ProjectService, parent=None):
        super().__init__(parent)
        self.service = service
        self.projects: list[Project] = []
        self._selected_name: str | None = None

        title = QLabel("项目管理")
        title.setObjectName("pageTitle")
        self.listing = QListWidget()
        self.listing.currentRowChanged.connect(self._select)

        self.name = QLineEdit()
        self.server_input = QLineEdit()
        self.server_output = QLineEdit()
        self.plugin = QLineEdit()
        self.description = QTextEdit()
        self.description.setMaximumHeight(100)
        form = QFormLayout()
        form.addRow("项目名称", self.name)
        form.addRow("服务器输入目录", self.server_input)
        form.addRow("服务器输出目录", self.server_output)
        form.addRow("插件", self.plugin)
        form.addRow("说明", self.description)
        group = QGroupBox("项目配置")
        group.setLayout(form)

        new_button = QPushButton("新建")
        new_button.clicked.connect(self._new)
        save_button = QPushButton("保存")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._save)
        delete_button = QPushButton("删除")
        delete_button.clicked.connect(self._delete)
        actions = QHBoxLayout()
        actions.addWidget(new_button)
        actions.addWidget(save_button)
        actions.addWidget(delete_button)
        actions.addStretch()
        self.status = QLabel()

        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.addWidget(group)
        editor_layout.addLayout(actions)
        editor_layout.addWidget(self.status)
        editor_layout.addStretch()
        splitter = QSplitter()
        splitter.addWidget(self.listing)
        splitter.addWidget(editor)
        splitter.setSizes([300, 900])

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(QLabel("项目保存在 config/projects.yaml；保存后其他页面立即更新。"))
        layout.addWidget(splitter, 1)
        self.reload()

    def reload(self) -> None:
        self.projects = self.service.list_projects()
        self.listing.clear()
        for project in self.projects:
            suffix = f" · {project.description}" if project.description else ""
            self.listing.addItem(f"{project.name}{suffix}")
        if self.projects:
            self.listing.setCurrentRow(0)
        else:
            self._new()

    def _select(self, row: int) -> None:
        if not 0 <= row < len(self.projects):
            return
        project = self.projects[row]
        self._selected_name = project.name
        self.name.setText(project.name)
        self.server_input.setText(project.server_input)
        self.server_output.setText(project.server_output)
        self.plugin.setText(project.plugin)
        self.description.setPlainText(project.description)

    def _new(self) -> None:
        self.listing.clearSelection()
        self.listing.setCurrentRow(-1)
        self._selected_name = None
        for editor in (self.name, self.server_input, self.server_output, self.plugin):
            editor.clear()
        self.description.clear()
        self.name.setFocus()
        self.status.setText("填写后点击保存即可新建项目")

    def _save(self) -> None:
        project = Project(
            name=self.name.text().strip(),
            server_input=self.server_input.text().strip(),
            server_output=self.server_output.text().strip(),
            plugin=self.plugin.text().strip(),
            description=self.description.toPlainText().strip(),
        )
        if not all((project.name, project.server_input, project.server_output, project.plugin)):
            show_error(self, "项目名称、输入目录、输出目录和插件均不能为空")
            return
        try:
            projects = self.service.upsert(project, self._selected_name)
        except (OSError, ValueError) as exc:
            show_error(self, f"项目保存失败: {exc}")
            return
        self.reload()
        row = next(i for i, item in enumerate(projects) if item.name == project.name)
        self.listing.setCurrentRow(row)
        self.status.setText(f"项目 {project.name} 已保存")
        self.projects_changed.emit(projects)

    def _delete(self) -> None:
        if not self._selected_name:
            return
        answer = QMessageBox.question(
            self,
            "删除项目",
            f"确定从客户端配置中删除项目 {self._selected_name}？\n不会删除服务器数据。",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        name = self._selected_name
        try:
            projects = self.service.delete(name)
        except OSError as exc:
            show_error(self, f"项目删除失败: {exc}")
            return
        self.reload()
        self.status.setText(f"项目 {name} 已从客户端配置删除；服务器数据未修改")
        self.projects_changed.emit(projects)
