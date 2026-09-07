from pathlib import Path

from plotdas_client.config import AppSettings
from plotdas_client.models import ImageRecord, Project
from plotdas_client.services import AnnotationService, HistoryService, ViewHistoryEntry
from plotdas_client.ui.image_page import ImagePage


def test_favorite_on_current_date_selects_exact_image(qtbot, tmp_path: Path):
    project = Project("xinjing", "/input", "/output", "xinjing")
    page = ImagePage(
        [project],
        lambda *_args: ["20230301"],
        lambda *_args: [],
        lambda _project, record, *_args: ImageRecord(
            "xinjing", str(record["image_path"])
        ),
        lambda: "",
        AppSettings(active_project="xinjing", data_source="/output"),
        AnnotationService(tmp_path / "annotations.json"),
        HistoryService(tmp_path / "history.json"),
    )
    qtbot.addWidget(page)
    page.dates.addItem("20230301")
    page.dates.blockSignals(True)
    page.dates.setCurrentRow(0)
    page.dates.blockSignals(False)
    page._all_records = [
        {"image_path": "/output/20230301/a.png"},
        {"image_path": "/output/20230301/b.png"},
    ]
    page.only_favorites.blockSignals(True)
    page.only_favorites.setChecked(True)
    page.only_favorites.blockSignals(False)

    page._open_history(
        ViewHistoryEntry("xinjing", "20230301", "/output/20230301/b.png", "now")
    )

    assert not page.only_favorites.isChecked()
    assert page.images.currentRow() == 1
    assert page.records[page.images.currentRow()]["image_path"].endswith("b.png")
    page.close_transfers()
