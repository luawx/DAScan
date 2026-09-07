from __future__ import annotations

import fcntl
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import PlotRequest


def output_paths(request: PlotRequest) -> tuple[Path, Path, Path]:
    if request.output_path is not None:
        image = request.output_path.resolve()
        metadata = image.with_suffix(".json")
        index = image.parent / "index.json"
        return image, metadata, index
    day = request.start_time.strftime("%Y%m%d")
    start = request.start_time.strftime("%H%M%S_%f")
    end = request.end_time.strftime("%H%M%S_%f")
    stem = f"{start}_{end}_ch{request.channel_start}_{request.channel_end}"
    root = request.output_root / request.project / day
    return root / "images" / f"{stem}.{request.image_format}", root / "metadata" / f"{stem}.json", root / "index.json"


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def update_index(index_path: Path, record: dict[str, Any]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = index_path.with_suffix(".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        existing: dict[str, Any] = {"schema_version": 1, "records": []}
        if index_path.exists():
            try:
                existing = json.loads(index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = {"schema_version": 1, "records": []}
        records = [item for item in existing.get("records", []) if item.get("metadata_path") != record.get("metadata_path")]
        records.append(record)
        records.sort(key=lambda item: (item.get("start_time", ""), item.get("channel_start", 0)))
        atomic_write_json(index_path, {"schema_version": 1, "project": record.get("project"), "records": records})
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def request_metadata(request: PlotRequest, plugin_name: str, plugin_version: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "project": request.project,
        "plugin": {"name": plugin_name, "version": plugin_version},
        "requested_start_time": request.start_time.isoformat(),
        "requested_end_time": request.end_time.isoformat(),
        "timezone": request.timezone,
        "channel_start": request.channel_start,
        "channel_end": request.channel_end,
        "filter": {"type": request.filter.type, "lowcut": request.filter.lowcut, "highcut": request.filter.highcut, "order": request.filter.order},
        "scale": {"mode": request.scale.mode, "percentile": request.scale.percentile, "absolute": request.scale.absolute, "std_factor": request.scale.std_factor},
        "dpi": request.dpi,
        "format": request.image_format,
    }


def write_failure_metadata(request: PlotRequest, plugin_name: str, plugin_version: str, error: Exception) -> Path:
    image, metadata, index = output_paths(request)
    payload = request_metadata(request, plugin_name, plugin_version)
    payload.update({
        "status": "failed",
        "error": {"type": type(error).__name__, "message": str(error)},
        "image_path": None,
        "metadata_path": str(metadata),
        "created_at": datetime.now().astimezone().isoformat(),
    })
    atomic_write_json(metadata, payload)
    update_index(index, payload)
    return metadata

