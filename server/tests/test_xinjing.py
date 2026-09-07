from datetime import timedelta
from pathlib import Path

import h5py
import numpy as np
import pytest

from plotdas.exceptions import ChannelRangeError, DataGapError, DataReadError
from plotdas.models import PlotRequest
from plotdas.plugin.xinjing import XinjingPlugin


def test_legacy_cross_file_read(legacy_pair, tmp_path: Path):
    root, start = legacy_pair
    request = PlotRequest("xinjing", root, tmp_path / "out", start + timedelta(seconds=0.5), start + timedelta(seconds=1.5), 1, 3)
    data = XinjingPlugin().read(request)
    assert data.data.shape == (3, 10)
    assert data.data.dtype == np.float32
    assert data.source_files[0].endswith("1200.h5")
    assert data.source_files[1].endswith("1201.h5")


def test_channel_error_is_explicit(legacy_pair, tmp_path: Path):
    root, start = legacy_pair
    request = PlotRequest("xinjing", root, tmp_path / "out", start, start + timedelta(seconds=0.5), 0, 6)
    with pytest.raises(ChannelRangeError, match="available channels 0-5"):
        XinjingPlugin().read(request)


def test_prodml_inspection_reinterprets_wall_clock(tmp_path: Path, zone):
    path = tmp_path / "prodml.h5"
    with h5py.File(path, "w") as handle:
        acquisition = handle.create_group("Acquisition")
        acquisition.attrs["SpatialSamplingInterval"] = 1.02
        acquisition.attrs["MeasurementStartTime"] = b"2023-03-15T19:38:00+00:00"
        raw = acquisition.create_group("Raw[0]")
        raw.attrs["OutputDataRate"] = 500.0
        raw.attrs["RawDataUnit"] = b"strain rate"
        raw.create_dataset("RawData", data=np.ones((2, 6), dtype=np.float32))
        raw.create_dataset("RawDataTime", data=np.asarray([1678909080000000, 1678909080002000], dtype=np.int64))
    info = XinjingPlugin().inspect_file(path)
    assert info.format_name == "prodml-2.0"
    assert info.start_time.hour == 19
    assert info.start_time.tzinfo == zone


@pytest.mark.parametrize("rate,channels", [(500.0, 880), (4000.0, 978), (5000.0, 900)])
def test_prodml_rate_and_channel_variants(tmp_path: Path, zone, rate: float, channels: int):
    path = tmp_path / f"prodml_{int(rate)}.h5"
    first = 1678909080000000
    step = int(1_000_000 / rate)
    with h5py.File(path, "w") as handle:
        acquisition = handle.create_group("Acquisition")
        acquisition.attrs["SpatialSamplingInterval"] = 1.02
        raw = acquisition.create_group("Raw[0]")
        raw.attrs["OutputDataRate"] = rate
        raw.create_dataset("RawData", data=np.ones((2, channels), dtype=np.float32))
        raw.create_dataset("RawDataTime", data=np.asarray([first, first + step], dtype=np.int64))
    info = XinjingPlugin().inspect_file(path)
    assert info.sampling_rate == rate
    assert info.channel_count == channels


def test_gap_between_files_is_reported(tmp_path: Path, zone):
    from conftest import write_legacy
    from datetime import datetime

    root = tmp_path / "input"
    start = datetime(2023, 3, 8, 12, 0, tzinfo=zone)
    write_legacy(root / "20230308" / "x_202303081200.h5", start, rate=10)
    write_legacy(root / "20230308" / "x_202303081201.h5", start + timedelta(seconds=1.2), rate=10)
    request = PlotRequest("xinjing", root, tmp_path / "out", start + timedelta(seconds=.5), start + timedelta(seconds=1.5), 0, 2)
    with pytest.raises(DataGapError, match="gap"):
        XinjingPlugin().read(request)


def test_empty_and_corrupt_files_are_rejected(tmp_path: Path):
    empty = tmp_path / "empty.h5"
    with h5py.File(empty, "w") as handle:
        handle.create_dataset("MultiwavelengthData", shape=(0, 0), dtype=np.float32)
    corrupt = tmp_path / "corrupt.h5"
    corrupt.write_bytes(b"not hdf5")
    with pytest.raises(DataReadError, match="Empty"):
        XinjingPlugin().inspect_file(empty)
    with pytest.raises(DataReadError, match="Cannot inspect"):
        XinjingPlugin().inspect_file(corrupt)


def test_sampling_rate_change_is_rejected(tmp_path: Path, zone):
    from conftest import write_legacy
    from datetime import datetime

    root = tmp_path / "input"
    start = datetime(2023, 3, 8, 12, 0, tzinfo=zone)
    write_legacy(root / "20230308" / "x_202303081200.h5", start, rate=10)
    write_legacy(root / "20230308" / "x_202303081201.h5", start + timedelta(seconds=1), rate=20)
    request = PlotRequest("xinjing", root, tmp_path / "out", start + timedelta(seconds=.5), start + timedelta(seconds=1.2), 0, 2)
    with pytest.raises(DataReadError, match="Sampling rate changes"):
        XinjingPlugin().read(request)
