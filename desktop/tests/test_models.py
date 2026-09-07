from datetime import datetime

import pytest

from plotdas_client.models import PlotRequest


def request(**changes):
    values = {
        "project": "xinjing",
        "start_time": datetime(2023, 3, 8, 12, 0),
        "end_time": datetime(2023, 3, 8, 12, 1),
        "channel_start": 390,
        "channel_end": 882,
    }
    values.update(changes)
    return PlotRequest(**values)


def test_valid_request():
    request(filter_type="bandpass", lowcut=2, highcut=40).validate()


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"end_time": datetime(2023, 3, 8, 11, 59)}, "结束时间"),
        ({"channel_end": 390}, "通道范围"),
        ({"filter_type": "bandpass", "lowcut": None, "highcut": 40}, "Lowcut"),
        ({"filter_type": "lowpass", "highcut": None}, "Highcut"),
    ],
)
def test_invalid_requests(changes, message):
    with pytest.raises(ValueError, match=message):
        request(**changes).validate()
