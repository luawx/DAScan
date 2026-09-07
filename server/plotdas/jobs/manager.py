from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

import psutil

from ..exceptions import JobError
from ..models import FilterConfig, PlotRequest, ScaleConfig
from ..output import atomic_write_json
from ..timeutil import parse_datetime


def request_to_dict(request: PlotRequest) -> dict[str, Any]:
    return {
        "project": request.project,
        "input_root": str(request.input_root),
        "output_root": str(request.output_root),
        "start_time": request.start_time.isoformat(),
        "end_time": request.end_time.isoformat(),
        "channel_start": request.channel_start,
        "channel_end": request.channel_end,
        "filter": vars(request.filter),
        "scale": vars(request.scale),
        "dpi": request.dpi,
        "image_format": request.image_format,
        "figsize": list(request.figsize),
        "max_time_pixels": request.max_time_pixels,
        "timezone": request.timezone,
        "overwrite": request.overwrite,
        "gap_tolerance_samples": request.gap_tolerance_samples,
        "channel_block_size": request.channel_block_size,
        "memory_limit_mb": request.memory_limit_mb,
        "temp_root": str(request.temp_root),
    }


def request_from_dict(payload: dict[str, Any]) -> PlotRequest:
    data = dict(payload)
    data["input_root"] = Path(data["input_root"])
    data["output_root"] = Path(data["output_root"])
    data["temp_root"] = Path(data.get("temp_root", "/tmp"))
    data["start_time"] = parse_datetime(data["start_time"], data.get("timezone", "Asia/Shanghai"))
    data["end_time"] = parse_datetime(data["end_time"], data.get("timezone", "Asia/Shanghai"))
    data["filter"] = FilterConfig(**data.get("filter", {}))
    data["scale"] = ScaleConfig(**data.get("scale", {}))
    data["figsize"] = tuple(data.get("figsize", [14.0, 8.0]))
    return PlotRequest(**data)


def split_windows(start: datetime, end: datetime, seconds: float) -> Iterator[tuple[datetime, datetime]]:
    if seconds <= 0:
        raise JobError("window_length must be positive")
    current = start
    step = timedelta(seconds=seconds)
    while current < end:
        following = min(current + step, end)
        yield current, following
        current = following


class JobManager:
    def __init__(self, jobs_root: Path):
        self.jobs_root = jobs_root.resolve()
        self.jobs_root.mkdir(parents=True, exist_ok=True)

    def _directory(self, job_id: str) -> Path:
        if not job_id.startswith("job_") or any(char in job_id for char in "/\\"):
            raise JobError(f"Invalid job id: {job_id}")
        return self.jobs_root / job_id

    def _path(self, job_id: str) -> Path:
        return self._directory(job_id) / "job.json"

    def get_job(self, job_id: str) -> dict[str, Any]:
        path = self._path(job_id)
        if not path.exists():
            raise JobError(f"Job not found: {job_id}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise JobError(f"Cannot read job {job_id}: {exc}") from exc

    def save_job(self, job: dict[str, Any]) -> None:
        job["updated_at"] = datetime.now().astimezone().isoformat()
        atomic_write_json(self._path(job["job_id"]), job)

    def create_job(self, request: PlotRequest, window_length: float) -> dict[str, Any]:
        request.validate()
        windows = list(split_windows(request.start_time, request.end_time, window_length))
        return self.create_job_from_windows(request, windows, window_length, continue_on_error=False)

    def create_job_from_windows(
        self,
        request: PlotRequest,
        windows: list[tuple[datetime, datetime]],
        window_length: float,
        *,
        continue_on_error: bool,
        discovery: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request.validate()
        if not windows:
            raise JobError("No readable windows were discovered")
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        job_id = f"job_{stamp}_{uuid.uuid4().hex[:8]}"
        directory = self._directory(job_id)
        directory.mkdir(parents=True, exist_ok=False)
        window_payload = {
            "schema_version": 1,
            "windows": [{"start": start.isoformat(), "end": end.isoformat()} for start, end in windows],
            "discovery": discovery or {},
        }
        atomic_write_json(directory / "windows.json", window_payload)
        now = datetime.now().astimezone().isoformat()
        job = {
            "schema_version": 1,
            "job_id": job_id,
            "project": request.project,
            "status": "pending",
            "pid": None,
            "request": request_to_dict(request),
            "window_length": window_length,
            "window_manifest": "windows.json",
            "continue_on_error": continue_on_error,
            "total": len(windows),
            "completed": 0,
            "failed": 0,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "updated_at": now,
            "current_window": None,
            "cancel_requested": False,
            "error": None,
        }
        self.save_job(job)
        return job

    def load_windows(self, job: dict[str, Any]) -> list[tuple[datetime, datetime]]:
        manifest = job.get("window_manifest")
        if not manifest:
            request = request_from_dict(job["request"])
            return list(split_windows(request.start_time, request.end_time, float(job["window_length"])))
        path = self._directory(job["job_id"]) / manifest
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            timezone = job["request"].get("timezone", "Asia/Shanghai")
            return [(parse_datetime(item["start"], timezone), parse_datetime(item["end"], timezone)) for item in payload["windows"]]
        except (OSError, KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
            raise JobError(f"Cannot read window manifest for {job['job_id']}: {exc}") from exc

    def start_job(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        if job["status"] != "pending":
            raise JobError(f"Job {job_id} is {job['status']}; only pending jobs can start")
        log_path = self._directory(job_id) / "log.txt"
        command = [sys.executable, "-m", "plotdas.jobs.worker", "--jobs-root", str(self.jobs_root), job_id]
        with log_path.open("ab", buffering=0) as log:
            process = subprocess.Popen(command, cwd=Path(__file__).resolve().parents[2], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
        job["pid"] = process.pid
        job["status"] = "running"
        job["started_at"] = datetime.now().astimezone().isoformat()
        self.save_job(job)
        return job

    def list_jobs(self) -> list[dict[str, Any]]:
        jobs = []
        for path in sorted(self.jobs_root.glob("job_*/job.json"), reverse=True):
            try:
                jobs.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return jobs

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        job["cancel_requested"] = True
        pid = job.get("pid")
        if pid:
            try:
                process = psutil.Process(int(pid))
                command = " ".join(process.cmdline())
                if job_id not in command or "plotdas.jobs.worker" not in command:
                    raise JobError(f"Refusing to terminate PID {pid}: command does not match job {job_id}")
                process.terminate()
            except psutil.NoSuchProcess:
                job["status"] = "cancelled"
                job["finished_at"] = datetime.now().astimezone().isoformat()
        else:
            job["status"] = "cancelled"
            job["finished_at"] = datetime.now().astimezone().isoformat()
        self.save_job(job)
        return job
