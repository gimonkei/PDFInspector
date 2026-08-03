from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject


class SelectionOverlay(QGraphicsObject):
    """Central selection border and resize-handle layer."""

    HANDLE_RADIUS = 6.0
    HIT_RADIUS = 12.0
    MIN_SIZE = 8.0

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.target = None
        self._geometry = QRectF()
        self._handles = {}
        self._active_handle = None
        self._fixed_anchor = None
        self._before_snapshot = None

        self.setZValue(10000.0)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, False)
        self.setVisible(False)

    def clear_target(self):
        self.prepareGeometryChange()
        self.target = None
        self._geometry = QRectF()
        self._handles = {}
        self.setVisible(False)
        self.update()

    def set_target(self, target):
        self.target = target
        if target is None:
            self.clear_target()
        else:
            self.setVisible(True)
            self.refresh_geometry()

    def _record_type(self):
        if self.target is None:
            return ""
        return str(getattr(self.target, "record", {}).get("type", ""))

    def refresh_geometry(self):
        if self.target is None or self.target.scene() is None:
            self.clear_target()
            return

        self.prepareGeometryChange()
        record_type = self._record_type()

        if record_type == "arrow" and hasattr(self.target, "_vector"):
            start = self.target.mapToScene(QPointF(0.0, 0.0))
            end = self.target.mapToScene(self.target._vector())
            self._geometry = QRectF(start, end).normalized()
            self._handles = {
                "arrow_start": start,
                "arrow_end": end,
            }
        elif record_type == "date_stamp" and hasattr(
            self.target,
            "_stamp_rect",
        ):
            self._geometry = self.target.mapRectToScene(
                self.target._stamp_rect()
            )
            self._set_corner_handles()
        elif record_type in {"rectangle", "ellipse"} and hasattr(
            self.target,
            "_rect",
        ):
            self._geometry = self.target.mapRectToScene(
                self.target._rect()
            )
            self._set_corner_handles()
        else:
            self._geometry = self.target.sceneBoundingRect()
            self._handles = {}

        self.setVisible(True)
        self.update()

    def _set_corner_handles(self):
        rect = self._geometry
        self._handles = {
            "top_left": rect.topLeft(),
            "top_right": rect.topRight(),
            "bottom_left": rect.bottomLeft(),
            "bottom_right": rect.bottomRight(),
        }

    def _scene_units(self, pixels):
        scale = abs(float(self.view.transform().m11()))
        if scale < 1e-6:
            scale = 1.0
        return float(pixels) / scale

    def handle_at_scene_point(self, scene_point):
        if self.target is None or not self.isVisible():
            return None
        return self._handle_at(self.mapFromScene(scene_point))

    def boundingRect(self):
        if self.target is None:
            return QRectF()

        rect = QRectF(self._geometry)
        pad = self._scene_units(self.HIT_RADIUS + 3.0)
        for point in self._handles.values():
            rect = rect.united(
                QRectF(
                    point.x() - pad,
                    point.y() - pad,
                    pad * 2.0,
                    pad * 2.0,
                )
            )
        return rect.adjusted(-2.0, -2.0, 2.0, 2.0)

    def shape(self):
        path = QPainterPath()
        radius = self._scene_units(self.HIT_RADIUS)
        for point in self._handles.values():
            path.addEllipse(
                point,
                radius,
                radius,
            )
        return path

    def paint(self, painter, option, widget=None):
        if self.target is None:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(
            QPen(
                QColor(40, 120, 230),
                1.0,
                Qt.PenStyle.DashLine,
            )
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self._record_type() != "arrow":
            painter.drawRect(self._geometry)

        painter.setPen(
            QPen(
                QColor(40, 120, 230),
                self._scene_units(1.0),
            )
        )
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        radius = self._scene_units(self.HANDLE_RADIUS)
        for point in self._handles.values():
            painter.drawEllipse(
                point,
                radius,
                radius,
            )

    def _handle_at(self, point):
        best_name = None
        best_distance = None
        radius = self._scene_units(self.HIT_RADIUS)
        radius_squared = radius * radius
        for name, handle in self._handles.items():
            dx = point.x() - handle.x()
            dy = point.y() - handle.y()
            distance = dx * dx + dy * dy
            if distance <= radius_squared:
                if best_distance is None or distance < best_distance:
                    best_name = name
                    best_distance = distance
        return best_name

    def hoverMoveEvent(self, event):
        handle = self._handle_at(event.pos())
        if handle is None:
            self.unsetCursor()
        elif handle.startswith("arrow_"):
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        event.accept()

    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return

        handle = self._handle_at(event.pos())
        if handle is None or self.target is None:
            event.ignore()
            return

        self._active_handle = handle
        self._before_snapshot = self.view._history_snapshot()

        if handle == "arrow_start":
            self._fixed_anchor = self.target.mapToScene(
                self.target._vector()
            )
        elif handle == "arrow_end":
            self._fixed_anchor = self.target.mapToScene(
                QPointF(0.0, 0.0)
            )
        else:
            self._fixed_anchor = {
                "top_left": self._geometry.bottomRight(),
                "top_right": self._geometry.bottomLeft(),
                "bottom_left": self._geometry.topRight(),
                "bottom_right": self._geometry.topLeft(),
            }[handle]

        event.accept()

    def mouseMoveEvent(self, event):
        if self._active_handle is None or self.target is None:
            event.ignore()
            return

        current = event.scenePos()
        record_type = self._record_type()

        if record_type == "arrow":
            self._resize_arrow(current)
        elif record_type == "date_stamp":
            self._resize_date_stamp(current)
        elif record_type in {"rectangle", "ellipse"}:
            self._resize_shape(current)

        self.view._sync_annotation_records()
        self.refresh_geometry()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._active_handle is None:
            event.ignore()
            return

        self.view._sync_annotation_records()
        self.view._commit_history_change(self._before_snapshot)
        self._active_handle = None
        self._fixed_anchor = None
        self._before_snapshot = None
        self.refresh_geometry()
        event.accept()

    def _resize_arrow(self, current):
        if self._active_handle == "arrow_end":
            start = QPointF(self._fixed_anchor)
            vector = current - start
            self.target.prepareGeometryChange()
            self.target.record["dx"] = float(vector.x())
            self.target.record["dy"] = float(vector.y())
            self.target.update()
            return

        fixed_end = QPointF(self._fixed_anchor)
        self.target.setPos(current)
        local_end = self.target.mapFromScene(fixed_end)
        self.target.prepareGeometryChange()
        self.target.record["dx"] = float(local_end.x())
        self.target.record["dy"] = float(local_end.y())
        self.target.update()

    def _scene_rect_from_anchor(self, current):
        anchor = QPointF(self._fixed_anchor)
        left = min(anchor.x(), current.x())
        top = min(anchor.y(), current.y())
        right = max(anchor.x(), current.x())
        bottom = max(anchor.y(), current.y())

        if right - left < self.MIN_SIZE:
            if current.x() < anchor.x():
                left = anchor.x() - self.MIN_SIZE
            else:
                right = anchor.x() + self.MIN_SIZE

        if bottom - top < self.MIN_SIZE:
            if current.y() < anchor.y():
                top = anchor.y() - self.MIN_SIZE
            else:
                bottom = anchor.y() + self.MIN_SIZE

        return QRectF(
            QPointF(left, top),
            QPointF(right, bottom),
        ).normalized()

    def _resize_shape(self, current):
        rect = self._scene_rect_from_anchor(current)
        self.target.prepareGeometryChange()
        self.target.setPos(rect.topLeft())
        self.target.record["width"] = float(rect.width())
        self.target.record["height"] = float(rect.height())
        self.target.update()

    def _resize_date_stamp(self, current):
        anchor = QPointF(self._fixed_anchor)
        dx = current.x() - anchor.x()
        dy = current.y() - anchor.y()
        side = max(abs(dx), abs(dy), 42.0)

        left = anchor.x() - side if dx < 0 else anchor.x()
        top = anchor.y() - side if dy < 0 else anchor.y()
        rect = QRectF(left, top, side, side)

        self.target.prepareGeometryChange()
        self.target.setPos(rect.center())
        self.target.record["size"] = float(side)
        self.target.update()
