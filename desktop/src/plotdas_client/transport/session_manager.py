from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Condition, Lock
from typing import TypeVar

from plotdas_client.config import AppSettings

from .base import (
    CancellationToken,
    CommandResult,
    ProgressCallback,
    ServerTransport,
    TransferCancelled,
    TransportError,
)
from .ssh import SSHTransport

T = TypeVar("T")


class SessionManager(ServerTransport):
    """WinSCP-style persistent browse session plus reusable transfer sessions."""

    def __init__(
        self,
        settings: AppSettings,
        password: str = "",
        transport_factory: Callable[[], ServerTransport] | None = None,
    ) -> None:
        self.settings = settings
        self.password = password
        self._factory = transport_factory or (lambda: SSHTransport(settings, password))
        self._browse_transport: ServerTransport | None = None
        self._browse_lock = Lock()
        self._cache_lock = Lock()
        self._list_cache: dict[str, list[str]] = {}
        self._text_cache: dict[str, str] = {}
        self._pool = Condition()
        self._idle: list[ServerTransport] = []
        self._active: set[ServerTransport] = set()
        self._created = 0
        self._closed = False

    def _browse_call(self, operation: Callable[[ServerTransport], T]) -> T:
        with self._browse_lock:
            last_error: TransportError | None = None
            for attempt in range(self.settings.reconnect_attempts + 1):
                if self._closed:
                    raise TransportError("SSH 会话已关闭")
                if self._browse_transport is None:
                    self._browse_transport = self._factory()
                try:
                    return operation(self._browse_transport)
                except TransportError as exc:
                    last_error = exc
                    self._browse_transport.close()
                    self._browse_transport = None
                    if attempt >= self.settings.reconnect_attempts:
                        raise
            raise last_error or TransportError("SSH 会话重连失败")

    def test_connection(self) -> None:
        self._browse_call(lambda transport: transport.test_connection())

    def run_command(self, command: str, timeout: float | None = None) -> CommandResult:
        return self._browse_call(lambda transport: transport.run_command(command, timeout))

    def list_files(self, remote_path: str) -> list[str]:
        with self._cache_lock:
            cached = self._list_cache.get(remote_path)
        if cached is not None:
            return list(cached)
        result = self._browse_call(lambda transport: transport.list_files(remote_path))
        with self._cache_lock:
            self._list_cache[remote_path] = list(result)
        return result

    def read_text(self, remote_path: str) -> str:
        with self._cache_lock:
            cached = self._text_cache.get(remote_path)
        if cached is not None:
            return cached
        result = self._browse_call(lambda transport: transport.read_text(remote_path))
        with self._cache_lock:
            self._text_cache[remote_path] = result
        return result

    def invalidate(self, remote_prefix: str | None = None) -> None:
        with self._cache_lock:
            if remote_prefix is None:
                self._list_cache.clear()
                self._text_cache.clear()
                return
            self._list_cache = {
                path: value for path, value in self._list_cache.items() if not path.startswith(remote_prefix)
            }
            self._text_cache = {
                path: value for path, value in self._text_cache.items() if not path.startswith(remote_prefix)
            }

    def _acquire_transfer(self, token: CancellationToken) -> ServerTransport:
        with self._pool:
            while True:
                token.raise_if_cancelled()
                if self._closed:
                    raise TransportError("SSH 会话已关闭")
                if self._idle:
                    transport = self._idle.pop()
                    self._active.add(transport)
                    return transport
                if self._created < self.settings.max_background_transfers:
                    transport = self._factory()
                    self._created += 1
                    self._active.add(transport)
                    return transport
                self._pool.wait(timeout=0.1)

    def _release_transfer(self, transport: ServerTransport, healthy: bool) -> None:
        with self._pool:
            self._active.discard(transport)
            if healthy and not self._closed:
                self._idle.append(transport)
            else:
                transport.close()
                self._created = max(0, self._created - 1)
            self._pool.notify_all()

    def download_file(
        self,
        remote_path: str,
        local_path: Path,
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> Path:
        token = cancel_token or CancellationToken()
        last_error: TransportError | None = None
        for attempt in range(self.settings.reconnect_attempts + 1):
            token.raise_if_cancelled()
            transport = self._acquire_transfer(token)
            try:
                result = transport.download_file(remote_path, local_path, progress_callback, token)
            except TransferCancelled:
                self._release_transfer(transport, healthy=False)
                raise
            except TransportError as exc:
                last_error = exc
                self._release_transfer(transport, healthy=False)
                if attempt >= self.settings.reconnect_attempts:
                    raise
            else:
                self._release_transfer(transport, healthy=True)
                return result
        raise last_error or TransportError("文件传输重连失败")

    def close(self) -> None:
        with self._browse_lock:
            self._closed = True
            if self._browse_transport is not None:
                self._browse_transport.close()
                self._browse_transport = None
        with self._pool:
            transports = [*self._idle, *self._active]
            self._idle.clear()
            self._active.clear()
            self._created = 0
            self._pool.notify_all()
        for transport in transports:
            transport.close()
        self.invalidate()
