from pathlib import Path

from PySide6.QtWidgets import QWidget

from plotdas_client.services import TransferEvent
from plotdas_client.transport import TransferProgress
from plotdas_client.ui.main_window import MainWindow


def test_main_window_starts(qtbot, tmp_path: Path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "projects.yaml").write_text("projects: []\n", encoding="utf-8")
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    assert window.windowTitle() == "DAScan"
    assert window.navigation.currentItem().text() == "图片"
    assert window.stack.count() == 5
    assert window.image_page.progress.isHidden()
    window.image_page.focus_button.setChecked(True)
    assert window.navigation.isHidden()
    assert window.image_page.browser_panel.isHidden()
    assert window.image_page.metadata_panel.isHidden()
    window.image_page.focus_button.setChecked(False)
    assert not window.navigation.isHidden()
    window.image_page.current_task_id = "task"
    window.image_page._on_task_updated(
        TransferEvent(
            "task",
            "key",
            "image.png",
            True,
            "transferring",
            TransferProgress("/image.png", 50, 100, 50.0, 1024.0, 1.0),
        )
    )
    assert window.image_page.progress.value() == 50
    assert not window.image_page.progress.isHidden()
    assert "KiB/s" in window.image_page.progress_detail.text()
    window.image_page._set_complete("下载完成")
    assert window.image_page.progress.value() == 100
    assert window.image_page.progress.isHidden()
    assert window.image_page.progress_detail.isHidden()
    assert window.image_page.cancel_button.isHidden()
    window.image_page._set_busy("正在下载…")
    assert not window.image_page.progress.isHidden()
    window.image_page.current_task_id = None
    window.image_page.task_context["prefetch"] = (window.image_page.generation, 1)
    window.image_page.row_tasks[1] = "prefetch"
    window.image_page._on_task_updated(
        TransferEvent("prefetch", "key-2", "prefetch.png", False, "cancelled")
    )
    assert "prefetch" not in window.image_page.task_context
    assert 1 not in window.image_page.row_tasks
    assert window.image_page.queue_table.isHidden()
    window.image_page.records = [{"image_path": str(index)} for index in range(5)]
    window.settings_page.prefetch_count.setValue(2)
    window.settings_page._save()
    assert window.image_page._prefetch_count == 2
    assert window.image_page._prefetch_rows(2) == [3, 1, 4, 0]
    assert window.settings_store.load().prefetch_count == 2
    assert window.image_page.previous_shortcut.key().toString() == "Left"
    assert window.image_page.next_shortcut.key().toString() == "Right"
    metadata_options = window.settings_page.findChild(QWidget, "metadataOptions")
    metadata_layout = metadata_options.layout()
    assert metadata_layout.count() == 5
    assert {metadata_layout.getItemPosition(index)[0] for index in range(5)} == {0, 1}
    window.image_page.images.blockSignals(True)
    window.image_page.images.addItems([str(index) for index in range(5)])
    window.image_page.images.setCurrentRow(2)
    window.image_page.images.blockSignals(False)
    window.image_page.next_shortcut.activated.emit()
    assert window.image_page.images.currentRow() == 3
    window.image_page.previous_shortcut.activated.emit()
    assert window.image_page.images.currentRow() == 2
