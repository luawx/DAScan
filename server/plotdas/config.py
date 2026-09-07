from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigurationError

BUILTIN_DEFAULTS: dict[str, Any] = {
    "input_root": "/cluster/datapool4/liaoxl/xinjing_group/das_h5",
    "output_root": "/cluster/datapool2/xuxy/1.Code/PlotDas/output",
    "jobs_root": "/cluster/datapool2/xuxy/1.Code/PlotDas/jobs",
    "project": "xinjing",
    "timezone": "Asia/Shanghai",
    "plot": {"dpi": 200, "format": "png", "figsize": [14.0, 8.0], "max_time_pixels": 6000},
    "filter": {"type": "none", "order": 4},
    "scale": {"mode": "percentile", "percentile": 99.0},
    "reader": {"gap_tolerance_samples": 0.5, "channel_block_size": 64, "memory_limit_mb": 8192, "temp_root": "/tmp"},
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        elif value is not None:
            result[key] = value
    return result


def load_config(path: Path | None = None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    config = deepcopy(BUILTIN_DEFAULTS)
    default_path = Path(__file__).resolve().parents[1] / "config" / "default.yaml"
    selected = path or (default_path if default_path.exists() else None)
    if selected:
        try:
            with selected.open("r", encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigurationError(f"Cannot load configuration {selected}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ConfigurationError(f"Configuration {selected} must contain a mapping")
        config = deep_merge(config, loaded)
    if overrides:
        config = deep_merge(config, overrides)
    return config
