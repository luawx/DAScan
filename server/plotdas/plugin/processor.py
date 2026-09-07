from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt

from ..exceptions import InvalidRequestError
from ..models import DASData, PlotRequest


def process_data(data: DASData, request: PlotRequest) -> DASData:
    config = request.filter
    config.validate(data.sampling_rate)
    if config.type == "none":
        return data

    nyquist = data.sampling_rate / 2.0
    if config.type == "bandpass":
        wn = [config.lowcut / nyquist, config.highcut / nyquist]  # type: ignore[operator]
        btype = "bandpass"
    elif config.type == "lowpass":
        wn = config.highcut / nyquist  # type: ignore[operator]
        btype = "lowpass"
    else:
        wn = config.lowcut / nyquist  # type: ignore[operator]
        btype = "highpass"
    sos = butter(config.order, wn, btype=btype, output="sos")
    in_place = isinstance(data.data, np.memmap)
    result = data.data if in_place else np.empty_like(data.data, dtype=np.float32)
    block = max(1, request.channel_block_size)
    try:
        for start in range(0, data.data.shape[0], block):
            stop = min(start + block, data.data.shape[0])
            filtered = sosfiltfilt(sos, data.data[start:stop], axis=-1)
            result[start:stop] = filtered.astype(np.float32, copy=False)
            if in_place:
                result.flush()
    except ValueError as exc:
        raise InvalidRequestError(f"Data window is too short for {config.type} filter order {config.order}: {exc}") from exc
    return DASData(
        data=result,
        start_time=data.start_time,
        end_time=data.end_time,
        sampling_rate=data.sampling_rate,
        channels=data.channels,
        channel_positions=data.channel_positions,
        channel_spacing=data.channel_spacing,
        units=data.units,
        source_files=data.source_files,
        metadata={**data.metadata, "filter_applied": True},
        temporary_files=data.temporary_files,
    )
