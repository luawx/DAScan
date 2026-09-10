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


def test_clicking_fit_to_window_again_restores_previous_view(qtbot):
    viewer = ImageViewerWidget()
    qtbot.addWidget(viewer)
    viewer.resize(640, 480)
    viewer.pixmap_item.setPixmap(QPixmap(2000, 2000))
    viewer.scene.setSceneRect(viewer.pixmap_item.boundingRect())
    viewer._has_image = True
    viewer.view.resetTransform()
    viewer.view.scale(0.75, 0.75)

    viewer.fit_to_window()

    assert viewer.view.transform().m11() != pytest.approx(0.75)

    viewer.fit_to_window()

    assert viewer.view.transform().m11() == pytest.approx(0.75)


def test_clicking_actual_size_again_restores_previous_view(qtbot):
    viewer = ImageViewerWidget()
    qtbot.addWidget(viewer)
    viewer.resize(640, 480)
    viewer.pixmap_item.setPixmap(QPixmap(2000, 2000))
    viewer.scene.setSceneRect(viewer.pixmap_item.boundingRect())
    viewer._has_image = True
    viewer.view.scale(0.75, 0.75)

    viewer.actual_size()

    assert viewer.view.transform().m11() == pytest.approx(1.0)

    viewer.actual_size()

    assert viewer.view.transform().m11() == pytest.approx(0.75)


def test_switching_view_actions_uses_the_current_view_as_restore_point(qtbot):
    viewer = ImageViewerWidget()
    qtbot.addWidget(viewer)
    viewer.resize(640, 480)
    viewer.pixmap_item.setPixmap(QPixmap(2000, 2000))
    viewer.scene.setSceneRect(viewer.pixmap_item.boundingRect())
    viewer._has_image = True
    viewer.view.scale(0.75, 0.75)

    viewer.fit_to_window()
    fitted_scale = viewer.view.transform().m11()
    viewer.actual_size()
    viewer.actual_size()

    assert viewer.view.transform().m11() == pytest.approx(fitted_scale)
