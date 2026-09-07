from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PlotRequest:
    project: str
    start_time: datetime
    end_time: datetime
    channel_start: int
    channel_end: int
    filter_type: str = "none"
    lowcut: float | None = None
    highcut: float | None = None
    dpi: int = 200
    window_length: int = 60

    def validate(self) -> None:
        if self.end_time <= self.start_time:
            raise ValueError("结束时间必须晚于开始时间")
        if self.channel_start < 0 or self.channel_end <= self.channel_start:
            raise ValueError("通道范围必须满足 0 ≤ 起始通道 < 结束通道")
        if self.filter_type not in {"none", "bandpass", "lowpass", "highpass"}:
            raise ValueError(f"不支持的滤波类型: {self.filter_type}")
        if self.filter_type in {"bandpass", "highpass"} and self.lowcut is None:
            raise ValueError("当前滤波类型需要 Lowcut")
        if self.filter_type in {"bandpass", "lowpass"} and self.highcut is None:
            raise ValueError("当前滤波类型需要 Highcut")
        if self.lowcut is not None and self.highcut is not None and self.lowcut >= self.highcut:
            raise ValueError("Lowcut 必须小于 Highcut")
        if not 50 <= self.dpi <= 1200:
            raise ValueError("DPI 必须在 50–1200 之间")
