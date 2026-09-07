from __future__ import annotations

from pathlib import Path, PurePosixPath
from time import monotonic

import paramiko

from .base import (
    CancellationToken,
    ProgressCallback,
    TransferCancelled,
    TransferProgress,
    TransportError,
)


class SFTPTransport:
    """Small SFTP adapter, intentionally independent from UI and services."""

    def __init__(self, client: paramiko.SFTPClient):
        self._client = client

    def download_file(
        self,
        remote_path: str,
        local_path: Path,
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> Path:
        started_at = monotonic()
        last_emitted_at = 0.0
        token = cancel_token or CancellationToken()
        temporary = local_path.with_suffix(local_path.suffix + ".part")

        def report(transferred: int, total: int) -> None:
            nonlocal last_emitted_at
            token.raise_if_cancelled()
            now = monotonic()
            if progress_callback is None or (transferred < total and now - last_emitted_at < 0.1):
                return
            elapsed = max(now - started_at, 0.001)
            speed = transferred / elapsed
            remaining = max(total - transferred, 0)
            progress_callback(
                TransferProgress(
                    remote_path=remote_path,
                    transferred_bytes=transferred,
                    total_bytes=total,
                    percent=(transferred / total * 100.0) if total else 0.0,
                    speed_bps=speed,
                    eta_seconds=(remaining / speed) if speed > 0 else None,
                )
            )
            last_emitted_at = now

        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            token.raise_if_cancelled()
            if progress_callback:
                progress_callback(TransferProgress(remote_path, 0, 0, 0.0, 0.0, None))
            self._client.get(remote_path, str(temporary), callback=report)
            token.raise_if_cancelled()
            temporary.replace(local_path)
            size = local_path.stat().st_size
            if progress_callback:
                elapsed = max(monotonic() - started_at, 0.001)
                progress_callback(
                    TransferProgress(
                        remote_path,
                        size,
                        size,
                        100.0,
                        size / elapsed,
                        0.0,
                        status="completed",
                    )
                )
            return local_path
        except TransferCancelled:
            temporary.unlink(missing_ok=True)
            raise
        except (OSError, paramiko.SSHException) as exc:
            temporary.unlink(missing_ok=True)
            raise TransportError(f"PNG 下载失败: {remote_path}: {exc}") from exc

    def list_files(self, remote_path: str) -> list[str]:
        try:
            base = PurePosixPath(remote_path)
            return [str(base / name) for name in self._client.listdir(remote_path)]
        except OSError as exc:
            raise TransportError(f"无法列出服务器目录 {remote_path}: {exc}") from exc

    def read_text(self, remote_path: str) -> str:
        try:
            with self._client.open(remote_path, "r") as stream:
                data = stream.read()
            return data.decode("utf-8") if isinstance(data, bytes) else data
        except OSError as exc:
            raise TransportError(f"无法读取服务器文件 {remote_path}: {exc}") from exc
