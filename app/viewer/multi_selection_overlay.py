from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject


class MultiSelectionOverlay(QGraphicsObject):
    """Visual-only per-item selection indicators for multiple annotations."""

    HANDLE_RADIUS_PIXELS = 5.0
    PADDING_PIXELS = 3.0

    def __init__(self, view):
        super().__init__()
        self.view = view
        self._entries = []
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, False)
        self.setZValue(9990.0)
        self.setVisible(False)

    def _scene_units(self, pixels):
        scale = abs(float(self.view.transform().m11()))
        if scale < 1e-6:
            scale = 1.0
        return float(pixels) / scale

    def clear(self):
        self.prepareGeometryChange()
        self._entries = []
        self.setVisible(False)
        self.update()

    def set_items(self, items, active_item=None):
        valid = [
            item for item in items
            if item is not None and item.scene() is not None
        ]
        self.prepareGeometryChange()
        self._entries = []

        if len(valid) < 2:
            self.setVisible(False)
            self.update()
            return

        padding = self._scene_units(self.PADDING_PIXELS)
        for item in valid:
            rect = item.sceneBoundingRect().normalized().adjusted(
                -padding, -padding, padding, padding
            )
            self._entries.append({
                "rect": rect,
                "active": item is active_item,
            })

        if not any(entry["active"] for entry in self._entries):
            self._entries[-1]["active"] = True

        self.setVisible(True)
        self.update()

    def refresh(self):
        scene = self.scene()
        if scene is None:
            self.clear()
            return
        try:
            selected = [
                item for item in scene.selectedItems()
                if hasattr(item, "record")
            ]
        except RuntimeError:
            self.clear()
            return
        self.set_items(
            selected,
            getattr(self.view, "_active_selection_item", None),
        )

    def boundingRect(self):
        if not self._entries:
            return QRectF()
        result = QRectF()
        pad = self._scene_units(self.HANDLE_RADIUS_PIXELS + 3.0)
        for entry in self._entries:
            rect = entry["rect"].adjusted(-pad, -pad, pad, pad)
            result = rect if result.isNull() else result.united(rect)
        return result

    def paint(self, painter, option, widget=None):
        if len(self._entries) < 2:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        radius = self._scene_units(self.HANDLE_RADIUS_PIXELS)

        for entry in self._entries:
            rect = entry["rect"]
            color = (
                QColor(40, 120, 230)
                if entry["active"]
                else QColor(125, 135, 150)
            )

            pen = QPen(color, 1.0, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            handle_pen = QPen(color, 1.0)
            handle_pen.setCosmetic(True)
            painter.setPen(handle_pen)
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            for point in (
                rect.topLeft(),
                rect.topRight(),
                rect.bottomLeft(),
                rect.bottomRight(),
            ):
                painter.drawEllipse(point, radius, radius)
