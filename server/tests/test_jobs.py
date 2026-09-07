from datetime import datetime, timedelta
from pathlib import Path

import pytest

from plotdas.exceptions import JobError
from plotdas.jobs.manager import JobManager, split_windows
from plotdas.models import PlotRequest


def test_split_windows_keeps_short_tail(zone):
    start = datetime(2023, 3, 8, tzinfo=zone)
    windows = list(split_windows(start, start + timedelta(seconds=125), 60))
    assert [int((end - begin).total_seconds()) for begin, end in windows] == [60, 60, 5]


def test_create_job_persists_pending_state(zone, tmp_path: Path):
    start = datetime(2023, 3, 8, tzinfo=zone)
    request = PlotRequest("xinjing", tmp_path, tmp_path / "out", start, start + timedelta(seconds=120), 0, 2)
    manager = JobManager(tmp_path / "jobs")
    job = manager.create_job(request, 60)
    assert job["status"] == "pending"
    assert manager.get_job(job["job_id"])["total"] == 2


def test_cancel_pending_job_is_safe(zone, tmp_path: Path):
    start = datetime(2023, 3, 8, tzinfo=zone)
    request = PlotRequest("xinjing", tmp_path, tmp_path / "out", start, start + timedelta(seconds=10), 0, 2)
    manager = JobManager(tmp_path / "jobs")
    job = manager.create_job(request, 10)
    cancelled = manager.cancel_job(job["job_id"])
    assert cancelled["status"] == "cancelled"
    assert cancelled["finished_at"] is not None


def test_cancel_refuses_unrelated_pid(zone, tmp_path: Path, monkeypatch):
    start = datetime(2023, 3, 8, tzinfo=zone)
    request = PlotRequest("xinjing", tmp_path, tmp_path / "out", start, start + timedelta(seconds=10), 0, 2)
    manager = JobManager(tmp_path / "jobs")
    job = manager.create_job(request, 10)
    job.update({"status": "running", "pid": 12345})
    manager.save_job(job)

    class UnrelatedProcess:
        def cmdline(self):
            return ["python", "unrelated.py"]

        def terminate(self):
            raise AssertionError("must not terminate unrelated process")

    monkeypatch.setattr("plotdas.jobs.manager.psutil.Process", lambda _pid: UnrelatedProcess())
    with pytest.raises(JobError, match="Refusing to terminate"):
        manager.cancel_job(job["job_id"])
