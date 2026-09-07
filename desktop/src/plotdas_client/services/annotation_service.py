from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Annotation:
    project: str
    image_path: str
    favorite: bool = False
    note: str = ""
    tags: list[str] | None = None
    group: str = "默认分组"
    event_start_time: str = ""
    event_end_time: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []


class AnnotationService:
    """Local-only favorites and notes, keyed by project and remote image path."""

    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def _key(project: str, image_path: str) -> str:
        return f"{project}\n{image_path}"

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}

    def _save(self, payload: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def get(self, project: str, image_path: str) -> Annotation:
        data = self._load().get(self._key(project, image_path))
        return Annotation(**data) if data else Annotation(project, image_path)

    def save(self, annotation: Annotation) -> Annotation:
        payload = self._load()
        key = self._key(annotation.project, annotation.image_path)
        existing = payload.get(key, {})
        now = datetime.now().astimezone().isoformat()
        annotation.created_at = str(existing.get("created_at") or annotation.created_at or now)
        annotation.updated_at = now
        if annotation.favorite or annotation.note.strip() or annotation.tags:
            payload[key] = asdict(annotation)
        else:
            payload.pop(key, None)
        self._save(payload)
        return annotation

    def list_favorites(self, project: str | None = None) -> list[Annotation]:
        annotations = [Annotation(**item) for item in self._load().values()]
        return sorted(
            (item for item in annotations if item.favorite and (project is None or item.project == project)),
            key=lambda item: item.updated_at,
            reverse=True,
        )

    def export_favorites(self, root: Path) -> list[Path]:
        """按项目/收藏分组导出事件起止时间，返回生成的 txt 文件。"""
        grouped: dict[tuple[str, str], list[Annotation]] = {}
        for item in self.list_favorites():
            grouped.setdefault((item.project, item.group.strip() or "默认分组"), []).append(item)
        exported: list[Path] = []
        for (project, group), items in grouped.items():
            project_dir = root / self._safe_name(project)
            project_dir.mkdir(parents=True, exist_ok=True)
            target = project_dir / f"{self._safe_name(group)}.txt"
            lines = [
                f"{item.event_start_time}\t{item.event_end_time}"
                for item in items
                if item.event_start_time or item.event_end_time
            ]
            target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            exported.append(target)
        return exported

    @staticmethod
    def _safe_name(value: str) -> str:
        cleaned = "".join("_" if char in '<>:"/\\|?*' else char for char in value).strip(" .")
        return cleaned or "未命名"
