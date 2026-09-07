from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Job:
    job_id: str
    project: str
    status: str
    completed: int = 0
    total: int = 0
    failed: int = 0
    pid: int | None = None
    created_at: str | None = None
    current_window: Any = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        request = data.get("request") or {}
        return cls(
            job_id=str(data.get("job_id", "")),
            project=str(request.get("project", data.get("project", ""))),
            status=str(data.get("status", "unknown")),
            completed=int(data.get("completed", 0)),
            total=int(data.get("total", 0)),
            failed=int(data.get("failed", 0)),
            pid=data.get("pid"),
            created_at=data.get("created_at"),
            current_window=data.get("current_window"),
            raw=data,
        )
