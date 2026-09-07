from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import h5py
import numpy as np
import pytest


@pytest.fixture
def zone():
    return ZoneInfo("Asia/Shanghai")


def write_legacy(path: Path, start: datetime, samples: int = 10, channels: int = 6, rate: float = 10.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    string = h5py.string_dtype("utf-8")
    times = [(start + timedelta(seconds=i / rate)).strftime("%Y%m%d%H%M%S.%f") for i in range(samples)]
    values = np.arange(samples * channels, dtype=np.float32).reshape(samples, channels)
    with h5py.File(path, "w") as handle:
        handle.create_dataset("MultiwavelengthData", data=values)
        handle.create_dataset("Time", data=np.asarray(times, dtype=object), dtype=string)
        handle.create_dataset("Locus", data=np.arange(channels, dtype=np.float32))
        handle.create_dataset("SamplingFreq", data=rate)
        handle.create_dataset("SpaceInterval", data=np.float32(1.0))
        handle.create_dataset("Spacecount", data=np.uint32(channels))
        handle.create_dataset("Timecount", data=np.uint64(samples))


@pytest.fixture
def legacy_pair(tmp_path: Path, zone):
    root = tmp_path / "input"
    start = datetime(2023, 3, 8, 12, 0, 0, tzinfo=zone)
    write_legacy(root / "20230308" / "xinjing_202303081200.h5", start)
    write_legacy(root / "20230308" / "xinjing_202303081201.h5", start + timedelta(seconds=1))
    return root, start

