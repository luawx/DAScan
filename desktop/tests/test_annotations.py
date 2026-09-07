from plotdas_client.services import Annotation, AnnotationService


def test_favorites_and_notes_are_persisted(tmp_path):
    service = AnnotationService(tmp_path / "data" / "annotations.json")
    saved = service.save(
        Annotation("xinjing", "/output/a.png", favorite=True, note="疑似微震", tags=["微震"])
    )

    loaded = service.get("xinjing", "/output/a.png")
    assert loaded.favorite is True
    assert loaded.note == "疑似微震"
    assert loaded.tags == ["微震"]
    assert saved.created_at
    assert service.list_favorites("xinjing") == [loaded]


def test_empty_annotation_is_removed(tmp_path):
    service = AnnotationService(tmp_path / "annotations.json")
    service.save(Annotation("xinjing", "/output/a.png", favorite=True))
    service.save(Annotation("xinjing", "/output/a.png"))

    assert service.list_favorites() == []
    assert service.get("xinjing", "/output/a.png").updated_at == ""


def test_favorites_are_exported_by_project_and_group(tmp_path):
    service = AnnotationService(tmp_path / "annotations.json")
    service.save(
        Annotation(
            "xinjing",
            "/output/a.png",
            favorite=True,
            group="微震",
            event_start_time="2026-09-07T10:00:00",
            event_end_time="2026-09-07T10:00:30",
        )
    )
    files = service.export_favorites(tmp_path / "exports")

    assert files == [tmp_path / "exports" / "xinjing" / "微震.txt"]
    assert files[0].read_text(encoding="utf-8") == (
        "2026-09-07T10:00:00\t2026-09-07T10:00:30\n"
    )
