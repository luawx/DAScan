import json
from pathlib import Path

from plotdas_client.cache import CacheManager

from plotdas_client.services import ImageService
from plotdas_client.transport import CommandResult, ServerTransport


class FakeTransfer(ServerTransport):
    def __init__(self):
        self.downloaded = []

    def test_connection(self):
        pass

    def run_command(self, command, timeout=None):
        return CommandResult("", "", 0)

    def download_file(self, remote_path: str, local_path: Path, progress_callback=None, cancel_token=None):
        self.downloaded.append(remote_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"png")
        return local_path

    def list_files(self, remote_path):
        return []

    def read_text(self, remote_path):
        return json.dumps({"status": "success", "metadata_path": remote_path})

    def close(self):
        pass


def test_project_output_resolves_index_relative_image(tmp_path):
    transport = FakeTransfer()
    service = ImageService(transport, CacheManager(tmp_path))
    result = service.fetch_index_record(
        "xinjing",
        "/cluster/PlotDas/output/xinjing",
        {
            "image_path": "xinjing/20230308/images/a.png",
            "metadata_path": "/cluster/PlotDas/output/xinjing/20230308/metadata/a.json",
        },
    )
    assert result.remote_image_path == "/cluster/PlotDas/output/xinjing/20230308/images/a.png"
    assert transport.downloaded == [result.remote_image_path]
    cache_events = []
    cached = service.fetch_index_record(
        "xinjing",
        "/cluster/PlotDas/output/xinjing",
        {
            "image_path": "xinjing/20230308/images/a.png",
            "metadata_path": "/cluster/PlotDas/output/xinjing/20230308/metadata/a.json",
        },
        cache_events.append,
    )
    assert cached.local_image_path == result.local_image_path
    assert transport.downloaded == [result.remote_image_path]
    assert cache_events[-1].is_cached
    assert cache_events[-1].percent == 100
