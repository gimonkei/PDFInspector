from copy import deepcopy
import uuid

from PySide6.QtCore import QPointF, QRectF, QTimer, Signal, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QKeySequence, QPainter, QPainterPath, QPainterPathStroker, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QMenu,
)

from app.viewer.graphics_view import GraphicsView
from app.viewer.page_manager import PageManager
from app.viewer.selection_overlay import SelectionOverlay
from app.viewer.multi_selection_overlay import MultiSelectionOverlay
from app.annotations.date_stamp import draw_date_stamp



class CheckAnnotationItem(QGraphicsPathItem):
    MIN_SIZE = 6.0

    def __init__(self, record):
        super().__init__()
        self.record = record
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.refresh_from_record()
        self.setZValue(20.0)

    def _size(self):
        return max(float(self.record.get("size", 15.0)), self.MIN_SIZE)

    def _color(self):
        color = QColor(str(self.record.get("color", "#dc0000")))
        return color if color.isValid() else QColor(220, 0, 0)

    def _line_width(self):
        return max(float(self.record.get("line_width", 2.2)), 0.5)

    def _build_path(self):
        size = self._size()
        path = QPainterPath()
        path.moveTo(-size * 0.48, 0.0)
        path.lineTo(-size * 0.12, size * 0.38)
        path.lineTo(size * 0.55, -size * 0.48)
        return path

    def refresh_from_record(self):
        self.setPath(self._build_path())
        self.setPen(QPen(self._color(), self._line_width(), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        self.update()



class TextAnnotationItem(QGraphicsTextItem):
    def __init__(self, record):
        super().__init__(record["text"])
        self.record = record
        font = QFont()
        font.setPointSizeF(float(record.get("font_size", 11.0)))
        self.setFont(font)
        self.setDefaultTextColor(QColor(220, 0, 0))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setZValue(20.0)


class DateStampItem(QGraphicsObject):
    HANDLE_SIZE = 8.0
    MIN_SIZE = 24.0

    def __init__(self, record):
        super().__init__()
        self.record = record
        self._resizing = False
        self._resize_corner = None
        self._resize_start_scene = None
        self._resize_start_size = None
        self.setAcceptHoverEvents(True)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setZValue(21.0)

    def stamp_size(self):
        return max(float(self.record.get("size", 72.0)), self.MIN_SIZE)

    def boundingRect(self):
        size = self.stamp_size()
        pad = self.HANDLE_SIZE + 3.0
        return QRectF(-size / 2 - pad, -size / 2 - pad, size + pad * 2, size + pad * 2)

    def _stamp_rect(self):
        size = self.stamp_size()
        return QRectF(-size / 2, -size / 2, size, size)

    def _color(self):
        name = self.record.get("color", "black")
        return {
            "black": QColor(0, 0, 0),
            "blue": QColor(0, 70, 220),
            "red": QColor(220, 0, 0),
        }.get(name, QColor(0, 0, 0))

    def _handle_rects(self):
        rect = self._stamp_rect()
        hs = self.HANDLE_SIZE
        points = {
            "tl": rect.topLeft(),
            "tr": rect.topRight(),
            "bl": rect.bottomLeft(),
            "br": rect.bottomRight(),
        }
        return {
            key: QRectF(point.x() - hs / 2, point.y() - hs / 2, hs, hs)
            for key, point in points.items()
        }

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self._stamp_rect()
        draw_date_stamp(painter, rect, self.record)


    def _corner_at(self, position):
        return None

    def hoverMoveEvent(self, event):
        if self._corner_at(event.pos()) is not None:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        corner = self._corner_at(event.pos())
        if corner is not None and event.button() == Qt.MouseButton.LeftButton:
            self._resizing = True
            self._resize_corner = corner
            self._resize_start_scene = event.scenePos()
            self._resize_start_size = self.stamp_size()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta = event.scenePos() - self._resize_start_scene
            sign_x = -1.0 if "l" in self._resize_corner else 1.0
            sign_y = -1.0 if "t" in self._resize_corner else 1.0
            change = (delta.x() * sign_x + delta.y() * sign_y) / 2.0
            new_size = max(self.MIN_SIZE, self._resize_start_size + change * 2.0)
            self.prepareGeometryChange()
            self.record["size"] = float(new_size)
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            self._resize_corner = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def refresh_from_record(self):
        self.prepareGeometryChange()
        self.update()


class ArrowAnnotationItem(QGraphicsObject):
    HANDLE_RADIUS = 5.0
    HIT_PADDING = 8.0
    MIN_LENGTH = 6.0

    def __init__(self, record):
        super().__init__()
        self.record = record
        self._editing_endpoint = None
        self._drag_start_scene = None
        self._start_vector = None
        self._start_item_pos = None
        self._fixed_end_scene = None
        self.setAcceptHoverEvents(True)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

    def _vector(self):
        return QPointF(
            float(self.record.get("dx", 80.0)),
            float(self.record.get("dy", 0.0)),
        )

    def _color(self):
        color = QColor(str(self.record.get("color", "#dc0000")))
        return color if color.isValid() else QColor(220, 0, 0)

    def _line_width(self):
        return max(float(self.record.get("line_width", 2.0)), 0.5)

    def boundingRect(self):
        end = self._vector()
        pad = self.HIT_PADDING + self._line_width()
        left = min(0.0, end.x()) - pad
        top = min(0.0, end.y()) - pad
        right = max(0.0, end.x()) + pad
        bottom = max(0.0, end.y()) + pad
        return QRectF(left, top, right - left, bottom - top)

    def shape(self):
        # Give the thin arrow a practical hit area, similar to check marks.
        path = QPainterPath()
        path.moveTo(QPointF(0.0, 0.0))
        path.lineTo(self._vector())

        stroker = QPainterPathStroker()
        stroker.setWidth(max(self.HIT_PADDING * 2.0, self._line_width() + 8.0))
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return stroker.createStroke(path)

    def _arrow_head_points(self):
        end = self._vector()
        length = max((end.x() ** 2 + end.y() ** 2) ** 0.5, 0.001)
        ux = end.x() / length
        uy = end.y() / length
        head = min(max(self._line_width() * 4.2, 10.0), length * 0.45)
        wing = head * 0.52
        base_x = end.x() - ux * head
        base_y = end.y() - uy * head
        perp_x = -uy
        perp_y = ux
        return (
            QPointF(base_x + perp_x * wing, base_y + perp_y * wing),
            QPointF(base_x - perp_x * wing, base_y - perp_y * wing),
        )

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = self._color()
        pen = QPen(
            color,
            self._line_width(),
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        start = QPointF(0.0, 0.0)
        end = self._vector()
        painter.drawLine(start, end)
        wing1, wing2 = self._arrow_head_points()
        painter.drawLine(end, wing1)
        painter.drawLine(end, wing2)


    def _endpoint_at(self, pos):
        return None

    def hoverMoveEvent(self, event):
        endpoint = self._endpoint_at(event.pos())
        if endpoint is not None:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        # Endpoint handles work in every tool mode. PDFView already gives an
        # existing annotation priority over creating a new one, so dragging a
        # selected handle edits the arrow while dragging its body moves it.
        endpoint = self._endpoint_at(event.pos())
        if endpoint is not None and event.button() == Qt.MouseButton.LeftButton:
            self._editing_endpoint = endpoint
            self._drag_start_scene = event.scenePos()
            self._start_vector = self._vector()
            self._start_item_pos = QPointF(self.pos())
            self._fixed_end_scene = self.mapToScene(self._start_vector)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._editing_endpoint is None:
            super().mouseMoveEvent(event)
            return

        delta = event.scenePos() - self._drag_start_scene
        self.prepareGeometryChange()

        if self._editing_endpoint == "end":
            vector = self._start_vector + delta
            self.record["dx"] = float(vector.x())
            self.record["dy"] = float(vector.y())
        else:
            # Use the position captured at mouse press. The previous code
            # repeatedly added the total drag delta to an already moved item,
            # which made the arrow jump much farther than the cursor.
            self.setPos(self._start_item_pos + delta)
            new_vector = self.mapFromScene(self._fixed_end_scene)
            self.record["dx"] = float(new_vector.x())
            self.record["dy"] = float(new_vector.y())

        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._editing_endpoint is not None:
            self._editing_endpoint = None
            self._drag_start_scene = None
            self._start_vector = None
            self._start_item_pos = None
            self._fixed_end_scene = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def refresh_from_record(self):
        self.prepareGeometryChange()
        self.update()


class ShapeAnnotationItem(QGraphicsObject):
    HANDLE_RADIUS = 5.0
    MIN_SIZE = 8.0

    def __init__(self, record):
        super().__init__()
        self.record = record
        self._resize_handle = None
        self._resize_start_scene = None
        self._resize_start_rect = None
        self._resize_start_pos = None
        self._resize_anchor_scene = None
        self.setAcceptHoverEvents(True)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

    def _rect(self):
        return QRectF(
            0.0,
            0.0,
            max(float(self.record.get("width", 80.0)), self.MIN_SIZE),
            max(float(self.record.get("height", 50.0)), self.MIN_SIZE),
        )


    def _cloud_path(self):
        rect = self._rect()
        path = QPainterPath()

        radius = max(
            4.0,
            min(
                float(self.record.get("cloud_radius", 8.0)),
                min(rect.width(), rect.height()) / 4.0,
            ),
        )

        def edge_points(start, end):
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            length = max((dx * dx + dy * dy) ** 0.5, 0.001)
            count = max(1, int(round(length / (radius * 1.55))))
            return [
                QPointF(
                    start.x() + dx * index / count,
                    start.y() + dy * index / count,
                )
                for index in range(count + 1)
            ]

        points = (
            edge_points(rect.topLeft(), rect.topRight())
            + edge_points(rect.topRight(), rect.bottomRight())[1:]
            + edge_points(rect.bottomRight(), rect.bottomLeft())[1:]
            + edge_points(rect.bottomLeft(), rect.topLeft())[1:]
        )

        if not points:
            return path

        path.moveTo(points[0])
        center = rect.center()

        for index, current in enumerate(points):
            following = points[(index + 1) % len(points)]
            midpoint = QPointF(
                (current.x() + following.x()) * 0.5,
                (current.y() + following.y()) * 0.5,
            )
            vx = midpoint.x() - center.x()
            vy = midpoint.y() - center.y()
            distance = max((vx * vx + vy * vy) ** 0.5, 0.001)
            control = QPointF(
                midpoint.x() + vx / distance * radius * 0.62,
                midpoint.y() + vy / distance * radius * 0.62,
            )
            path.quadTo(control, following)

        path.closeSubpath()
        return path

    def _color(self):
        color = QColor(str(self.record.get("color", "#dc0000")))
        return color if color.isValid() else QColor(220, 0, 0)

    def _fill_brush(self):
        if not bool(self.record.get("fill_enabled", False)):
            return QBrush(Qt.BrushStyle.NoBrush)

        fill_value = str(self.record.get("fill_color", "#ffff00"))
        color = QColor(fill_value)
        if not color.isValid():
            color = QColor(self._color())

        opacity = min(
            max(float(self.record.get("fill_opacity", 0.25)), 0.0),
            1.0,
        )
        color.setAlphaF(opacity)
        return QBrush(color)

    def _text_font(self):
        font = QFont()
        font.setPointSizeF(max(float(self.record.get("font_size", 11.0)), 4.0))
        return font

    def _text_rect(self):
        margin = max(5.0, float(self.record.get("line_width", 2.0)) * 2.0)
        return self._rect().adjusted(margin, margin, -margin, -margin)

    def _draw_text(self, painter):
        text = str(self.record.get("text", "")).strip()
        if not text:
            return
        painter.setFont(self._text_font())
        text_value = str(
            self.record.get("text_color", "#000000")
        )
        text_color = QColor(text_value)
        if not text_color.isValid():
            text_color = QColor(self._color())
        painter.setPen(QPen(text_color))
        painter.drawText(
            self._text_rect(),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            text,
        )

    def _line_width(self):
        return max(float(self.record.get("line_width", 2.0)), 0.5)

    def boundingRect(self):
        pad = self.HANDLE_RADIUS + self._line_width() + 2.0
        return self._rect().adjusted(-pad, -pad, pad, pad)

    def shape(self):
        path = QPainterPath()
        if self.record.get("type") == "ellipse":
            path.addEllipse(self._rect())
        elif self.record.get("type") == "cloud":
            path = self._cloud_path()
        else:
            path.addRect(self._rect())

        stroker = QPainterPathStroker()
        stroker.setWidth(max(12.0, self._line_width() + 8.0))
        return stroker.createStroke(path)

    def _handles(self):
        rect = self._rect()
        return {
            "top_left": rect.topLeft(),
            "top_right": rect.topRight(),
            "bottom_left": rect.bottomLeft(),
            "bottom_right": rect.bottomRight(),
        }

    def _handle_at(self, pos):
        return None

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(
            QPen(
                self._color(),
                self._line_width(),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.setBrush(self._fill_brush())

        if self.record.get("type") == "ellipse":
            painter.drawEllipse(self._rect())
        elif self.record.get("type") == "cloud":
            painter.drawPath(self._cloud_path())
        else:
            painter.drawRect(self._rect())

        if self.record.get("type") in {"rectangle", "cloud"}:
            self._draw_text(painter)


    def hoverMoveEvent(self, event):
        if self._handle_at(event.pos()) is not None:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        handle = self._handle_at(event.pos())
        if handle is not None and event.button() == Qt.MouseButton.LeftButton:
            self._resize_handle = handle
            self._resize_start_scene = event.scenePos()
            self._resize_start_rect = QRectF(self._rect())
            self._resize_start_pos = QPointF(self.pos())

            # Keep the diagonally opposite corner fixed in scene coordinates.
            # Resizing is then calculated directly from the cursor's current
            # scene position, so the handle remains under the cursor at every
            # zoom level and for very large circles.
            opposite = {
                "top_left": self._rect().bottomRight(),
                "top_right": self._rect().bottomLeft(),
                "bottom_left": self._rect().topRight(),
                "bottom_right": self._rect().topLeft(),
            }[handle]
            self._resize_anchor_scene = self.mapToScene(opposite)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resize_handle is None:
            super().mouseMoveEvent(event)
            return

        current_scene = event.scenePos()
        anchor = QPointF(self._resize_anchor_scene)

        left = min(anchor.x(), current_scene.x())
        top = min(anchor.y(), current_scene.y())
        right = max(anchor.x(), current_scene.x())
        bottom = max(anchor.y(), current_scene.y())

        width = right - left
        height = bottom - top

        # Clamp without allowing the active handle to drift away from the
        # cursor. The fixed opposite corner remains unchanged.
        if width < self.MIN_SIZE:
            if current_scene.x() < anchor.x():
                left = anchor.x() - self.MIN_SIZE
                right = anchor.x()
            else:
                left = anchor.x()
                right = anchor.x() + self.MIN_SIZE

        if height < self.MIN_SIZE:
            if current_scene.y() < anchor.y():
                top = anchor.y() - self.MIN_SIZE
                bottom = anchor.y()
            else:
                top = anchor.y()
                bottom = anchor.y() + self.MIN_SIZE

        scene_rect = QRectF(
            QPointF(left, top),
            QPointF(right, bottom),
        ).normalized()

        self.prepareGeometryChange()
        self.setPos(scene_rect.topLeft())
        self.record["width"] = float(scene_rect.width())
        self.record["height"] = float(scene_rect.height())
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._resize_handle is not None:
            self._resize_handle = None
            self._resize_start_scene = None
            self._resize_start_rect = None
            self._resize_start_pos = None
            self._resize_anchor_scene = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def refresh_from_record(self):
        self.prepareGeometryChange()
        self.update()


class PDFView(GraphicsView):
    page_changed = Signal(int)
    visible_region_changed = Signal()
    annotation_clicked = Signal(int, QPointF)
    annotation_edit_requested = Signal(object)
    annotation_selected = Signal(object)
    undo_available_changed = Signal(bool)
    redo_available_changed = Signal(bool)
    selection_count_changed = Signal(int)

    PAGE_MARGIN = 20.0
    PREFETCH_VIEWPORTS = 0.65

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self._selection_overlay = SelectionOverlay(self)
        self.scene.addItem(self._selection_overlay)

        self._multi_selection_overlay = MultiSelectionOverlay(self)
        self.scene.addItem(self._multi_selection_overlay)
        self.scene.selectionChanged.connect(
            self._on_scene_selection_changed
        )
        self.page_manager = PageManager()
        self.pages = []
        self.current_page_index = 0
        self.single_page_mode = True

        self._page_items = {}
        self._page_origins = {}
        self._tile_items = {}
        self._active_render_scale = None
        self.annotation_mode = "hand"
        self._annotation_records = []
        self._annotation_items = []
        self._annotation_dragging = False
        self._arrow_drawing = False
        self._arrow_start_hit = None
        self._arrow_preview = None
        self._shape_drawing = False
        self._shape_start_hit = None
        self._shape_preview = None
        self._shape_kind = None

        self._date_stamp_preview_settings = {}
        self._date_stamp_preview_item = None
        self._date_stamp_preview_page = None
        self._date_stamp_preview_point = None

        self._annotation_defaults = {
            "check": {
                "color": "#dc0000",
                "size": 15.0,
                "line_width": 2.2,
            },
            "arrow": {
                "color": "#dc0000",
                "line_width": 2.0,
            },
            "rectangle": {
                "color": "#dc0000",
                "line_width": 2.0,
                "text_color": "#000000",
                "fill_enabled": False,
                "fill_opacity": 0.25,
                "fill_color": "#ffff00",
                "font_size": 11.0,
            },
            "ellipse": {
                "color": "#dc0000",
                "line_width": 2.0,
                "fill_enabled": False,
                "fill_opacity": 0.25,
                "fill_color": "#ffff00",
            },
            "cloud": {
                "color": "#dc0000",
                "line_width": 2.0,
                "text_color": "#000000",
                "fill_enabled": False,
                "fill_opacity": 0.25,
                "fill_color": "#ffff00",
                "font_size": 11.0,
            },
        }

        # Annotation undo / redo uses complete lightweight record snapshots.
        # This keeps every annotation type consistent and also covers move,
        # resize, delete, text edits, and property-panel edits.
        self._undo_stack = []
        self._redo_stack = []
        self._history_limit = 100
        self._history_suspended = False
        self._gesture_before = None
        self._property_edit_before = None

        self._annotation_clipboard = []
        self._paste_offset_step = 18.0
        self._paste_generation = 0
        self._ctrl_drag_source_item = None
        self._ctrl_drag_clone_item = None
        self._ctrl_drag_started = False
        self._multi_drag_before = None
        self._multi_dragging = False
        self._active_selection_item = None

        self._ctrl_pending_item = None
        self._ctrl_pending_start_scene = None
        self._ctrl_pending_before = None
        self._ctrl_pending_clones = []
        self._ctrl_pending_clone_positions = []
        self._ctrl_pending_dragging = False

        self._property_edit_timer = QTimer(self)
        self._property_edit_timer.setSingleShot(True)
        self._property_edit_timer.setInterval(400)
        self._property_edit_timer.timeout.connect(self.finish_property_edit)

        self._visible_signal_timer = QTimer(self)
        self._visible_signal_timer.setSingleShot(True)
        self._visible_signal_timer.setInterval(40)
        self._visible_signal_timer.timeout.connect(
            self.visible_region_changed.emit
        )

        self.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.horizontalScrollBar().valueChanged.connect(
            self._schedule_visible_region_changed
        )


    def set_annotation_defaults(self, defaults):
        if not isinstance(defaults, dict):
            return
        for annotation_type, values in defaults.items():
            if not isinstance(values, dict):
                continue
            current = self._annotation_defaults.setdefault(
                str(annotation_type),
                {},
            )
            current.update(values)

    def annotation_defaults(self, annotation_type):
        return dict(
            self._annotation_defaults.get(
                str(annotation_type),
                {},
            )
        )

    def _on_scene_selection_changed(self):
        try:
            scene = self.scene
            if scene is None:
                return
            selected = sorted(
                [
                    item
                    for item in scene.selectedItems()
                    if hasattr(item, "record")
                ],
                key=lambda item: float(
                    item.record.get("z", 0.0)
                ),
            )
        except RuntimeError:
            return

        single_overlay = getattr(self, "_selection_overlay", None)
        multi_overlay = getattr(
            self,
            "_multi_selection_overlay",
            None,
        )

        try:
            if len(selected) == 1:
                self._active_selection_item = selected[0]
                if single_overlay is not None:
                    single_overlay.set_target(selected[0])
                if multi_overlay is not None:
                    multi_overlay.clear()
            elif len(selected) > 1:
                if self._active_selection_item not in selected:
                    self._active_selection_item = selected[-1]
                if single_overlay is not None:
                    single_overlay.clear_target()
                if multi_overlay is not None:
                    multi_overlay.set_items(
                        selected,
                        self._active_selection_item,
                    )
            else:
                self._active_selection_item = None
                if single_overlay is not None:
                    single_overlay.clear_target()
                if multi_overlay is not None:
                    multi_overlay.clear()
        except RuntimeError:
            return

        self.selection_count_changed.emit(len(selected))


    def _refresh_selection_overlay(self):
        single_overlay = getattr(
            self,
            "_selection_overlay",
            None,
        )
        multi_overlay = getattr(
            self,
            "_multi_selection_overlay",
            None,
        )

        try:
            selected = self._selected_annotation_items_sorted()
        except RuntimeError:
            return

        try:
            if len(selected) == 1:
                self._active_selection_item = selected[0]
                if single_overlay is not None:
                    single_overlay.set_target(selected[0])
                    single_overlay.refresh_geometry()
                if multi_overlay is not None:
                    multi_overlay.clear()
            elif len(selected) > 1:
                if self._active_selection_item not in selected:
                    self._active_selection_item = selected[-1]
                if single_overlay is not None:
                    single_overlay.clear_target()
                if multi_overlay is not None:
                    multi_overlay.set_items(
                        selected,
                        self._active_selection_item,
                    )
            else:
                self._active_selection_item = None
                if single_overlay is not None:
                    single_overlay.clear_target()
                if multi_overlay is not None:
                    multi_overlay.clear()
        except RuntimeError:
            return


    def _detach_selection_overlay(self):
        if (
            self._selection_overlay is not None
            and self._selection_overlay.scene() is self.scene
        ):
            self.scene.removeItem(self._selection_overlay)

        if (
            self._multi_selection_overlay is not None
            and self._multi_selection_overlay.scene() is self.scene
        ):
            self.scene.removeItem(
                self._multi_selection_overlay
            )

    def _reattach_selection_overlay(self):
        if self._selection_overlay is None:
            self._selection_overlay = SelectionOverlay(self)
        if self._selection_overlay.scene() is None:
            self.scene.addItem(self._selection_overlay)
        self._selection_overlay.clear_target()

        if self._multi_selection_overlay is None:
            self._multi_selection_overlay = (
                MultiSelectionOverlay(self)
            )
        if self._multi_selection_overlay.scene() is None:
            self.scene.addItem(
                self._multi_selection_overlay
            )
        self._multi_selection_overlay.clear()
        self.selection_count_changed.emit(0)




    def _clear_ctrl_pending(self):
        self._ctrl_pending_item = None
        self._ctrl_pending_start_scene = None
        self._ctrl_pending_before = None
        self._ctrl_pending_clones = []
        self._ctrl_pending_clone_positions = []
        self._ctrl_pending_dragging = False

    def _begin_ctrl_pending(self, item, scene_point):
        self._ctrl_pending_item = item
        self._ctrl_pending_start_scene = QPointF(scene_point)
        self._ctrl_pending_before = None
        self._ctrl_pending_clones = []
        self._ctrl_pending_clone_positions = []
        self._ctrl_pending_dragging = False

    def _ctrl_drag_threshold_scene(self):
        scale = abs(float(self.transform().m11()))
        if scale < 1e-6:
            scale = 1.0
        return 5.0 / scale

    def _start_pending_ctrl_duplicate(self):
        source = self._ctrl_pending_item
        if source is None or not hasattr(source, "record"):
            return False

        self._sync_annotation_records()
        selected = self._selected_annotation_items_sorted()
        sources = (
            selected
            if source.isSelected() and len(selected) > 1
            else [source]
        )

        self._ctrl_pending_before = self._history_snapshot()
        self.scene.clearSelection()
        clones = []

        for item in sources:
            record = self._clone_record(item.record)
            self._annotation_records.append(record)
            clone = self._create_annotation_item(record)
            if clone is not None:
                clone.setSelected(True)
                clones.append(clone)

        if not clones:
            self._clear_ctrl_pending()
            return False

        self._ctrl_pending_clones = clones
        self._ctrl_pending_clone_positions = [
            QPointF(clone.pos()) for clone in clones
        ]
        self._ctrl_pending_dragging = True
        self._active_selection_item = clones[-1]
        self.annotation_selected.emit(clones[-1])
        self._refresh_selection_overlay()
        return True

    def _move_pending_ctrl_duplicate(self, scene_point):
        if not self._ctrl_pending_dragging:
            return False

        delta = QPointF(scene_point) - self._ctrl_pending_start_scene
        for clone, start_pos in zip(
            self._ctrl_pending_clones,
            self._ctrl_pending_clone_positions,
        ):
            clone.setPos(start_pos + delta)

        self._sync_annotation_records()
        self._refresh_selection_overlay()
        return True

    def _finish_pending_ctrl(self):
        item = self._ctrl_pending_item

        if self._ctrl_pending_dragging:
            before = self._ctrl_pending_before
            self._sync_annotation_records()
            self._clear_ctrl_pending()
            self._commit_history_change(before)
            return True

        if item is not None:
            item.setSelected(not item.isSelected())
            selected = self._selected_annotation_items_sorted()
            self._active_selection_item = (
                item if item.isSelected()
                else (selected[-1] if selected else None)
            )
            if self._active_selection_item is not None:
                self.annotation_selected.emit(
                    self._active_selection_item
                )
            self._refresh_selection_overlay()
            self._clear_ctrl_pending()
            return True

        self._clear_ctrl_pending()
        return False

    def _selected_annotation_items_sorted(self):
        return sorted(
            self._selected_annotation_items(),
            key=lambda item: float(item.record.get("z", 0.0)),
        )

    def select_all_annotations(self):
        if not self.has_document():
            return False

        self.scene.clearSelection()
        for item in self._annotation_items:
            item.setSelected(True)

        selected = self._selected_annotation_items_sorted()
        if not selected:
            return False

        self._active_selection_item = selected[-1]
        self.annotation_selected.emit(selected[-1])
        self._refresh_selection_overlay()
        return True

    def _begin_multi_drag(self):
        if len(self._selected_annotation_items()) < 2:
            return False
        self._multi_drag_before = self._history_snapshot()
        self._multi_dragging = True
        return True

    def _finish_multi_drag(self):
        if not self._multi_dragging:
            return
        self._sync_annotation_records()
        before = self._multi_drag_before
        self._multi_drag_before = None
        self._multi_dragging = False
        self._commit_history_change(before)

    def _duplicate_selected_for_ctrl_drag(self):
        selected = self._selected_annotation_items_sorted()
        if not selected:
            return []

        before = self._history_snapshot()
        self.scene.clearSelection()
        clones = []

        for source_item in selected:
            record = self._clone_record(source_item.record)
            self._annotation_records.append(record)
            clone = self._create_annotation_item(record)
            if clone is not None:
                clone.setSelected(True)
                clones.append(clone)

        if not clones:
            return []

        self._gesture_before = before
        self._ctrl_drag_started = True
        self._ctrl_drag_clone_item = clones[-1]
        self.annotation_selected.emit(clones[-1])
        self._refresh_selection_overlay()
        return clones

    def _selected_annotation_items(self):
        return [
            item
            for item in self.scene.selectedItems()
            if hasattr(item, "record")
        ]

    def copy_selected_annotations(self):
        self._sync_annotation_records()
        selected = self._selected_annotation_items()
        if not selected:
            return False

        self._annotation_clipboard = [
            deepcopy(item.record)
            for item in selected
        ]
        self._paste_generation = 0
        return True

    def _clone_record(
        self,
        source_record,
        offset_x=0.0,
        offset_y=0.0,
        page_index=None,
    ):
        record = deepcopy(source_record)
        record["id"] = str(uuid.uuid4())
        record["x"] = float(record.get("x", 0.0)) + float(offset_x)
        record["y"] = float(record.get("y", 0.0)) + float(offset_y)
        record["z"] = self._next_annotation_z()

        if page_index is not None:
            record["page_index"] = int(page_index)

        return record

    def paste_annotations(self):
        if not self._annotation_clipboard:
            return False

        before = self._history_snapshot()
        self._paste_generation += 1
        offset = self._paste_offset_step * self._paste_generation

        self.scene.clearSelection()
        created = []

        for source_record in self._annotation_clipboard:
            record = self._clone_record(
                source_record,
                offset_x=offset,
                offset_y=offset,
            )
            self._annotation_records.append(record)
            item = self._create_annotation_item(record)
            if item is not None:
                item.setSelected(True)
                created.append(item)

        if not created:
            return False

        self.annotation_selected.emit(created[-1])
        self._commit_history_change(before)
        return True

    def _begin_ctrl_drag_duplicate(self, source_item):
        if source_item is None or not hasattr(source_item, "record"):
            return None

        before = self._history_snapshot()
        self._sync_annotation_records()

        record = self._clone_record(source_item.record)
        self._annotation_records.append(record)
        clone = self._create_annotation_item(record)
        if clone is None:
            return None

        self.scene.clearSelection()
        clone.setSelected(True)
        self.annotation_selected.emit(clone)

        self._gesture_before = before
        self._ctrl_drag_source_item = source_item
        self._ctrl_drag_clone_item = clone
        self._ctrl_drag_started = True
        return clone

    def _finish_ctrl_drag_duplicate(self):
        if not self._ctrl_drag_started:
            return

        self._sync_annotation_records()
        before = self._gesture_before
        self._gesture_before = None
        self._ctrl_drag_source_item = None
        self._ctrl_drag_clone_item = None
        self._ctrl_drag_started = False
        self._commit_history_change(before)

    def _history_snapshot(self):
        self._sync_annotation_records()
        return deepcopy(self._annotation_records)

    def _emit_history_state(self):
        self.undo_available_changed.emit(bool(self._undo_stack))
        self.redo_available_changed.emit(bool(self._redo_stack))

    def _commit_history_change(self, before):
        if self._history_suspended or before is None:
            return
        after = self._history_snapshot()
        if before == after:
            return
        self._undo_stack.append(deepcopy(before))
        if len(self._undo_stack) > self._history_limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._emit_history_state()

    def reset_annotation_history(self):
        self._property_edit_timer.stop()
        self._gesture_before = None
        self._property_edit_before = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._emit_history_state()

    def _restore_history_snapshot(self, snapshot):
        self._history_suspended = True
        try:
            self._annotation_records = deepcopy(snapshot)
            self.scene.clearSelection()
            self._restore_annotation_items()
        finally:
            self._history_suspended = False
        self.annotation_selected.emit(None)

    def finish_property_edit(self):
        before = self._property_edit_before
        self._property_edit_before = None
        self._commit_history_change(before)

    def undo_annotations(self):
        self.finish_property_edit()
        if not self._undo_stack:
            return
        current = self._history_snapshot()
        target = self._undo_stack.pop()
        self._redo_stack.append(current)
        self._restore_history_snapshot(target)
        self._emit_history_state()

    def redo_annotations(self):
        self.finish_property_edit()
        if not self._redo_stack:
            return
        current = self._history_snapshot()
        target = self._redo_stack.pop()
        self._undo_stack.append(current)
        self._restore_history_snapshot(target)
        self._emit_history_state()

    def update_annotation_record(self, item, changes, merge_property_edits=False):
        if item is None or item.scene() is None:
            return
        if merge_property_edits:
            if self._property_edit_before is None:
                self._property_edit_before = self._history_snapshot()
            item.record.update(changes)
            if hasattr(item, "refresh_from_record"):
                item.refresh_from_record()
            self._property_edit_timer.start()
            return
        before = self._history_snapshot()
        item.record.update(changes)
        if hasattr(item, "setPlainText") and "text" in changes:
            item.setPlainText(str(changes["text"]))
        if hasattr(item, "refresh_from_record"):
            item.refresh_from_record()
        self._commit_history_change(before)

    def remove_annotation_item(self, item):
        if item is None or not hasattr(item, "record"):
            return
        before = self._history_snapshot()
        record = item.record
        if record in self._annotation_records:
            self._annotation_records.remove(record)
        if item in self._annotation_items:
            self._annotation_items.remove(item)
        if item.scene() is self.scene:
            self.scene.removeItem(item)
        self._commit_history_change(before)


    def set_date_stamp_preview_settings(self, settings):
        self._date_stamp_preview_settings = dict(settings or {})

    def _remove_date_stamp_preview(self):
        item = self._date_stamp_preview_item
        self._date_stamp_preview_item = None
        self._date_stamp_preview_page = None
        self._date_stamp_preview_point = None
        if item is None:
            return
        try:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
        except RuntimeError:
            pass

    def _start_date_stamp_preview(self, page_index, page_point):
        self._remove_date_stamp_preview()
        origin = self._page_origins.get(int(page_index))
        if origin is None:
            return False

        settings = dict(self._date_stamp_preview_settings)
        record = {
            "type": "date_stamp",
            "page_index": int(page_index),
            "x": float(page_point.x()),
            "y": float(page_point.y()),
            "top": str(settings.get("top", "検図")),
            "date": str(settings.get("date", "")),
            "bottom": str(settings.get("bottom", "")),
            "color": str(settings.get("color", "black")),
            "size": float(settings.get("size", 72.0)),
            "line_width": float(settings.get("line_width", 1.5)),
            "z": 10000.0,
        }
        item = DateStampItem(record)
        item.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
            False,
        )
        item.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,
            False,
        )
        item.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges,
            False,
        )
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        item.setOpacity(0.45)
        item.setPos(origin[0] + record["x"], origin[1] + record["y"])
        item.setZValue(10000.0)
        self.scene.addItem(item)

        self._date_stamp_preview_item = item
        self._date_stamp_preview_page = int(page_index)
        self._date_stamp_preview_point = QPointF(page_point)
        return True

    def _move_date_stamp_preview(self, page_index, page_point):
        item = self._date_stamp_preview_item
        if item is None:
            return False
        origin = self._page_origins.get(int(page_index))
        if origin is None:
            return False

        self._date_stamp_preview_page = int(page_index)
        self._date_stamp_preview_point = QPointF(page_point)
        item.record["page_index"] = int(page_index)
        item.record["x"] = float(page_point.x())
        item.record["y"] = float(page_point.y())
        item.setPos(origin[0] + page_point.x(), origin[1] + page_point.y())
        item.update()
        return True

    def set_annotation_mode(self, mode):
        if mode != "date_stamp":
            self._remove_date_stamp_preview()
        if mode not in {"hand", "check", "comment", "date_stamp", "arrow", "rectangle", "ellipse", "cloud"}:
            mode = "hand"
        self.annotation_mode = mode
        cursor = (
            Qt.CursorShape.ArrowCursor
            if mode == "hand"
            else Qt.CursorShape.CrossCursor
        )
        self.setCursor(cursor)

    def _page_point_at(self, scene_point):
        for page_index, item in self._page_items.items():
            if not item.sceneBoundingRect().contains(scene_point):
                continue
            origin = self._page_origins.get(page_index)
            if origin is None:
                return None
            return (
                page_index,
                QPointF(
                    scene_point.x() - origin[0],
                    scene_point.y() - origin[1],
                ),
            )
        return None

    def add_check_overlay(self, page_index, point):
        before = self._history_snapshot()
        defaults = self.annotation_defaults("check")
        record = {
            "type": "check",
            "page_index": int(page_index),
            "x": float(point.x()),
            "y": float(point.y()),
            "size": float(defaults.get("size", 15.0)),
            "color": str(defaults.get("color", "#dc0000")),
            "line_width": float(
                defaults.get("line_width", 2.2)
            ),
        }
        self._annotation_records.append(record)
        self._create_annotation_item(record)
        self._commit_history_change(before)

    def add_text_overlay(self, page_index, point, text):
        before = self._history_snapshot()
        record = {
            "type": "text",
            "page_index": int(page_index),
            "x": float(point.x()),
            "y": float(point.y()),
            "text": str(text).strip(),
            "font_size": 11.0,
            "text_color": "#000000",
        }
        if not record["text"]:
            return
        self._annotation_records.append(record)
        self._create_annotation_item(record)
        self._commit_history_change(before)

    def add_date_stamp_overlay(self, page_index, point, settings):
        before = self._history_snapshot()
        record = {
            "type": "date_stamp",
            "page_index": int(page_index),
            "x": float(point.x()),
            "y": float(point.y()),
            "top": str(settings.get("top", "検図")),
            "date": str(settings.get("date", "")),
            "bottom": str(settings.get("bottom", "")),
            "color": str(settings.get("color", "black")),
            "size": float(settings.get("size", 72.0)),
            "line_width": float(settings.get("line_width", 1.5)),
        }
        self._annotation_records.append(record)
        item = self._create_annotation_item(record)
        if item is not None:
            self.scene.clearSelection()
            item.setSelected(True)
            self.annotation_selected.emit(item)
        self._commit_history_change(before)
        return item


    def add_arrow_overlay(
        self,
        page_index,
        start_point,
        end_point,
        color=None,
        line_width=None,
    ):
        before = self._history_snapshot()
        defaults = self.annotation_defaults("arrow")
        if color is None:
            color = defaults.get("color", "#dc0000")
        if line_width is None:
            line_width = defaults.get("line_width", 2.0)
        record = {
            "id": str(uuid.uuid4()),
            "type": "arrow",
            "page_index": int(page_index),
            "x": float(start_point.x()),
            "y": float(start_point.y()),
            "dx": float(end_point.x() - start_point.x()),
            "dy": float(end_point.y() - start_point.y()),
            "color": str(color),
            "line_width": float(line_width),
            "text": "",
            "font_size": 11.0,
            "fill_enabled": False,
            "fill_opacity": 0.25,
            "fill_color": "#ffff00",
            "z": self._next_annotation_z(),
        }
        self._annotation_records.append(record)
        item = self._create_annotation_item(record)
        if item is not None:
            self.scene.clearSelection()
            item.setSelected(True)
            self.annotation_selected.emit(item)
        self._commit_history_change(before)
        return item


    def _ensure_annotation_identity(self, record):
        if not record.get("id"):
            record["id"] = str(uuid.uuid4())
        if "z" not in record:
            record["z"] = self._next_annotation_z()
        return record

    def _next_annotation_z(self):
        values = [
            float(record.get("z", 20.0))
            for record in self._annotation_records
        ]
        return (max(values) + 1.0) if values else 20.0

    def _normalize_annotation_z(self):
        ordered = sorted(
            self._annotation_records,
            key=lambda record: float(record.get("z", 20.0)),
        )
        for index, record in enumerate(ordered):
            record["z"] = 20.0 + index
        for item in self._annotation_items:
            item.setZValue(float(item.record.get("z", 20.0)))

    def change_selected_z_order(self, operation):
        selected_items = self._selected_annotation_items_sorted()
        if not selected_items:
            return False

        selected_records = [
            item.record for item in selected_items
        ]
        selected_ids = {
            id(record) for record in selected_records
        }

        before = self._history_snapshot()
        ordered = sorted(
            self._annotation_records,
            key=lambda record: float(record.get("z", 20.0)),
        )

        if operation == "front":
            remaining = [
                record
                for record in ordered
                if id(record) not in selected_ids
            ]
            ordered = remaining + selected_records

        elif operation == "back":
            remaining = [
                record
                for record in ordered
                if id(record) not in selected_ids
            ]
            ordered = selected_records + remaining

        elif operation == "forward":
            for index in range(len(ordered) - 2, -1, -1):
                current = ordered[index]
                following = ordered[index + 1]
                if (
                    id(current) in selected_ids
                    and id(following) not in selected_ids
                ):
                    ordered[index], ordered[index + 1] = (
                        following,
                        current,
                    )

        elif operation == "backward":
            for index in range(1, len(ordered)):
                current = ordered[index]
                previous = ordered[index - 1]
                if (
                    id(current) in selected_ids
                    and id(previous) not in selected_ids
                ):
                    ordered[index - 1], ordered[index] = (
                        current,
                        previous,
                    )

        else:
            return False

        for index, record in enumerate(ordered):
            record["z"] = 20.0 + index

        self._normalize_annotation_z()
        self._refresh_selection_overlay()
        self._commit_history_change(before)
        return True


    def add_shape_overlay(
        self,
        shape_type,
        page_index,
        start_point,
        end_point,
        color="red",
        line_width=2.0,
    ):
        before = self._history_snapshot()
        defaults = self.annotation_defaults(shape_type)
        color = defaults.get("color", color)
        line_width = defaults.get("line_width", line_width)
        left = min(float(start_point.x()), float(end_point.x()))
        top = min(float(start_point.y()), float(end_point.y()))
        width = max(
            abs(float(end_point.x() - start_point.x())),
            ShapeAnnotationItem.MIN_SIZE,
        )
        height = max(
            abs(float(end_point.y() - start_point.y())),
            ShapeAnnotationItem.MIN_SIZE,
        )
        record = {
            "id": str(uuid.uuid4()),
            "type": str(shape_type),
            "page_index": int(page_index),
            "x": left,
            "y": top,
            "width": width,
            "height": height,
            "color": str(color),
            "line_width": float(line_width),
            "text": "",
            "font_size": float(defaults.get("font_size", 11.0)),
            "text_color": str(
                defaults.get("text_color", "#000000")
            ),
            "fill_enabled": bool(
                defaults.get("fill_enabled", False)
            ),
            "fill_opacity": float(
                defaults.get("fill_opacity", 0.25)
            ),
            "fill_color": str(
                defaults.get("fill_color", "#ffff00")
            ),
            "z": self._next_annotation_z(),
        }
        self._annotation_records.append(record)
        item = self._create_annotation_item(record)
        if item is not None:
            self.scene.clearSelection()
            item.setSelected(True)
            self.annotation_selected.emit(item)
        self._commit_history_change(before)
        return item

    def update_arrow_properties(self, item, color=None, line_width=None):
        record = getattr(item, "record", None)
        if not record or record.get("type") != "arrow":
            return False
        before = self._history_snapshot()
        if color is not None:
            parsed = QColor(str(color))
            if parsed.isValid(): record["color"] = parsed.name(QColor.NameFormat.HexRgb)
        if line_width is not None: record["line_width"] = max(float(line_width), 0.5)
        item.refresh_from_record(); self._refresh_selection_overlay(); self._commit_history_change(before)
        return True

    def update_check_properties(self, item, color=None, size=None, line_width=None):
        record = getattr(item, "record", None)
        if not record or record.get("type") != "check":
            return False
        before = self._history_snapshot()
        if color is not None:
            parsed = QColor(str(color))
            if parsed.isValid(): record["color"] = parsed.name(QColor.NameFormat.HexRgb)
        if size is not None: record["size"] = max(float(size), CheckAnnotationItem.MIN_SIZE)
        if line_width is not None: record["line_width"] = max(float(line_width), 0.5)
        item.refresh_from_record(); self._refresh_selection_overlay(); self._commit_history_change(before)
        return True

    def update_shape_properties(
        self,
        item,
        text,
        font_size=None,
        fill_enabled=None,
        fill_opacity=None,
        fill_color=None,
        text_color=None,
        border_color=None,
        line_width=None,
        width=None,
        height=None,
    ):
        record = getattr(item, "record", None)
        if not record or record.get("type") not in {"rectangle", "cloud"}:
            return False

        before = self._history_snapshot()
        record["text"] = str(text).strip()

        if font_size is not None:
            record["font_size"] = max(float(font_size), 4.0)
        if fill_enabled is not None:
            record["fill_enabled"] = bool(fill_enabled)
        if fill_opacity is not None:
            record["fill_opacity"] = min(
                max(float(fill_opacity), 0.0),
                1.0,
            )

        if fill_color is not None:
            color = QColor(str(fill_color))
            if color.isValid():
                record["fill_color"] = color.name(
                    QColor.NameFormat.HexRgb
                )

        if text_color is not None:
            color = QColor(str(text_color))
            if color.isValid():
                record["text_color"] = color.name(
                    QColor.NameFormat.HexRgb
                )

        if border_color is not None:
            color = QColor(str(border_color))
            if color.isValid(): record["color"] = color.name(QColor.NameFormat.HexRgb)
        if line_width is not None:
            record["line_width"] = max(float(line_width), 0.5)

        if width is not None:
            record["width"] = max(
                float(width),
                ShapeAnnotationItem.MIN_SIZE,
            )

        if height is not None:
            record["height"] = max(
                float(height),
                ShapeAnnotationItem.MIN_SIZE,
            )

        if hasattr(item, "refresh_from_record"):
            item.refresh_from_record()
        else:
            item.update()

        self._refresh_selection_overlay()
        self._commit_history_change(before)
        return True

    def update_shape_text(self, item, text, font_size=None):
        return self.update_shape_properties(
            item,
            text,
            font_size=font_size,
        )


    def _create_annotation_item(self, record):
        self._ensure_annotation_identity(record)
        origin = self._page_origins.get(record["page_index"])
        if origin is None:
            return
        if record["type"] == "check":
            item = CheckAnnotationItem(record)
        elif record["type"] == "text":
            item = TextAnnotationItem(record)
        elif record["type"] == "date_stamp":
            item = DateStampItem(record)
        elif record["type"] == "arrow":
            item = ArrowAnnotationItem(record)
        elif record["type"] in {"rectangle", "ellipse", "cloud"}:
            item = ShapeAnnotationItem(record)
        else:
            return None
        item.setPos(origin[0] + record["x"], origin[1] + record["y"])
        item.setZValue(float(record.get("z", 20.0)))
        self.scene.addItem(item)
        self._annotation_items.append(item)
        self._refresh_selection_overlay()
        return item

    def _sync_annotation_records(self):
        for item in list(self._annotation_items):
            record = item.record
            origin = self._page_origins.get(record["page_index"])
            if origin is None:
                continue
            record["x"] = float(item.pos().x() - origin[0])
            record["y"] = float(item.pos().y() - origin[1])
        self._refresh_selection_overlay()

    def _remove_annotation_items(self):
        for item in list(self._annotation_items):
            if item.scene() is self.scene:
                self.scene.removeItem(item)
        self._annotation_items.clear()

    def _restore_annotation_items(self):
        self._remove_annotation_items()
        for record in self._annotation_records:
            if record["page_index"] in self._page_origins:
                self._create_annotation_item(record)

    def export_annotations(self):
        self._sync_annotation_records()
        return [dict(record) for record in self._annotation_records]

    def clear_pending_annotations(self):
        self._remove_date_stamp_preview()
        self._remove_annotation_items()
        self._annotation_records.clear()
        self.reset_annotation_history()

    def delete_selected_annotations(self):
        selected = [
            item
            for item in self.scene.selectedItems()
            if hasattr(item, "record")
        ]
        if not selected:
            return
        before = self._history_snapshot()
        for item in selected:
            record = item.record
            if record in self._annotation_records:
                self._annotation_records.remove(record)
            if item in self._annotation_items:
                self._annotation_items.remove(item)
            self.scene.removeItem(item)
        self.annotation_selected.emit(None)
        self._commit_history_change(before)

    def _annotation_item_near(self, viewport_pos, radius=10):
        direct = self.itemAt(viewport_pos)
        item = direct
        while item is not None:
            if hasattr(item, "record"):
                return item
            item = item.parentItem()

        scene_pos = self.mapToScene(viewport_pos)
        search_rect = QRectF(
            scene_pos.x() - radius / max(self.zoom_factor, 0.01),
            scene_pos.y() - radius / max(self.zoom_factor, 0.01),
            radius * 2 / max(self.zoom_factor, 0.01),
            radius * 2 / max(self.zoom_factor, 0.01),
        )
        candidates = [
            item for item in self.scene.items(search_rect)
            if hasattr(item, "record")
        ]
        return candidates[0] if candidates else None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene_point = self.mapToScene(
                event.position().toPoint()
            )

            # Selection handles always have the highest priority. Without
            # this branch, PDFView can start drawing a new circle before the
            # scene has a chance to deliver the event to SelectionOverlay.
            overlay_handle = (
                self._selection_overlay.handle_at_scene_point(
                    scene_point
                )
                if self._selection_overlay is not None
                else None
            )
            if overlay_handle is not None:
                self.finish_property_edit()
                QGraphicsView.mousePressEvent(self, event)
                return

            nearby = self._annotation_item_near(
                event.position().toPoint()
            )
            if nearby is not None:
                self.finish_property_edit()

                modifiers = event.modifiers()
                ctrl_pressed = bool(
                    modifiers
                    & Qt.KeyboardModifier.ControlModifier
                )

                if ctrl_pressed:
                    self._begin_ctrl_pending(
                        nearby,
                        scene_point,
                    )
                    event.accept()
                    return

                if not nearby.isSelected():
                    self.scene.clearSelection()
                    nearby.setSelected(True)

                self._active_selection_item = nearby

                if len(self._selected_annotation_items()) > 1:
                    self._begin_multi_drag()
                else:
                    self._gesture_before = self._history_snapshot()

                self.annotation_selected.emit(nearby)
                QGraphicsView.mousePressEvent(self, event)
                return

            hit = self._page_point_at(scene_point)

            if self.annotation_mode == "date_stamp" and hit is not None:
                page_index, page_point = hit
                if self._start_date_stamp_preview(page_index, page_point):
                    event.accept()
                    return

            if (
                self.annotation_mode in {"rectangle", "ellipse", "cloud"}
                and hit is not None
            ):
                page_index, page_point = hit
                self._shape_drawing = True
                self._shape_start_hit = (
                    page_index,
                    QPointF(page_point),
                )
                self._shape_kind = self.annotation_mode
                scene_point = self.mapToScene(
                    event.position().toPoint()
                )
                preview = (
                    QGraphicsEllipseItem()
                    if self._shape_kind == "ellipse"
                    else QGraphicsRectItem()
                )
                preview.setRect(
                    scene_point.x(),
                    scene_point.y(),
                    0.0,
                    0.0,
                )
                preview.setPen(
                    QPen(
                        QColor(220, 0, 0),
                        2.0,
                        Qt.PenStyle.DashLine,
                    )
                )
                preview.setBrush(Qt.BrushStyle.NoBrush)
                preview.setZValue(1000.0)
                self.scene.addItem(preview)
                self._shape_preview = preview
                event.accept()
                return

            if self.annotation_mode == "arrow" and hit is not None:
                page_index, page_point = hit
                self._arrow_drawing = True
                self._arrow_start_hit = (page_index, QPointF(page_point))
                scene_point = self.mapToScene(event.position().toPoint())
                preview = QGraphicsLineItem(
                    scene_point.x(),
                    scene_point.y(),
                    scene_point.x(),
                    scene_point.y(),
                )
                preview.setPen(
                    QPen(
                        QColor(220, 0, 0),
                        2.0,
                        Qt.PenStyle.DashLine,
                    )
                )
                preview.setZValue(1000.0)
                self.scene.addItem(preview)
                self._arrow_preview = preview
                event.accept()
                return

            if (
                self.annotation_mode not in {"hand", "date_stamp"}
                and hit is not None
            ):
                self.annotation_clicked.emit(hit[0], hit[1])
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._date_stamp_preview_item is not None:
            hit = self._page_point_at(
                self.mapToScene(event.position().toPoint())
            )
            if hit is not None:
                self._move_date_stamp_preview(hit[0], hit[1])
            event.accept()
            return

        if self._ctrl_pending_item is not None:
            current = self.mapToScene(event.position().toPoint())
            delta = current - self._ctrl_pending_start_scene

            if (
                not self._ctrl_pending_dragging
                and (
                    delta.x() * delta.x()
                    + delta.y() * delta.y()
                ) ** 0.5
                >= self._ctrl_drag_threshold_scene()
            ):
                self._start_pending_ctrl_duplicate()

            if self._ctrl_pending_dragging:
                self._move_pending_ctrl_duplicate(current)

            event.accept()
            return

        if self._shape_drawing and self._shape_preview is not None:
            start_scene = self._shape_preview.rect().topLeft()
            current = self.mapToScene(event.position().toPoint())
            self._shape_preview.setRect(
                QRectF(start_scene, current).normalized()
            )
            event.accept()
            return

        if self._arrow_drawing and self._arrow_preview is not None:
            current = self.mapToScene(event.position().toPoint())
            line = self._arrow_preview.line()
            line.setP2(current)
            self._arrow_preview.setLine(line)
            event.accept()
            return

        super().mouseMoveEvent(event)
        self._refresh_selection_overlay()

    def mouseReleaseEvent(self, event):
        if (
            self._date_stamp_preview_item is not None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            page_index = self._date_stamp_preview_page
            page_point = self._date_stamp_preview_point
            self._remove_date_stamp_preview()
            if page_index is not None and page_point is not None:
                self.annotation_clicked.emit(
                    int(page_index),
                    QPointF(page_point),
                )
            event.accept()
            return

        if (
            self._ctrl_pending_item is not None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._finish_pending_ctrl()
            event.accept()
            return

        if (
            self._multi_dragging
            and event.button() == Qt.MouseButton.LeftButton
        ):
            QGraphicsView.mouseReleaseEvent(self, event)
            self._finish_multi_drag()
            self._refresh_selection_overlay()
            event.accept()
            return

        if (
            self._ctrl_drag_started
            and event.button() == Qt.MouseButton.LeftButton
        ):
            QGraphicsView.mouseReleaseEvent(self, event)
            self._finish_ctrl_drag_duplicate()
            self._refresh_selection_overlay()
            event.accept()
            return

        if (
            self._shape_drawing
            and event.button() == Qt.MouseButton.LeftButton
        ):
            start_hit = self._shape_start_hit
            preview = self._shape_preview
            shape_kind = self._shape_kind
            self._shape_drawing = False
            self._shape_start_hit = None
            self._shape_preview = None
            self._shape_kind = None

            if preview is not None and preview.scene() is self.scene:
                self.scene.removeItem(preview)

            if start_hit is not None:
                page_index, start_point = start_hit
                hit = self._page_point_at(
                    self.mapToScene(event.position().toPoint())
                )
                if hit is not None and hit[0] == page_index:
                    end_point = hit[1]
                    delta = end_point - start_point
                    if (
                        abs(delta.x()) >= ShapeAnnotationItem.MIN_SIZE
                        or abs(delta.y()) >= ShapeAnnotationItem.MIN_SIZE
                    ):
                        self.add_shape_overlay(
                            shape_kind,
                            page_index,
                            start_point,
                            end_point,
                        )
            event.accept()
            return

        if (
            self._arrow_drawing
            and event.button() == Qt.MouseButton.LeftButton
        ):
            start_hit = self._arrow_start_hit
            preview = self._arrow_preview
            self._arrow_drawing = False
            self._arrow_start_hit = None
            self._arrow_preview = None

            if preview is not None and preview.scene() is self.scene:
                self.scene.removeItem(preview)

            if start_hit is not None:
                page_index, start_point = start_hit
                hit = self._page_point_at(
                    self.mapToScene(event.position().toPoint())
                )
                if hit is not None and hit[0] == page_index:
                    end_point = hit[1]
                    delta = end_point - start_point
                    if (
                        abs(delta.x()) + abs(delta.y())
                        >= ArrowAnnotationItem.MIN_LENGTH
                    ):
                        self.add_arrow_overlay(
                            page_index,
                            start_point,
                            end_point,
                        )
            event.accept()
            return

        (
            QGraphicsView.mouseReleaseEvent(self, event)
            if self.scene.selectedItems()
            else super().mouseReleaseEvent(event)
        )
        self._sync_annotation_records()
        self._refresh_selection_overlay()
        before = self._gesture_before
        self._gesture_before = None
        self._commit_history_change(before)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            nearby = self._annotation_item_near(event.position().toPoint())
            if nearby is not None and nearby.record.get("type") in {"text", "date_stamp", "rectangle", "cloud", "arrow", "check"}:
                self.scene.clearSelection()
                nearby.setSelected(True)
                self.annotation_selected.emit(nearby)
                self.annotation_edit_requested.emit(nearby)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)


    def contextMenuEvent(self, event):
        nearby = self._annotation_item_near(event.pos())

        if nearby is not None:
            if not nearby.isSelected():
                self.scene.clearSelection()
                nearby.setSelected(True)

            self._active_selection_item = nearby
            self.annotation_selected.emit(nearby)
            self._refresh_selection_overlay()

        selected_items = self._selected_annotation_items_sorted()
        has_selection = bool(selected_items)
        has_clipboard = bool(self._annotation_clipboard)

        menu = QMenu(self)

        copy_action = menu.addAction("コピー\tCtrl+C")
        copy_action.setEnabled(has_selection)

        paste_action = menu.addAction("貼り付け\tCtrl+V")
        paste_action.setEnabled(has_clipboard)

        duplicate_action = menu.addAction("複製")
        duplicate_action.setEnabled(has_selection)

        menu.addSeparator()

        order_menu = menu.addMenu("重なり順")
        front_action = order_menu.addAction("最前面へ")
        forward_action = order_menu.addAction("前面へ")
        backward_action = order_menu.addAction("背面へ")
        back_action = order_menu.addAction("最背面へ")
        order_menu.setEnabled(has_selection)

        menu.addSeparator()

        properties_action = menu.addAction("プロパティ")
        properties_action.setEnabled(
            has_selection and len(selected_items) == 1
        )

        delete_action = menu.addAction("削除\tDelete")
        delete_action.setEnabled(has_selection)

        selected_action = menu.exec(event.globalPos())
        if selected_action is None:
            return

        if selected_action is copy_action:
            self.copy_selected_annotations()

        elif selected_action is paste_action:
            self.paste_annotations()

        elif selected_action is duplicate_action:
            if self.copy_selected_annotations():
                self.paste_annotations()

        elif selected_action is front_action:
            self.change_selected_z_order("front")

        elif selected_action is forward_action:
            self.change_selected_z_order("forward")

        elif selected_action is backward_action:
            self.change_selected_z_order("backward")

        elif selected_action is back_action:
            self.change_selected_z_order("back")

        elif selected_action is properties_action:
            self.annotation_edit_requested.emit(
                selected_items[-1]
            )

        elif selected_action is delete_action:
            self.delete_selected_annotations()


    def _cancel_shape_drawing(self):
        if not self._shape_drawing:
            return False

        preview = self._shape_preview
        self._shape_drawing = False
        self._shape_start_hit = None
        self._shape_preview = None
        self._shape_kind = None

        if preview is not None:
            try:
                if preview.scene() is self.scene:
                    self.scene.removeItem(preview)
            except RuntimeError:
                pass

        return True

    def _cancel_arrow_drawing(self):
        if not self._arrow_drawing:
            return False

        preview = self._arrow_preview
        self._arrow_drawing = False
        self._arrow_start_hit = None
        self._arrow_preview = None

        if preview is not None:
            try:
                if preview.scene() is self.scene:
                    self.scene.removeItem(preview)
            except RuntimeError:
                pass

        return True

    def _cancel_active_gesture(self):
        if self._ctrl_pending_item is not None:
            before = self._ctrl_pending_before
            was_dragging = self._ctrl_pending_dragging
            self._clear_ctrl_pending()
            if was_dragging and before is not None:
                self._restore_history_snapshot(before)
            return True

        if self._ctrl_drag_started:
            before = self._gesture_before
            self._gesture_before = None
            self._ctrl_drag_source_item = None
            self._ctrl_drag_clone_item = None
            self._ctrl_drag_started = False

            if before is not None:
                self._restore_history_snapshot(before)
            return True

        if self._multi_dragging:
            before = self._multi_drag_before
            self._multi_drag_before = None
            self._multi_dragging = False

            if before is not None:
                self._restore_history_snapshot(before)
            return True

        if self._gesture_before is not None:
            before = self._gesture_before
            self._gesture_before = None
            self._restore_history_snapshot(before)
            return True

        return False

    def clear_annotation_selection(self):
        try:
            selected = self._selected_annotation_items()
        except RuntimeError:
            return False

        if not selected:
            return False

        self.scene.clearSelection()
        self._active_selection_item = None
        self._refresh_selection_overlay()
        self.selection_count_changed.emit(0)
        return True


    def cancel_current_operation(self):
        self.finish_property_edit()

        if self._date_stamp_preview_item is not None:
            self._remove_date_stamp_preview()
            return True

        if self._cancel_shape_drawing():
            return True
        if self._cancel_arrow_drawing():
            return True
        if self._cancel_active_gesture():
            return True
        if self.clear_annotation_selection():
            return True

        return False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.cancel_current_operation():
                event.accept()
                return

        if event.matches(QKeySequence.StandardKey.SelectAll):
            if self.select_all_annotations():
                event.accept()
                return

        if event.matches(QKeySequence.StandardKey.Copy):
            if self.copy_selected_annotations():
                event.accept()
                return

        if event.matches(QKeySequence.StandardKey.Paste):
            if self.paste_annotations():
                event.accept()
                return

        if event.matches(QKeySequence.StandardKey.Undo):
            self.undo_annotations()
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.Redo):
            self.redo_annotations()
            event.accept()
            return
        if event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}:
            self.delete_selected_annotations()
            event.accept()
            return
        super().keyPressEvent(event)

    def clear_pages(self):
        self._sync_annotation_records()
        self._annotation_items.clear()
        self._detach_selection_overlay()
        self.scene.clear()
        self._reattach_selection_overlay()
        self.page_manager.clear()
        self._page_items.clear()
        self._page_origins.clear()
        self._tile_items.clear()
        self._active_render_scale = None

    def show_pages(self, pages):
        """Create page placeholders only. No PDF bitmap is rendered here."""
        self.pages = list(pages)
        if not self.pages:
            self.clear_pages()
            return

        self.current_page_index = min(
            self.current_page_index,
            len(self.pages) - 1,
        )
        if self.single_page_mode:
            self._show_single_page(self.current_page_index)
        else:
            self._show_continuous_pages()
        self._restore_annotation_items()
        self._schedule_visible_region_changed()

    def refresh_pages(self, pages):
        center = self.mapToScene(self.viewport().rect().center())
        page_index = self.current_page_index
        self.show_pages(pages)
        self.current_page_index = min(
            page_index,
            max(0, len(self.pages) - 1),
        )
        self.centerOn(center)
        self._schedule_visible_region_changed()

    def clear_rendered_tiles(self):
        for item in list(self._tile_items.values()):
            self.scene.removeItem(item)
        self._tile_items.clear()
        self._active_render_scale = None
        self._schedule_visible_region_changed()

    def apply_rendered_pages(self, rendered_pages):
        """
        Convert worker-produced QImages to QPixmaps on the GUI thread.

        The replacement item is inserted before the previous item occupying
        the same page/column/row is removed. The old bitmap therefore remains
        visible during asynchronous zoom rendering, avoiding a white flash.
        """
        for rendered_page in rendered_pages:
            origin = self._page_origins.get(rendered_page.page_index)
            if origin is None:
                continue

            self._active_render_scale = rendered_page.render_scale

            for tile in rendered_page.tiles:
                if tile.image.isNull():
                    continue

                pixmap = QPixmap.fromImage(tile.image)
                if pixmap.isNull():
                    continue

                key = (
                    tile.page_index,
                    tile.column,
                    tile.row,
                )
                previous_item = self._tile_items.get(key)

                item = QGraphicsPixmapItem(pixmap)
                inverse_scale = (
                    1.0 / tile.render_scale
                    if tile.render_scale > 0
                    else 1.0
                )
                item.setScale(inverse_scale)
                item.setPos(
                    origin[0] + tile.scene_x,
                    origin[1] + tile.scene_y,
                )
                item.setZValue(0.1)
                self.scene.addItem(item)
                self._tile_items[key] = item

                if previous_item is not None:
                    self.scene.removeItem(previous_item)

                item.setZValue(0.0)

    def visible_page_regions(self) -> dict[int, QRectF]:
        if not self._page_origins:
            return {}

        visible_scene = self.mapToScene(
            self.viewport().rect()
        ).boundingRect()

        extra_x = visible_scene.width() * self.PREFETCH_VIEWPORTS
        extra_y = visible_scene.height() * self.PREFETCH_VIEWPORTS
        requested_scene = visible_scene.adjusted(
            -extra_x,
            -extra_y,
            extra_x,
            extra_y,
        )

        regions = {}
        for page in self.page_manager.pages:
            page_rect = page.item.sceneBoundingRect()
            intersection = requested_scene.intersected(page_rect)
            if intersection.isEmpty():
                continue

            origin = self._page_origins.get(page.page)
            if origin is None:
                continue

            regions[page.page] = QRectF(
                intersection.x() - origin[0],
                intersection.y() - origin[1],
                intersection.width(),
                intersection.height(),
            )
        return regions

    def set_single_mode(self):
        self.single_page_mode = True
        if self.pages:
            self._show_single_page(self.current_page_index)
            self._schedule_visible_region_changed()

    def set_continuous_mode(self):
        self.single_page_mode = False
        if self.pages:
            self._show_continuous_pages()
            self.scroll_to_page(self.current_page_index)
            self._schedule_visible_region_changed()

    def _add_page_placeholder(
        self,
        rendered_page,
        page_index: int,
        y_position: float,
    ):
        page_item = QGraphicsRectItem(
            QRectF(
                0.0,
                y_position,
                rendered_page.scene_width,
                rendered_page.scene_height,
            )
        )
        page_item.setBrush(QBrush(QColor("white")))
        page_item.setPen(QPen(QColor(190, 190, 190)))
        page_item.setZValue(-1.0)
        self.scene.addItem(page_item)

        self._page_items[page_index] = page_item
        self._page_origins[page_index] = (0.0, y_position)

        rect = page_item.sceneBoundingRect()
        self.page_manager.add_page(
            page_index,
            None,
            page_item,
            rect.top(),
            rect.bottom(),
        )

    def _show_single_page(self, page_index):
        if page_index < 0 or page_index >= len(self.pages):
            return

        current_zoom = self.zoom_factor
        self.clear_pages()
        self.current_page_index = page_index
        self._add_page_placeholder(
            self.pages[page_index],
            page_index,
            0.0,
        )
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self._restore_zoom(current_zoom)

    def _show_continuous_pages(self):
        current_zoom = self.zoom_factor
        self.clear_pages()
        y = 0.0

        for index, rendered_page in enumerate(self.pages):
            self._add_page_placeholder(rendered_page, index, y)
            y += rendered_page.scene_height + self.PAGE_MARGIN

        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self._restore_zoom(current_zoom)

    def _restore_zoom(self, zoom):
        self.resetTransform()
        self.scale(zoom, zoom)
        self.zoom_factor = zoom

    def scroll_to_page(self, page_index):
        if page_index < 0 or page_index >= len(self.pages):
            return

        self.current_page_index = page_index
        if self.single_page_mode:
            self._show_single_page(page_index)
            self._schedule_visible_region_changed()
            return

        for page in self.page_manager.pages:
            if page.page == page_index:
                self.verticalScrollBar().setValue(
                    int(page.top * self.zoom_factor)
                )
                self._schedule_visible_region_changed()
                return

    def get_visible_page(self):
        if self.single_page_mode:
            return self.current_page_index

        point = self.mapToScene(self.viewport().rect().topLeft())
        y = point.y() + (
            self.viewport().height()
            / max(self.zoom_factor, 0.01)
            * 0.2
        )
        return self.page_manager.visible_page(y)

    def on_scroll(self):
        if not self.single_page_mode:
            page = self.get_visible_page()
            self.current_page_index = page
            self.page_changed.emit(page)
        self._schedule_visible_region_changed()

    def _schedule_visible_region_changed(self):
        self._visible_signal_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_visible_region_changed()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.on_scroll()
