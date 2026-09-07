from __future__ import annotations

import math
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import h5py
import numpy as np

from ..exceptions import ChannelRangeError, DataGapError, DataReadError, UnsupportedFormatError
from ..models import DASData, FileInfo, PlotRequest, PlotResult
from .base import DASPlotPlugin
from .processor import process_data
from .renderer import render_data

_FILENAME_TIME = re.compile(r"(\d{12})(?:\.h5)?$")


def _decode(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [_decode(item) for item in value.tolist()]
    return value


def _legacy_time(value, zone: ZoneInfo) -> datetime:
    text = _decode(value)
    return datetime.strptime(str(text), "%Y%m%d%H%M%S.%f").replace(tzinfo=zone)


def _prodml_time(microseconds: int, zone: ZoneInfo) -> datetime:
    utc_clock = datetime.fromtimestamp(int(microseconds) / 1_000_000, tz=timezone.utc)
    return utc_clock.replace(tzinfo=zone)


class XinjingPlugin(DASPlotPlugin):
    name = "xinjing"
    version = "0.1.0"

    def inspect_file(self, path: Path, timezone_name: str = "Asia/Shanghai") -> FileInfo:
        zone = ZoneInfo(timezone_name)
        try:
            with h5py.File(path, "r") as handle:
                if "MultiwavelengthData" in handle:
                    dataset = handle["MultiwavelengthData"]
                    count, channels = dataset.shape
                    if count == 0 or channels == 0:
                        raise DataReadError(f"Empty DAS dataset in {path}")
                    rate = float(handle["SamplingFreq"][()])
                    start = _legacy_time(handle["Time"][0], zone)
                    last = _legacy_time(handle["Time"][-1], zone)
                    spacing = float(handle["SpaceInterval"][()]) if "SpaceInterval" in handle else None
                    end = last + timedelta(seconds=1.0 / rate)
                    raw = {"layout": "legacy-flat", "raw_start": str(_decode(handle["Time"][0])), "raw_end": str(_decode(handle["Time"][-1]))}
                    return FileInfo(path, "legacy-flat", start, end, rate, channels, spacing, count, "amplitude", raw)
                raw_path = "Acquisition/Raw[0]/RawData"
                time_path = "Acquisition/Raw[0]/RawDataTime"
                if raw_path in handle and time_path in handle:
                    dataset = handle[raw_path]
                    count, channels = dataset.shape
                    if count == 0 or channels == 0:
                        raise DataReadError(f"Empty DAS dataset in {path}")
                    raw_group = handle["Acquisition/Raw[0]"]
                    acquisition = handle["Acquisition"]
                    rate = float(raw_group.attrs["OutputDataRate"])
                    times = handle[time_path]
                    start = _prodml_time(int(times[0]), zone)
                    end = _prodml_time(int(times[-1]), zone) + timedelta(seconds=1.0 / rate)
                    spacing = float(acquisition.attrs.get("SpatialSamplingInterval", np.nan))
                    if not np.isfinite(spacing):
                        spacing = None
                    units = str(_decode(raw_group.attrs.get("RawDataUnit", b"unknown")))
                    raw = {
                        "layout": "prodml-2.0",
                        "embedded_measurement_start": str(_decode(acquisition.attrs.get("MeasurementStartTime", b""))),
                        "raw_time_first_us": int(times[0]),
                        "raw_time_last_us": int(times[-1]),
                        "time_policy": "reinterpret-clock-as-Asia/Shanghai",
                    }
                    return FileInfo(path, "prodml-2.0", start, end, rate, channels, spacing, count, units, raw)
        except (OSError, KeyError, ValueError) as exc:
            raise DataReadError(f"Cannot inspect HDF5 {path}: {exc}") from exc
        raise UnsupportedFormatError(f"Unsupported Xinjing HDF5 structure: {path}")

    def _candidate_paths(self, request: PlotRequest) -> list[Path]:
        paths: list[Path] = []
        current = request.start_time.date()
        last = request.end_time.date()
        while current <= last:
            directory = request.input_root / current.strftime("%Y%m%d")
            if directory.is_dir():
                paths.extend(sorted(directory.glob("*.h5")))
            current += timedelta(days=1)
        lower = request.start_time - timedelta(minutes=2)
        upper = request.end_time + timedelta(minutes=2)
        filtered: list[Path] = []
        for path in paths:
            match = _FILENAME_TIME.search(path.stem)
            if match:
                nominal = datetime.strptime(match.group(1), "%Y%m%d%H%M").replace(tzinfo=request.start_time.tzinfo)
                if nominal < lower or nominal > upper:
                    continue
            filtered.append(path)
        return filtered

    def _overlapping_files(self, request: PlotRequest) -> list[FileInfo]:
        infos: list[FileInfo] = []
        errors: list[str] = []
        for path in self._candidate_paths(request):
            try:
                info = self.inspect_file(path, request.timezone)
            except (DataReadError, UnsupportedFormatError) as exc:
                errors.append(str(exc))
                continue
            if info.end_time > request.start_time and info.start_time < request.end_time:
                infos.append(info)
        infos.sort(key=lambda item: item.start_time)
        if not infos:
            detail = f" Inspection errors: {'; '.join(errors[:3])}" if errors else ""
            raise DataReadError(f"No readable HDF5 data covers {request.start_time.isoformat()} to {request.end_time.isoformat()}.{detail}")
        return infos

    def read(self, request: PlotRequest) -> DASData:
        request.validate()
        infos = self._overlapping_files(request)
        first = infos[0]
        if request.channel_end >= first.channel_count:
            raise ChannelRangeError(f"Requested channel {request.channel_end} exceeds available channels 0-{first.channel_count - 1} in {first.path}")
        sources: list[str] = []
        source_details = []
        overlap_trims = []
        segments: list[tuple[FileInfo, int, int]] = []
        actual_start = None
        actual_end = None
        previous_end = None
        tolerance = request.gap_tolerance_samples / first.sampling_rate
        for info in infos:
            if not math.isclose(info.sampling_rate, first.sampling_rate, rel_tol=0, abs_tol=1e-9):
                raise DataReadError(f"Sampling rate changes from {first.sampling_rate} to {info.sampling_rate} Hz at {info.path}")
            if info.channel_count != first.channel_count:
                raise DataReadError(f"Channel count changes from {first.channel_count} to {info.channel_count} at {info.path}")
            if request.channel_end >= info.channel_count:
                raise ChannelRangeError(f"Requested channel {request.channel_end} exceeds available channels 0-{info.channel_count - 1} in {info.path}")
            rate = info.sampling_rate
            start_index = max(0, int(math.ceil((request.start_time - info.start_time).total_seconds() * rate - 1e-7)))
            end_index = min(info.sample_count, int(math.ceil((request.end_time - info.start_time).total_seconds() * rate - 1e-7)))
            if end_index <= start_index:
                continue
            segment_start = info.start_time + timedelta(seconds=start_index / rate)
            segment_end = info.start_time + timedelta(seconds=end_index / rate)
            if previous_end is not None:
                delta = (segment_start - previous_end).total_seconds()
                if delta > tolerance:
                    raise DataGapError(f"Data gap of {delta:.6f}s before {info.path}; tolerance is {tolerance:.6f}s")
                if delta < -tolerance:
                    trim_samples = int(math.ceil((-delta) * rate - 1e-7))
                    start_index += trim_samples
                    segment_start = info.start_time + timedelta(seconds=start_index / rate)
                    overlap_trims.append({"path": str(info.path), "trimmed_samples": trim_samples, "overlap_seconds": -delta})
                    if end_index <= start_index:
                        continue
            segments.append((info, start_index, end_index))
            sources.append(str(info.path))
            source_details.append(info.raw_metadata)
            actual_start = segment_start if actual_start is None else actual_start
            actual_end = segment_end
            previous_end = segment_end
        if not segments or actual_start is None or actual_end is None:
            raise DataReadError("No samples remain after applying the requested time range")
        initial_gap = (actual_start - request.start_time).total_seconds()
        final_gap = (request.end_time - actual_end).total_seconds()
        boundary_tolerance = 1.5 / first.sampling_rate
        if initial_gap > boundary_tolerance or final_gap > boundary_tolerance:
            raise DataGapError(f"Requested interval is not fully covered: leading={initial_gap:.6f}s trailing={final_gap:.6f}s boundary_tolerance={boundary_tolerance:.6f}s")
        channel_count = request.channel_end - request.channel_start + 1
        total_samples = sum(end - start for _, start, end in segments)
        byte_count = channel_count * total_samples * np.dtype(np.float32).itemsize
        temporary_files: list[str] = []
        if byte_count > request.memory_limit_mb * 1024 * 1024:
            request.temp_root.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix="plotdas-data-", suffix=".mmap", dir=request.temp_root)
            os.close(fd)
            combined = np.memmap(temporary, dtype=np.float32, mode="w+", shape=(channel_count, total_samples))
            temporary_files.append(temporary)
        else:
            combined = np.empty((channel_count, total_samples), dtype=np.float32)
        time_offset = 0
        try:
            for info, start_index, end_index in segments:
                count = end_index - start_index
                with h5py.File(info.path, "r") as handle:
                    key = "MultiwavelengthData" if info.format_name == "legacy-flat" else "Acquisition/Raw[0]/RawData"
                    dataset = handle[key]
                    for channel_start in range(request.channel_start, request.channel_end + 1, request.channel_block_size):
                        channel_end = min(channel_start + request.channel_block_size, request.channel_end + 1)
                        chunk = np.asarray(dataset[start_index:end_index, channel_start:channel_end], dtype=np.float32)
                        out_start = channel_start - request.channel_start
                        combined[out_start:out_start + chunk.shape[1], time_offset:time_offset + count] = chunk.T
                time_offset += count
            if isinstance(combined, np.memmap):
                combined.flush()
        except Exception:
            for temporary in temporary_files:
                Path(temporary).unlink(missing_ok=True)
            raise
        channels = np.arange(request.channel_start, request.channel_end + 1, dtype=np.int32)
        positions = channels.astype(np.float64) * first.channel_spacing if first.channel_spacing is not None else None
        return DASData(
            data=combined,
            start_time=actual_start,
            end_time=actual_end,
            sampling_rate=first.sampling_rate,
            channels=channels,
            channel_positions=positions,
            channel_spacing=first.channel_spacing,
            units=first.units,
            source_files=sources,
            metadata={"formats": sorted({info.format_name for info in infos}), "source_details": source_details, "overlap_trims": overlap_trims, "requested_start": request.start_time.isoformat(), "requested_end": request.end_time.isoformat()},
            temporary_files=temporary_files,
        )

    def process(self, data: DASData, request: PlotRequest) -> DASData:
        return process_data(data, request)

    def render(self, data: DASData, request: PlotRequest) -> PlotResult:
        return render_data(data, request, self.name, self.version)
