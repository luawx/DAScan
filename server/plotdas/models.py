from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .exceptions import InvalidRequestError
from .timeutil import parse_datetime


@dataclass(frozen=True)
class FilterConfig:
    type: str = "none"
    lowcut: float | None = None
    highcut: float | None = None
    order: int = 4

    def validate(self, sampling_rate: float | None = None) -> None:
        allowed = {"none", "bandpass", "lowpass", "highpass"}
        if self.type not in allowed:
            raise InvalidRequestError(f"Unsupported filter type {self.type!r}; expected {sorted(allowed)}")
        if not 1 <= self.order <= 20:
            raise InvalidRequestError("filter_order must be between 1 and 20")
        nyquist = sampling_rate / 2.0 if sampling_rate else None
        if self.type == "bandpass":
            if self.lowcut is None or self.highcut is None or not 0 < self.lowcut < self.highcut:
                raise InvalidRequestError("bandpass requires 0 < lowcut < highcut")
            if nyquist and self.highcut >= nyquist:
                raise InvalidRequestError(f"highcut {self.highcut} Hz must be below Nyquist {nyquist} Hz")
        elif self.type == "lowpass":
            if self.highcut is None or self.highcut <= 0:
                raise InvalidRequestError("lowpass requires highcut > 0")
            if nyquist and self.highcut >= nyquist:
                raise InvalidRequestError(f"highcut {self.highcut} Hz must be below Nyquist {nyquist} Hz")
        elif self.type == "highpass":
            if self.lowcut is None or self.lowcut <= 0:
                raise InvalidRequestError("highpass requires lowcut > 0")
            if nyquist and self.lowcut >= nyquist:
                raise InvalidRequestError(f"lowcut {self.lowcut} Hz must be below Nyquist {nyquist} Hz")


@dataclass(frozen=True)
class ScaleConfig:
    mode: str = "percentile"
    percentile: float = 99.0
    absolute: float | None = None
    std_factor: float = 3.0

    def validate(self) -> None:
        if self.mode not in {"percentile", "absolute", "std"}:
            raise InvalidRequestError("scale_mode must be percentile, absolute, or std")
        if self.mode == "percentile" and not 50.0 <= self.percentile <= 100.0:
            raise InvalidRequestError("percentile must be between 50 and 100")
        if self.mode == "absolute" and (self.absolute is None or self.absolute <= 0):
            raise InvalidRequestError("absolute scale requires a positive value")
        if self.mode == "std" and self.std_factor <= 0:
            raise InvalidRequestError("std_factor must be positive")


@dataclass
class DASData:
    data: np.ndarray
    start_time: datetime
    end_time: datetime
    sampling_rate: float
    channels: np.ndarray
    channel_positions: np.ndarray | None = None
    channel_spacing: float | None = None
    units: str = "unknown"
    source_files: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    temporary_files: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if self.data.ndim != 2:
            raise InvalidRequestError("DASData.data must have shape (channel, time)")
        if self.data.shape[0] != len(self.channels):
            raise InvalidRequestError("DASData channel dimension does not match channels")
        if self.data.dtype != np.float32:
            self.data = self.data.astype(np.float32, copy=False)
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise InvalidRequestError("DASData times must be timezone-aware")
        if self.end_time <= self.start_time or self.sampling_rate <= 0:
            raise InvalidRequestError("DASData requires a positive time span and sampling rate")


@dataclass(frozen=True)
class PlotRequest:
    project: str
    input_root: Path
    output_root: Path
    start_time: datetime
    end_time: datetime
    channel_start: int
    channel_end: int
    filter: FilterConfig = field(default_factory=FilterConfig)
    scale: ScaleConfig = field(default_factory=ScaleConfig)
    dpi: int = 200
    image_format: str = "png"
    figsize: tuple[float, float] = (14.0, 8.0)
    max_time_pixels: int = 6000
    timezone: str = "Asia/Shanghai"
    overwrite: bool = False
    output_path: Path | None = None
    gap_tolerance_samples: float = 0.5
    channel_block_size: int = 64
    memory_limit_mb: int = 8192
    temp_root: Path = Path("/tmp")

    def validate(self) -> None:
        if self.end_time <= self.start_time:
            raise InvalidRequestError("end_time must be later than start_time")
        if self.channel_start < 0 or self.channel_end < self.channel_start:
            raise InvalidRequestError("channel range must satisfy 0 <= start <= end")
        if not 50 <= self.dpi <= 1200:
            raise InvalidRequestError("dpi must be between 50 and 1200")
        if self.image_format.lower() != "png":
            raise InvalidRequestError("first release supports PNG only")
        if self.max_time_pixels < 100:
            raise InvalidRequestError("max_time_pixels must be at least 100")
        if self.channel_block_size < 1 or self.memory_limit_mb < 64:
            raise InvalidRequestError("channel_block_size must be positive and memory_limit_mb at least 64")
        self.filter.validate()
        self.scale.validate()

    @classmethod
    def from_values(cls, *, start_time: str | datetime, end_time: str | datetime, timezone: str = "Asia/Shanghai", **kwargs: Any) -> "PlotRequest":
        return cls(start_time=parse_datetime(start_time, timezone), end_time=parse_datetime(end_time, timezone), timezone=timezone, **kwargs)


@dataclass(frozen=True)
class FileInfo:
    path: Path
    format_name: str
    start_time: datetime
    end_time: datetime
    sampling_rate: float
    channel_count: int
    channel_spacing: float | None
    sample_count: int
    units: str
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlotResult:
    image_path: Path
    metadata_path: Path
    data: DASData
