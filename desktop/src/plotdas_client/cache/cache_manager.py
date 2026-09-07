from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import Any, Iterable


class CacheManager:
    """Project-scoped disk cache with a configurable LRU-like size limit."""

    def __init__(self, root: Path, max_bytes_per_project: int = 1024**3):
        self.root = root
        self.max_bytes_per_project = max(1, int(max_bytes_per_project))
        self._lock = Lock()

    def set_limit_gb(self, limit_gb: float) -> None:
        self.max_bytes_per_project = max(1, int(limit_gb * 1024**3))

    @staticmethod
    def _safe_component(value: str) -> str:
        return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)

    def project_root(self, project: str) -> Path:
        return self.root / self._safe_component(project)

    def paths_for(self, project: str, remote_image_path: str) -> tuple[Path, Path]:
        remote = PurePosixPath(remote_image_path)
        date = next(
            (part for part in reversed(remote.parts) if len(part) == 8 and part.isdigit()),
            "unknown-date",
        )
        project_dir = self.project_root(project) / date
        digest = hashlib.sha256(remote_image_path.encode("utf-8")).hexdigest()[:12]
        image = project_dir / "images" / f"{remote.stem}_{digest}{remote.suffix or '.png'}"
        metadata = project_dir / "metadata" / f"{remote.stem}_{digest}.json"
        return image, metadata

    def write_metadata(self, path: Path, metadata: dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return path

    def read_metadata(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        path.touch(exist_ok=True)
        return json.loads(path.read_text(encoding="utf-8"))

    def enforce_limit(self, project: str, protected: Iterable[Path] = ()) -> int:
        """Remove oldest files until one project's cache fits; return removed count."""
        project_root = self.project_root(project)
        if not project_root.exists():
            return 0
        protected_paths = {path.resolve() for path in protected}
        with self._lock:
            files = [path for path in project_root.rglob("*") if path.is_file()]
            total = sum(path.stat().st_size for path in files)
            removed = 0
            for path in sorted(files, key=lambda item: item.stat().st_mtime_ns):
                if total <= self.max_bytes_per_project:
                    break
                if path.resolve() in protected_paths:
                    continue
                size = path.stat().st_size
                path.unlink(missing_ok=True)
                total -= size
                removed += 1
            self._remove_empty_directories(project_root)
            return removed

    def clear(self, project: str | None = None) -> int:
        """Clear all cached files, or only one project's files."""
        target = self.project_root(project) if project else self.root
        if not target.exists():
            return 0
        with self._lock:
            files = [path for path in target.rglob("*") if path.is_file()]
            for path in files:
                path.unlink(missing_ok=True)
            self._remove_empty_directories(target)
            return len(files)

    @staticmethod
    def _remove_empty_directories(root: Path) -> None:
        directories = sorted(
            (path for path in root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        )
        for directory in directories:
            try:
                directory.rmdir()
            except OSError:
                pass
        try:
            root.rmdir()
        except OSError:
            pass
