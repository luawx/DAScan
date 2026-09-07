from datetime import datetime, timedelta
from pathlib import Path

import json
import numpy as np
import pytest

from plotdas.exceptions import OutputExistsError
from plotdas.models import DASData, FilterConfig, PlotRequest
from plotdas.plugin.processor import process_data
from plotdas.plugin.renderer import render_data


def data_fixture(zone, samples=1000):
    start = datetime(2023, 3, 8, 12, 0, tzinfo=zone)
    t = np.arange(samples, dtype=np.float32) / 100.0
    matrix = np.stack([np.sin(2 * np.pi * 5 * t), np.sin(2 * np.pi * 5 * t)]).astype(np.float32)
    return DASData(matrix, start, start + timedelta(seconds=samples / 100), 100.0, np.array([2, 3], dtype=np.int32), units="u")


def test_bandpass_keeps_float32(zone, tmp_path: Path):
    data = data_fixture(zone)
    request = PlotRequest("xinjing", tmp_path, tmp_path, data.start_time, data.end_time, 2, 3, filter=FilterConfig("bandpass", 2, 20, 4))
    result = process_data(data, request)
    assert result.data.dtype == np.float32
    assert result.data.shape == data.data.shape


def test_renderer_writes_image_metadata_and_index(zone, tmp_path: Path):
    data = data_fixture(zone, samples=200)
    request = PlotRequest("xinjing", tmp_path, tmp_path / "output", data.start_time, data.end_time, 2, 3, dpi=72, max_time_pixels=100)
    result = render_data(data, request, "test", "1")
    assert result.image_path.exists()
    payload = json.loads(result.metadata_path.read_text())
    assert payload["status"] == "success"
    index = json.loads((result.metadata_path.parent.parent / "index.json").read_text())
    assert len(index["records"]) == 1


def test_renderer_refuses_overwrite(zone, tmp_path: Path):
    data = data_fixture(zone, samples=200)
    request = PlotRequest("xinjing", tmp_path, tmp_path / "output", data.start_time, data.end_time, 2, 3, dpi=72)
    render_data(data, request, "test", "1")
    with pytest.raises(OutputExistsError, match="--overwrite"):
        render_data(data, request, "test", "1")
