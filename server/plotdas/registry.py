from __future__ import annotations

from .exceptions import InvalidRequestError
from .plugin.base import DASPlotPlugin


def get_plugin(name: str) -> DASPlotPlugin:
    if name == "xinjing":
        from .plugin.xinjing import XinjingPlugin

        return XinjingPlugin()
    raise InvalidRequestError(f"Unknown project/plugin {name!r}; available: xinjing")

