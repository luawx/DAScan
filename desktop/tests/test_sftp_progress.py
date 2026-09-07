from pathlib import Path
from time import sleep

import pytest

from plotdas_client.transport import CancellationToken, TransferCancelled
from plotdas_client.transport.sftp import SFTPTransport


class FakeSFTPClient:
    def get(self, remote_path, local_path, callback):
        Path(local_path).write_bytes(b"x" * 100)
        for transferred in (25, 50, 75, 100):
            sleep(0.11)
            callback(transferred, 100)


def test_sftp_progress_is_monotonic_and_completes(tmp_path):
    events = []
    target = tmp_path / "image.png"
    SFTPTransport(FakeSFTPClient()).download_file("/remote/image.png", target, events.append)
    percentages = [event.percent for event in events]
    assert percentages == sorted(percentages)
    assert percentages[-1] == 100
    assert events[-1].status == "completed"
    assert events[-1].eta_seconds == 0
    assert all(event.speed_bps > 0 for event in events if event.transferred_bytes)


def test_cancel_removes_partial_file(tmp_path):
    token = CancellationToken()
    target = tmp_path / "image.png"

    def cancel_after_first_chunk(event):
        if event.transferred_bytes:
            token.cancel()

    with pytest.raises(TransferCancelled):
        SFTPTransport(FakeSFTPClient()).download_file(
            "/remote/image.png", target, cancel_after_first_chunk, token
        )
    assert not target.exists()
    assert not target.with_suffix(".png.part").exists()
