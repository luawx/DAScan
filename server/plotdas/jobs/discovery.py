from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from multiprocessing import Pool
from pathlib import Path
from typing import Any

from ..models import FileInfo
from ..plugin.xinjing import XinjingPlugin


def _inspect_one(path: str):
    try:
        return True, XinjingPlugin().inspect_file(Path(path))
    except Exception as exc:
        return False, {"path": path, "error": f"{type(exc).__name__}: {exc}"}


def _segment_windows(infos: list[FileInfo], window_length: float) -> tuple[list[tuple[datetime, datetime]], int]:
    if not infos:
        return [], 0
    segments: list[tuple[datetime, datetime]] = []
    current_start = infos[0].start_time
    current_end = infos[0].end_time
    current_rate = infos[0].sampling_rate
    current_channels = infos[0].channel_count
    for info in infos[1:]:
        tolerance = 0.5 / current_rate
        gap = (info.start_time - current_end).total_seconds()
        compatible = info.sampling_rate == current_rate and info.channel_count == current_channels and abs(gap) <= tolerance
        if compatible:
            current_end = max(current_end, info.end_time)
        else:
            segments.append((current_start, current_end))
            current_start, current_end = info.start_time, info.end_time
            current_rate, current_channels = info.sampling_rate, info.channel_count
    segments.append((current_start, current_end))
    windows: list[tuple[datetime, datetime]] = []
    step = timedelta(seconds=window_length)
    for start, end in segments:
        current = start
        while current < end:
            following = min(current + step, end)
            windows.append((current, following))
            current = following
    return windows, len(segments)


def discover_all_windows(input_root: Path, channel_end: int, window_length: float, workers: int = 8) -> tuple[list[tuple[datetime, datetime]], dict[str, Any]]:
    paths = sorted(input_root.rglob("*.h5"))
    with Pool(max(1, workers)) as pool:
        results = list(pool.imap_unordered(_inspect_one, map(str, paths), chunksize=16))
    readable = [value for ok, value in results if ok]
    skipped = [value for ok, value in results if not ok]
    eligible: list[FileInfo] = []
    for info in readable:
        if info.channel_count <= channel_end:
            skipped.append({"path": str(info.path), "error": f"Channel {channel_end} exceeds available 0-{info.channel_count - 1}"})
        else:
            eligible.append(info)
    eligible.sort(key=lambda item: (item.start_time, item.end_time, str(item.path)))
    windows, segment_count = _segment_windows(eligible, window_length)
    discovery = {
        "scanned_files": len(paths),
        "readable_files": len(readable),
        "eligible_files": len(eligible),
        "skipped_count": len(skipped),
        "skipped_files": skipped,
        "segment_count": segment_count,
        "sampling_rates": dict(Counter(str(info.sampling_rate) for info in eligible)),
        "channel_counts": dict(Counter(str(info.channel_count) for info in eligible)),
        "discovered_at": datetime.now().astimezone().isoformat(),
    }
    return windows, discovery
