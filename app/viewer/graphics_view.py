from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QGraphicsView


class GraphicsView(QGraphicsView):
    zoom_changed = Signal(float)

    MIN_ZOOM = 0.10
    MAX_ZOOM = 8.00

    def __init__(self):
        super().__init__()
        self.zoom_factor = 1.0
        self._dragging = False
        self._last_mouse_pos = QPoint()
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def set_zoom(self, zoom_factor: float):
        zoom_factor = max(self.MIN_ZOOM, min(float(zoom_factor), self.MAX_ZOOM))
        self.resetTransform()
        self.scale(zoom_factor, zoom_factor)
        self.zoom_factor = zoom_factor
        self.zoom_changed.emit(self.zoom_factor)

    def fit_to_width(self, margin: int = 24) -> bool:
        scene_rect = self.scene.itemsBoundingRect()

        if scene_rect.isEmpty() or scene_rect.width() <= 0:
            return False

        available_width = self.viewport().width() - margin
        if available_width <= 0:
            return False

        zoom_factor = available_width / scene_rect.width()
        self.set_zoom(zoom_factor)
        self.horizontalScrollBar().setValue(0)
        return True

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._last_mouse_pos = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            current = event.position().toPoint()
            delta = current - self._last_mouse_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._last_mouse_pos = current
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        modifiers = event.modifiers()

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if delta > 0 else 0.85
            new_zoom = self.zoom_factor * factor
            if self.MIN_ZOOM <= new_zoom <= self.MAX_ZOOM:
                self.scale(factor, factor)
                self.zoom_factor = new_zoom
                self.zoom_changed.emit(self.zoom_factor)
            event.accept()
            return

        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta)
            event.accept()
            return

        self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta)
        event.accept()
