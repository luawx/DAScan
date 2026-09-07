from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from plotdas_client.config import AppSettings
from plotdas_client.models import PlotRequest
from plotdas_client.transport import ServerTransport, TransportError


class RemoteProtocolError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ConnectionReport:
    ssh_connected: bool
    project_exists: bool
    cli_available: bool
    cli_summary: str = ""


class PlotDasRemoteClient:
    """The only layer that knows the concrete PlotDas CLI contract."""

    def __init__(self, transport: ServerTransport, settings: AppSettings):
        self.transport = transport
        self.settings = settings

    def _in_project(self, command: str) -> str:
        return f"cd {shlex.quote(self.settings.project_path)} && {command}"

    def _run(self, arguments: list[str], timeout: float | None = None) -> Any:
        command = " ".join([self.settings.cli_command, *(shlex.quote(str(value)) for value in arguments)])
        result = self.transport.run_command(self._in_project(command), timeout=timeout)
        if result.exit_code != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.exit_code}"
            raise RemoteProtocolError(f"服务器 PlotDas 命令失败: {detail}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RemoteProtocolError(
                f"服务器返回的 JSON 格式错误: {exc}\n原始输出: {result.stdout[:1000]}"
            ) from exc

    def test_connection(self) -> ConnectionReport:
        self.transport.test_connection()
        project = self.transport.run_command(
            f"test -d {shlex.quote(self.settings.project_path)}", timeout=self.settings.connect_timeout
        )
        if project.exit_code != 0:
            raise TransportError(f"服务器 PlotDas 目录不存在: {self.settings.project_path}")
        help_result = self.transport.run_command(
            self._in_project(f"{self.settings.cli_command} --help"), timeout=30
        )
        if help_result.exit_code != 0 or "Commands:" not in help_result.stdout:
            detail = help_result.stderr.strip() or help_result.stdout.strip()
            raise TransportError(f"PlotDas CLI 不可用: {detail}")
        return ConnectionReport(True, True, True, help_result.stdout.strip())

    @staticmethod
    def _plot_arguments(request: PlotRequest) -> list[str]:
        request.validate()
        arguments = [
            "plot",
            "--project",
            request.project,
            "--start",
            request.start_time.isoformat(sep=" "),
            "--end",
            request.end_time.isoformat(sep=" "),
            "--channel-start",
            str(request.channel_start),
            "--channel-end",
            str(request.channel_end),
            "--filter",
            request.filter_type,
            "--dpi",
            str(request.dpi),
        ]
        if request.lowcut is not None and request.filter_type in {"bandpass", "highpass"}:
            arguments.extend(["--lowcut", str(request.lowcut)])
        if request.highcut is not None and request.filter_type in {"bandpass", "lowpass"}:
            arguments.extend(["--highcut", str(request.highcut)])
        return arguments

    def inspect(
        self, path: str | None = None, project: str | None = None, limit: int = 2
    ) -> list[dict[str, Any]]:
        arguments = ["inspect"]
        if path:
            arguments.append(path)
        if project:
            arguments.extend(["--project", project])
        arguments.extend(["--limit", str(limit)])
        return self._run(arguments, timeout=60)

    def preview(self, request: PlotRequest) -> dict[str, str]:
        payload = self._run([*self._plot_arguments(request), "--overwrite"], timeout=None)
        if not isinstance(payload, dict) or not payload.get("image"):
            raise RemoteProtocolError("服务器绘图成功但未返回 image 路径")
        return payload

    def create_job(self, request: PlotRequest) -> dict[str, Any]:
        arguments = [*self._plot_arguments(request)]
        arguments[0] = "create"
        arguments = ["job", *arguments, "--window-length", str(request.window_length)]
        return self._run(arguments)

    def start_job(self, job_id: str) -> dict[str, Any]:
        return self._run(["job", "start", job_id])

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._run(["job", "status", job_id])

    def list_jobs(self) -> list[dict[str, Any]]:
        return self._run(["job", "list"])

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return self._run(["job", "cancel", job_id])

    def list_dates(self, project_output: str) -> list[str]:
        entries = self.transport.list_files(project_output)
        return sorted(
            PurePosixPath(entry).name
            for entry in entries
            if len(PurePosixPath(entry).name) == 8 and PurePosixPath(entry).name.isdigit()
        )

    def list_images(self, project_output: str, date: str) -> list[dict[str, Any]]:
        index = PurePosixPath(project_output) / date / "index.json"
        try:
            payload = json.loads(self.transport.read_text(str(index)))
        except json.JSONDecodeError as exc:
            raise RemoteProtocolError(f"metadata index 格式错误: {index}: {exc}") from exc
        records = payload if isinstance(payload, list) else payload.get("images", payload.get("records", []))
        return [
            record for record in records if record.get("status") == "success" and record.get("image_path")
        ]
