from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ImageRecord:
    project: str
    remote_image_path: str
    remote_metadata_path: str | None = None
    local_image_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
