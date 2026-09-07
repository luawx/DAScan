from __future__ import annotations

from pathlib import Path

import paramiko

from plotdas_client.config import AppSettings

from .base import CancellationToken, CommandResult, ProgressCallback, ServerTransport, TransportError
from .sftp import SFTPTransport


class SSHTransport(ServerTransport):
    def __init__(self, settings: AppSettings, password: str | None = None):
        self.settings = settings
        self.password = password or None
        self._client: paramiko.SSHClient | None = None
        self._sftp: SFTPTransport | None = None

    def _connect(self) -> paramiko.SSHClient:
        if self._client is not None:
            transport = self._client.get_transport()
            if transport and transport.is_active():
                return self._client

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        hostname = self.settings.server_host
        port = self.settings.ssh_port
        username = self.settings.username or None
        key_filename = self.settings.private_key_path.strip() or None
        ssh_config_path = Path.home() / ".ssh" / "config"
        if ssh_config_path.exists():
            with ssh_config_path.open(encoding="utf-8") as stream:
                host_config = paramiko.SSHConfig.from_file(stream).lookup(hostname)
            hostname = host_config.get("hostname", hostname)
            username = username or host_config.get("user")
            if self.settings.ssh_port == AppSettings().ssh_port and host_config.get("port"):
                port = int(host_config["port"])
            if key_filename is None and host_config.get("identityfile"):
                key_filename = host_config["identityfile"][0]
        try:
            client.connect(
                hostname=hostname,
                port=port,
                username=username,
                password=self.password,
                key_filename=key_filename,
                timeout=self.settings.connect_timeout,
                auth_timeout=self.settings.connect_timeout,
                banner_timeout=self.settings.connect_timeout,
                look_for_keys=key_filename is None,
                allow_agent=True,
            )
        except paramiko.AuthenticationException as exc:
            raise TransportError("SSH 认证失败，请检查用户名、密码或私钥") from exc
        except paramiko.BadHostKeyException as exc:
            raise TransportError("服务器主机密钥与本机 known_hosts 不匹配") from exc
        except (paramiko.SSHException, TimeoutError, OSError) as exc:
            raise TransportError(f"服务器无法连接: {type(exc).__name__}: {exc}") from exc
        self._client = client
        transport = client.get_transport()
        if transport and self.settings.keepalive_interval > 0:
            transport.set_keepalive(self.settings.keepalive_interval)
        return client

    def test_connection(self) -> None:
        result = self.run_command("printf connection-ok", timeout=self.settings.connect_timeout)
        if result.stdout != "connection-ok":
            raise TransportError("SSH 已连接，但服务器握手响应异常")

    def run_command(self, command: str, timeout: float | None = None) -> CommandResult:
        client = self._connect()
        try:
            _, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            return CommandResult(
                stdout.read().decode("utf-8", errors="replace"),
                stderr.read().decode("utf-8", errors="replace"),
                exit_code,
            )
        except (paramiko.SSHException, TimeoutError, OSError) as exc:
            self.close()
            raise TransportError(f"SSH 命令执行失败: {type(exc).__name__}: {exc}") from exc

    def _sftp_transport(self) -> SFTPTransport:
        if self._sftp is None:
            try:
                self._sftp = SFTPTransport(self._connect().open_sftp())
            except (paramiko.SSHException, OSError) as exc:
                raise TransportError(f"SFTP 初始化失败: {exc}") from exc
        return self._sftp

    def download_file(
        self,
        remote_path: str,
        local_path: Path,
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> Path:
        return self._sftp_transport().download_file(remote_path, local_path, progress_callback, cancel_token)

    def list_files(self, remote_path: str) -> list[str]:
        return self._sftp_transport().list_files(remote_path)

    def read_text(self, remote_path: str) -> str:
        return self._sftp_transport().read_text(remote_path)

    def close(self) -> None:
        self._sftp = None
        if self._client is not None:
            self._client.close()
            self._client = None
