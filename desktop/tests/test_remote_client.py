from datetime import datetime

from plotdas_client.config import AppSettings
from plotdas_client.models import PlotRequest
from plotdas_client.services import PlotDasRemoteClient
from plotdas_client.transport import CommandResult, ServerTransport


class FakeTransport(ServerTransport):
    def __init__(self, response='{"image":"/remote/a.png","metadata":"/remote/a.json"}'):
        self.response = response
        self.commands = []

    def test_connection(self):
        pass

    def close(self):
        pass

    def download_file(self, remote_path, local_path, progress_callback=None, cancel_token=None):
        return local_path

    def list_files(self, remote_path):
        return [f"{remote_path}/20230308", f"{remote_path}/index.lock", f"{remote_path}/20230301"]

    def read_text(self, remote_path):
        return "[]"

    def run_command(self, command, timeout=None):
        self.commands.append(command)
        return CommandResult(self.response, "", 0)


def test_preview_builds_quoted_cli_and_parses_json():
    transport = FakeTransport()
    settings = AppSettings(project_path="/srv/Plot Das", cli_command="plotdas")
    client = PlotDasRemoteClient(transport, settings)
    result = client.preview(
        PlotRequest(
            project="xinjing",
            start_time=datetime(2023, 3, 8, 12, 0),
            end_time=datetime(2023, 3, 8, 12, 1),
            channel_start=390,
            channel_end=882,
            filter_type="bandpass",
            lowcut=2,
            highcut=40,
            dpi=200,
        )
    )
    assert result["image"] == "/remote/a.png"
    command = transport.commands[0]
    assert "cd '/srv/Plot Das'" in command
    assert "--channel-start 390" in command
    assert "--filter bandpass" in command
    assert "--overwrite" in command


def test_list_dates_only_returns_date_names():
    transport = FakeTransport()
    client = PlotDasRemoteClient(transport, AppSettings())
    assert client.list_dates("/output/xinjing") == ["20230301", "20230308"]
