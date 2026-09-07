from plotdas_client.config import AppSettings
from plotdas_client.transport import CommandResult, ServerTransport, SessionManager, TransportError


class FakeSession(ServerTransport):
    def __init__(self, fail_listing=False):
        self.fail_listing = fail_listing
        self.list_calls = 0
        self.download_calls = 0
        self.closed = False

    def test_connection(self):
        pass

    def run_command(self, command, timeout=None):
        return CommandResult("", "", 0)

    def download_file(self, remote_path, local_path, progress_callback=None, cancel_token=None):
        self.download_calls += 1
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"data")
        return local_path

    def list_files(self, remote_path):
        self.list_calls += 1
        if self.fail_listing:
            self.fail_listing = False
            raise TransportError("disconnected")
        return [f"{remote_path}/20230308"]

    def read_text(self, remote_path):
        return "{}"

    def close(self):
        self.closed = True


def test_directory_cache_and_invalidation():
    sessions = []

    def factory():
        session = FakeSession()
        sessions.append(session)
        return session

    manager = SessionManager(AppSettings(), transport_factory=factory)
    assert manager.list_files("/output") == ["/output/20230308"]
    assert manager.list_files("/output") == ["/output/20230308"]
    assert sessions[0].list_calls == 1
    manager.invalidate("/output")
    manager.list_files("/output")
    assert sessions[0].list_calls == 2
    manager.close()


def test_browse_reconnect_and_transfer_connection_reuse(tmp_path):
    sessions = []

    def factory():
        session = FakeSession(fail_listing=not sessions)
        sessions.append(session)
        return session

    manager = SessionManager(AppSettings(reconnect_attempts=2), transport_factory=factory)
    assert manager.list_files("/output") == ["/output/20230308"]
    manager.download_file("/a", tmp_path / "a")
    manager.download_file("/b", tmp_path / "b")
    transfer_sessions = [session for session in sessions if session.download_calls]
    assert len(transfer_sessions) == 1
    assert transfer_sessions[0].download_calls == 2
    manager.close()
