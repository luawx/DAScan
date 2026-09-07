from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _GraphicsView(QGraphicsView):
    MIN_SCALE = 0.3
    MAX_SCALE = 8.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._last_pos = QPoint()

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        current = self.transform().m11()
        target = max(self.MIN_SCALE, min(self.MAX_SCALE, current * factor))
        if current:
            self.scale(target / current, target / current)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._last_pos = event.position().toPoint()
        super().mousePressEvent(event)


class ImageViewerWidget(QWidget):
    previous_requested = Signal()
    next_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.view = _GraphicsView(self)
        self.view.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        self._has_image = False
        self._pixmap_cache: OrderedDict[Path, QPixmap] = OrderedDict()

        previous = QPushButton("← 上一张")
        previous.setToolTip("键盘方向键 ←")
        previous.clicked.connect(self.previous_requested)
        next_button = QPushButton("下一张 →")
        next_button.setToolTip("键盘方向键 →")
        next_button.clicked.connect(self.next_requested)
        fit = QPushButton("适应窗口")
        fit.clicked.connect(self.fit_to_window)
        actual = QPushButton("100%")
        actual.clicked.connect(self.actual_size)
        toolbar = QHBoxLayout()
        toolbar.addWidget(previous)
        toolbar.addWidget(next_button)
        toolbar.addStretch()
        toolbar.addWidget(fit)
        toolbar.addWidget(actual)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(toolbar)
        layout.addWidget(self.view, 1)

    def load_image(self, path: Path) -> None:
        resolved = path.resolve()
        pixmap = self._pixmap_cache.pop(resolved, None)
        if pixmap is None:
            pixmap = QPixmap(str(resolved))
            if pixmap.isNull():
                raise ValueError(f"图片无法加载: {path}")
        self._pixmap_cache[resolved] = pixmap
        while len(self._pixmap_cache) > 3:
            self._pixmap_cache.popitem(last=False)
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(self.pixmap_item.boundingRect())
        self._has_image = True
        self.fit_to_window()

    def fit_to_window(self) -> None:
        if self._has_image:
            self.view.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            current = self.view.transform().m11()
            if current < self.view.MIN_SCALE:
                self.view.resetTransform()
                self.view.scale(self.view.MIN_SCALE, self.view.MIN_SCALE)

    def actual_size(self) -> None:
        self.view.resetTransform()
