from datetime import datetime, timedelta
from pathlib import Path

import pytest

from plotdas.config import deep_merge
from plotdas.exceptions import InvalidRequestError
from plotdas.models import FilterConfig, PlotRequest


def test_deep_merge_preserves_nested_defaults():
    result = deep_merge({"plot": {"dpi": 200, "format": "png"}}, {"plot": {"dpi": 100}})
    assert result == {"plot": {"dpi": 100, "format": "png"}}


def test_filter_rejects_nyquist():
    with pytest.raises(InvalidRequestError, match="Nyquist"):
        FilterConfig(type="bandpass", lowcut=2, highcut=60).validate(100)


def test_request_uses_inclusive_channel_range(zone):
    start = datetime(2023, 1, 1, tzinfo=zone)
    request = PlotRequest("xinjing", Path("in"), Path("out"), start, start + timedelta(seconds=1), 2, 4)
    request.validate()
    assert request.channel_end - request.channel_start + 1 == 3

