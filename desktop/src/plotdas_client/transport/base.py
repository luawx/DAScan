from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Self


class TransportError(RuntimeError):
    """A user-actionable connection, command, or transfer failure."""


class TransferCancelled(TransportError):
    """Raised when a transfer is cancelled by the user or queue."""


@dataclass(frozen=True, slots=True)
class TransferProgress:
    remote_path: str
    transferred_bytes: int
    total_bytes: int
    percent: float
    speed_bps: float
    eta_seconds: float | None
    status: str = "downloading"
    is_cached: bool = False


ProgressCallback = Callable[[TransferProgress], None]


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise TransferCancelled("传输已取消")


@dataclass(frozen=True, slots=True)
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int


class ServerTransport(ABC):
    @abstractmethod
    def test_connection(self) -> None: ...

    @abstractmethod
    def run_command(self, command: str, timeout: float | None = None) -> CommandResult: ...

    @abstractmethod
    def download_file(
        self,
        remote_path: str,
        local_path: Path,
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> Path: ...

    @abstractmethod
    def list_files(self, remote_path: str) -> list[str]: ...

    @abstractmethod
    def read_text(self, remote_path: str) -> str: ...

    @abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> Self:
        self.test_connection()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
