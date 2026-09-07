from plotdas_client.services import HistoryService


def test_history_keeps_latest_view_and_deduplicates(tmp_path):
    service = HistoryService(tmp_path / "history.json", limit=2)
    service.record("xinjing", "20230308", "/output/a.png", "A")
    service.record("xinjing", "20230308", "/output/b.png", "B")
    service.record("xinjing", "20230308", "/output/a.png", "A again")

    recent = service.list_recent()
    assert [item.image_path for item in recent] == ["/output/a.png", "/output/b.png"]
    assert service.last_viewed().label == "A again"


def test_history_default_limit_is_100(tmp_path):
    service = HistoryService(tmp_path / "history.json")
    for index in range(105):
        service.record("xinjing", "20230308", f"/output/{index}.png")
    assert len(service.list_recent()) == 100
