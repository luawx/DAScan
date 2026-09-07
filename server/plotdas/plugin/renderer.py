from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from ..exceptions import InvalidRequestError, OutputExistsError
from ..models import DASData, PlotRequest, PlotResult
from ..output import atomic_write_json, output_paths, request_metadata, update_index


def _display_matrix(data: np.ndarray, max_columns: int, channel_block_size: int = 16) -> np.ndarray:
    columns = data.shape[1]
    if columns <= max_columns:
        return data
    factor = int(np.ceil(columns / max_columns))
    usable = (columns // factor) * factor
    output_columns = (usable // factor) + (1 if usable < columns else 0)
    output = np.empty((data.shape[0], output_columns), dtype=np.float32)
    for start in range(0, data.shape[0], channel_block_size):
        stop = min(start + channel_block_size, data.shape[0])
        cursor = 0
        if usable:
            reduced = data[start:stop, :usable].reshape(stop - start, -1, factor).mean(axis=2, dtype=np.float32)
            output[start:stop, :reduced.shape[1]] = reduced
            cursor = reduced.shape[1]
        if usable < columns:
            output[start:stop, cursor:] = data[start:stop, usable:].mean(axis=1, keepdims=True, dtype=np.float32)
    return output


def _scale_limit(values: np.ndarray, request: PlotRequest) -> float:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise InvalidRequestError("Requested data contains no finite samples")
    if request.scale.mode == "percentile":
        limit = float(np.percentile(np.abs(finite), request.scale.percentile))
    elif request.scale.mode == "std":
        limit = float(np.std(finite) * request.scale.std_factor)
    else:
        limit = float(request.scale.absolute)  # type: ignore[arg-type]
    if not np.isfinite(limit) or limit <= 0:
        raise InvalidRequestError("Amplitude scale is zero or non-finite")
    return limit


def render_data(data: DASData, request: PlotRequest, plugin_name: str, plugin_version: str) -> PlotResult:
    image_path, metadata_path, index_path = output_paths(request)
    if image_path.exists() and not request.overwrite:
        raise OutputExistsError(f"Output already exists: {image_path}; use --overwrite to replace it")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    display = _display_matrix(data.data, request.max_time_pixels, request.channel_block_size)
    limit = _scale_limit(display, request)
    start_num = mdates.date2num(data.start_time)
    end_num = mdates.date2num(data.end_time)
    y = data.channel_positions if data.channel_positions is not None else data.channels
    y0, y1 = float(y[0]), float(y[-1])
    fig, ax = plt.subplots(figsize=request.figsize, constrained_layout=True)
    plot = ax.imshow(display, aspect="auto", origin="lower", interpolation="nearest", cmap="seismic", vmin=-limit, vmax=limit, extent=[start_num, end_num, y0, y1])
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S", tz=data.start_time.tzinfo))
    ax.set_xlabel(f"Time ({request.timezone})")
    ax.set_ylabel("Distance (m)" if data.channel_positions is not None else "Channel")
    ax.set_title(f"{request.project} | {data.start_time:%Y-%m-%d %H:%M:%S} | ch {request.channel_start}-{request.channel_end} | {request.filter.type}")
    colorbar = fig.colorbar(plot, ax=ax)
    colorbar.set_label(data.units)
    fd, temporary = tempfile.mkstemp(prefix=f".{image_path.stem}.", suffix=f".{request.image_format}", dir=image_path.parent)
    os.close(fd)
    try:
        fig.savefig(temporary, dpi=request.dpi, format=request.image_format)
        os.replace(temporary, image_path)
    finally:
        plt.close(fig)
        if os.path.exists(temporary):
            os.unlink(temporary)

    payload = request_metadata(request, plugin_name, plugin_version)
    try:
        relative_image = str(image_path.relative_to(request.output_root))
    except ValueError:
        relative_image = str(image_path)
    payload.update({
        "status": "success",
        "start_time": data.start_time.isoformat(),
        "end_time": data.end_time.isoformat(),
        "sampling_rate": data.sampling_rate,
        "sample_count": data.data.shape[1],
        "channel_count": data.data.shape[0],
        "channel_spacing": data.channel_spacing,
        "units": data.units,
        "source_files": data.source_files,
        "source_metadata": data.metadata,
        "image_path": relative_image,
        "metadata_path": str(metadata_path),
        "created_at": datetime.now().astimezone().isoformat(),
    })
    atomic_write_json(metadata_path, payload)
    update_index(index_path, payload)
    return PlotResult(image_path=image_path, metadata_path=metadata_path, data=data)
