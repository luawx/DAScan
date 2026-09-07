from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath


@dataclass(frozen=True, slots=True)
class ViewHistoryEntry:
    project: str
    date: str
    image_path: str
    viewed_at: str
    label: str = ""

    @property
    def display_label(self) -> str:
        name = PurePosixPath(self.image_path).name
        return self.label or f"{self.project} · {self.date} · {name}"


class HistoryService:
    def __init__(self, path: Path, limit: int = 100):
        self.path = path
        self.limit = limit

    def list_recent(self) -> list[ViewHistoryEntry]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        entries = payload.get("entries", []) if isinstance(payload, dict) else []
        return [ViewHistoryEntry(**entry) for entry in entries]

    def last_viewed(self) -> ViewHistoryEntry | None:
        entries = self.list_recent()
        return entries[0] if entries else None

    def record(self, project: str, date: str, image_path: str, label: str = "") -> None:
        entry = ViewHistoryEntry(
            project=project,
            date=date,
            image_path=image_path,
            viewed_at=datetime.now().astimezone().isoformat(),
            label=label,
        )
        entries = [
            item
            for item in self.list_recent()
            if not (item.project == project and item.image_path == image_path)
        ]
        entries.insert(0, entry)
        payload = {"entries": [asdict(item) for item in entries[: self.limit]]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
