# Job System

Jobs live in `jobs/<job_id>/job.json` with a sibling `log.txt`. JSON writes are atomic. A job records request, PID, window length, total/completed/failed counts, current window, timestamps, cancellation flag, and error.

States are `pending`, `running`, `completed`, `failed`, and `cancelled`. `job start` launches `plotdas.jobs.worker` in a detached process and returns immediately. The worker divides `[start,end)` into consecutive windows; the final window may be shorter. It invokes the same plugin API as single-image plotting and fails the job on the first failed window.

Cancellation first persists `cancel_requested`, verifies that the stored PID command contains both the worker module and job ID, then sends SIGTERM. The worker catches it and atomically records `cancelled`. This check prevents terminating an unrelated reused PID.

The JSON contract is intentionally suitable for a future local service or desktop client; no database is required in this phase.

`job create-all` is the discontinuous archive mode. It scans HDF5 headers, excludes unreadable or channel-incompatible files, splits data whenever time, sample rate, or channel layout is discontinuous, and stores all resulting windows in `windows.json`. Its worker continues after individual failed windows; after exhausting the manifest it is `completed` with zero failures or `failed` with the final failure count.
