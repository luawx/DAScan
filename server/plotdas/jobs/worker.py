from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from ..registry import get_plugin
from .manager import JobManager, request_from_dict, split_windows


class JobCancelled(BaseException):
    """Control-flow signal kept outside ordinary plot failures."""

    pass


def run(jobs_root: Path, job_id: str) -> int:
    manager = JobManager(jobs_root)
    job = manager.get_job(job_id)

    # Avoid a launch race: the parent persists the spawned PID immediately after Popen.
    for _ in range(100):
        job = manager.get_job(job_id)
        if job.get("pid") == os.getpid():
            break
        time.sleep(0.05)
    else:
        raise RuntimeError(f"Job {job_id} did not publish worker PID {os.getpid()}")

    def cancel(_signum, _frame):
        raise JobCancelled("Cancellation requested")

    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    base = request_from_dict(job["request"])
    plugin = get_plugin(base.project)
    try:
        if job.get("cancel_requested"):
            raise JobCancelled("Cancellation requested before start")
        windows = manager.load_windows(job)
        for start, end in windows:
            job = manager.get_job(job_id)
            if job.get("cancel_requested"):
                raise JobCancelled("Cancellation requested")
            job["current_window"] = {"start": start.isoformat(), "end": end.isoformat()}
            manager.save_job(job)
            request = request_from_dict({**job["request"], "start_time": start.isoformat(), "end_time": end.isoformat()})
            try:
                plugin.plot(request)
            except Exception:
                job = manager.get_job(job_id)
                job["failed"] += 1
                manager.save_job(job)
                if job.get("continue_on_error"):
                    print(f"Window failed: {start.isoformat()} to {end.isoformat()}", file=sys.stderr, flush=True)
                    continue
                raise
            job = manager.get_job(job_id)
            job["completed"] += 1
            manager.save_job(job)
        job = manager.get_job(job_id)
        final_status = "completed" if job["failed"] == 0 else "failed"
        final_error = None if job["failed"] == 0 else f"Finished all windows with {job['failed']} failures"
        job.update({"status": final_status, "finished_at": datetime.now().astimezone().isoformat(), "current_window": None, "error": final_error})
        manager.save_job(job)
        return 0 if job["failed"] == 0 else 1
    except JobCancelled as exc:
        job = manager.get_job(job_id)
        job.update({"status": "cancelled", "finished_at": datetime.now().astimezone().isoformat(), "current_window": None, "error": str(exc)})
        manager.save_job(job)
        return 2
    except Exception as exc:
        job = manager.get_job(job_id)
        job.update({"status": "failed", "finished_at": datetime.now().astimezone().isoformat(), "error": f"{type(exc).__name__}: {exc}"})
        manager.save_job(job)
        print(job["error"], file=sys.stderr, flush=True)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs-root", required=True, type=Path)
    parser.add_argument("job_id")
    args = parser.parse_args()
    raise SystemExit(run(args.jobs_root, args.job_id))


if __name__ == "__main__":
    main()
