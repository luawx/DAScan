from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHeaderView, QTreeWidget, QTreeWidgetItem

FIELD_LABELS = {
    "job_id": "任务 ID",
    "project": "项目",
    "status": "状态",
    "completed": "已完成",
    "total": "任务总数",
    "failed": "失败数",
    "pid": "进程 PID",
    "current_window": "当前时间窗口",
    "request": "任务参数",
    "error": "错误信息",
    "cancel_requested": "已请求停止",
    "started_at": "开始运行时间",
    "finished_at": "结束时间",
    "updated_at": "更新时间",
    "requested_start_time": "请求开始时间",
    "requested_end_time": "请求结束时间",
    "start_time": "实际开始时间",
    "end_time": "实际结束时间",
    "created_at": "创建时间",
    "timezone": "时区",
    "channel_start": "起始通道",
    "channel_end": "结束通道",
    "channel_count": "通道数",
    "sampling_rate": "采样率",
    "sample_rate": "采样率",
    "sample_count": "采样点数",
    "samples": "采样点数",
    "channel_spacing": "通道间距",
    "unit": "数据单位",
    "filter_type": "滤波类型",
    "lowcut": "低截止频率",
    "highcut": "高截止频率",
    "filter_order": "滤波阶数",
    "order": "滤波阶数",
    "scale_mode": "缩放方式",
    "percentile": "百分位",
    "absolute_scale": "绝对幅值",
    "std_factor": "标准差倍数",
    "dpi": "图像 DPI",
    "format": "图像格式",
    "image_path": "图片文件",
    "metadata_path": "Metadata 文件",
    "plugin": "插件",
    "plugin_name": "插件名称",
    "plugin_version": "插件版本",
    "schema_version": "Schema 版本",
    "source_file": "来源文件",
    "source_files": "来源文件",
    "input_root": "输入数据目录",
    "output_root": "输出数据目录",
    "window_length": "窗口长度",
}

STATUS_LABELS = {
    "success": "成功",
    "completed": "已完成",
    "failed": "失败",
    "pending": "等待中",
    "running": "处理中",
    "cancelled": "已取消",
}

FILTER_LABELS = {
    "none": "不滤波",
    "bandpass": "带通滤波",
    "lowpass": "低通滤波",
    "highpass": "高通滤波",
}

SECTIONS = (
    (
        "基本信息",
        (
            "project",
            "status",
            "requested_start_time",
            "requested_end_time",
            "start_time",
            "end_time",
            "timezone",
            "created_at",
        ),
    ),
    (
        "数据范围",
        (
            "channel_start",
            "channel_end",
            "channel_count",
            "sampling_rate",
            "sample_rate",
            "sample_count",
            "samples",
            "channel_spacing",
            "unit",
        ),
    ),
    (
        "处理参数",
        (
            "filter_type",
            "lowcut",
            "highcut",
            "filter_order",
            "order",
            "scale_mode",
            "percentile",
            "absolute_scale",
            "std_factor",
            "dpi",
            "format",
        ),
    ),
    (
        "文件与版本",
        (
            "source_file",
            "source_files",
            "image_path",
            "metadata_path",
            "plugin",
            "plugin_name",
            "plugin_version",
            "schema_version",
        ),
    ),
)


class MetadataWidget(QTreeWidget):
    """Present sidecar metadata as grouped, localized fields instead of raw JSON."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(2)
        self.setHeaderLabels(["字段", "值"])
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(False)
        self.setWordWrap(True)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.setToolTip("完整路径可将鼠标停留在对应值上查看")

    def set_visible_sections(self, sections: list[str]) -> None:
        self._visible_sections = set(sections)

    def set_metadata(self, metadata: dict[str, Any] | None) -> None:
        self.clear()
        if not metadata:
            placeholder = QTreeWidgetItem(["暂无 Metadata", "—"])
            self.addTopLevelItem(placeholder)
            return

        consumed: set[str] = set()
        for section_name, keys in SECTIONS:
            if hasattr(self, "_visible_sections") and section_name not in self._visible_sections:
                consumed.update(key for key in keys if key in metadata)
                continue
            values = [(key, metadata[key]) for key in keys if key in metadata]
            if not values:
                continue
            section = self._section(section_name)
            for key, value in values:
                consumed.add(key)
                self._add_value(section, key, value)

        extras = [(key, value) for key, value in metadata.items() if key not in consumed]
        if extras and (not hasattr(self, "_visible_sections") or "其他信息" in self._visible_sections):
            section = self._section("其他信息")
            for key, value in extras:
                self._add_value(section, key, value)

        duration = self._duration(metadata)
        if duration is not None and (
            not hasattr(self, "_visible_sections") or "基本信息" in self._visible_sections
        ):
            basic_sections = self.findItems("基本信息", Qt.MatchFlag.MatchExactly, 0)
            parent = basic_sections[0] if basic_sections else self._section("基本信息")
            parent.addChild(QTreeWidgetItem(["持续时间", self._format_duration(duration)]))
        self.expandAll()

    def _section(self, title: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([title, ""])
        font = QFont(item.font(0))
        font.setBold(True)
        item.setFont(0, font)
        self.addTopLevelItem(item)
        return item

    def _add_value(self, parent: QTreeWidgetItem, key: str, value: Any) -> None:
        label = FIELD_LABELS.get(key, key.replace("_", " ").strip().title())
        if isinstance(value, dict):
            group = QTreeWidgetItem([label, ""])
            parent.addChild(group)
            for child_key, child_value in value.items():
                self._add_value(group, str(child_key), child_value)
            return
        if isinstance(value, (list, tuple)):
            group = QTreeWidgetItem([label, f"{len(value)} 项"])
            parent.addChild(group)
            for index, child_value in enumerate(value, start=1):
                child = QTreeWidgetItem([f"第 {index} 项", self._format_value(key, child_value)])
                self._set_path_tooltip(child, child_value)
                group.addChild(child)
            return
        item = QTreeWidgetItem([label, self._format_value(key, value)])
        self._set_path_tooltip(item, value)
        parent.addChild(item)

    @staticmethod
    def _set_path_tooltip(item: QTreeWidgetItem, value: Any) -> None:
        if isinstance(value, str) and ("/" in value or "\\" in value):
            item.setToolTip(1, value)

    @staticmethod
    def _format_value(key: str, value: Any) -> str:
        if value is None or value == "":
            return "—"
        if isinstance(value, bool):
            return "是" if value else "否"
        if key == "status":
            return STATUS_LABELS.get(str(value).lower(), str(value))
        if key == "filter_type":
            return FILTER_LABELS.get(str(value).lower(), str(value))
        if key in {
            "requested_start_time",
            "requested_end_time",
            "start_time",
            "end_time",
            "created_at",
        }:
            return str(value).replace("T", " ")
        if key in {"sampling_rate", "sample_rate", "lowcut", "highcut"}:
            return f"{value} Hz"
        if key == "dpi":
            return f"{value} dpi"
        if key == "percentile":
            return f"{value}%"
        if key == "format":
            return str(value).upper()
        if key in {"sample_count", "samples", "channel_count"}:
            try:
                return f"{int(value):,}"
            except (TypeError, ValueError):
                return str(value)
        if key in {"image_path", "metadata_path", "source_file", "source_files"}:
            return str(value)
        return str(value)

    @staticmethod
    def _duration(metadata: dict[str, Any]) -> float | None:
        start = metadata.get("requested_start_time", metadata.get("start_time"))
        end = metadata.get("requested_end_time", metadata.get("end_time"))
        if not start or not end:
            return None
        try:
            start_time = datetime.fromisoformat(str(start))
            end_time = datetime.fromisoformat(str(end))
            return max(0.0, (end_time - start_time).total_seconds())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:g} 秒"
        minutes, remaining = divmod(seconds, 60)
        if minutes < 60:
            return f"{int(minutes)} 分 {remaining:g} 秒"
        hours, minutes = divmod(minutes, 60)
        return f"{int(hours)} 小时 {int(minutes)} 分"
