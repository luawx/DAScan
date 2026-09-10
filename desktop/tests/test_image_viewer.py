import pytest
from PySide6.QtGui import QPixmap

from plotdas_client.ui.image_viewer import ImageViewerWidget


def test_fit_to_window_never_scales_below_30_percent(qtbot):
    viewer = ImageViewerWidget()
    qtbot.addWidget(viewer)
    viewer.resize(160, 120)
    viewer.pixmap_item.setPixmap(QPixmap(2000, 2000))
    viewer.scene.setSceneRect(viewer.pixmap_item.boundingRect())
    viewer._has_image = True

    viewer.fit_to_window()

    assert viewer.view.MIN_SCALE == pytest.approx(0.3)
    assert viewer.view.transform().m11() == pytest.approx(0.3)


def test_fit_to_window_can_be_undone(qtbot):
    viewer = ImageViewerWidget()
    qtbot.addWidget(viewer)
    viewer.resize(640, 480)
    viewer.pixmap_item.setPixmap(QPixmap(2000, 2000))
    viewer.scene.setSceneRect(viewer.pixmap_item.boundingRect())
    viewer._has_image = True
    viewer.view.resetTransform()
    viewer.view.scale(0.75, 0.75)

    viewer.fit_to_window()

    assert viewer.undo_button.isEnabled()
    assert viewer.view.transform().m11() != pytest.approx(0.75)

    viewer.undo_view_change()

    assert viewer.view.transform().m11() == pytest.approx(0.75)
    assert not viewer.undo_button.isEnabled()


def test_actual_size_and_fit_to_window_can_be_undone_in_order(qtbot):
    viewer = ImageViewerWidget()
    qtbot.addWidget(viewer)
    viewer.resize(640, 480)
    viewer.pixmap_item.setPixmap(QPixmap(2000, 2000))
    viewer.scene.setSceneRect(viewer.pixmap_item.boundingRect())
    viewer._has_image = True
    viewer.view.scale(0.75, 0.75)

    viewer.actual_size()
    viewer.fit_to_window()
    viewer.undo_view_change()

    assert viewer.view.transform().m11() == pytest.approx(1.0)

    viewer.undo_view_change()

    assert viewer.view.transform().m11() == pytest.approx(0.75)
