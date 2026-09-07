from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(slots=True)
class AppSettings:
    server_host: str = "asgroup"
    ssh_port: int = 1015
    username: str = "xuxy"
    project_path: str = "/cluster/datapool2/xuxy/1.Code/PlotDas"
    cli_command: str = "conda run -n xyenv plotdas"
    private_key_path: str = ""
    connect_timeout: int = 10
    keepalive_interval: int = 30
    reconnect_attempts: int = 2
    max_background_transfers: int = 2
    prefetch_count: int = field(default=3, compare=False)
    show_transfer_queue: bool = field(default=False, compare=False)
    active_project: str = field(default="xinjing", compare=False)
    data_source: str = field(default="/cluster/datapool2/xuxy/1.Code/PlotDas/output/xinjing", compare=False)
    metadata_visible_sections: list[str] = field(
        default_factory=lambda: ["基本信息", "数据范围", "处理参数", "文件与版本", "其他信息"],
        compare=False,
    )


class SettingsStore:
    def __init__(self, root: Path):
        self.path = root / "config" / "settings.json"

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        allowed = AppSettings.__dataclass_fields__.keys()
        return AppSettings(**{key: value for key, value in data.items() if key in allowed})

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def save_prefetch_count(self, count: int) -> None:
        settings = self.load()
        settings.prefetch_count = max(0, min(20, count))
        self.save(settings)
