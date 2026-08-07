from __future__ import annotations

import math
import uuid

import fitz
from app.annotations.pdf_annotation_painter import draw_raster_annotation
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsObject,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


def _qcolor(value, fallback="#d00000"):
    color = QColor(str(value or fallback))
    return color if color.isValid() else QColor(fallback)


def _set_color_button(button, color):
    name = color.name(QColor.NameFormat.HexRgb)
    foreground = "#000000" if color.lightness() > 145 else "#ffffff"
    button.setText(name.upper())
    button.setStyleSheet(
        "QPushButton {"
        f"background-color: {name};"
        f"color: {foreground};"
        "padding: 5px 12px;"
        "}"
    )


class BalloonPropertiesDialog(QDialog):
    def __init__(self, parent, record):
        super().__init__(parent)
        self.setWindowTitle("バルーンのプロパティ")
        self.setMinimumWidth(410)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.text_edit = QLineEdit(
            str(record.get("text", "1")),
            self,
        )
        form.addRow("表示文字:", self.text_edit)

        self._border_color = _qcolor(
            record.get("color"),
            "#d00000",
        )
        self._fill_color = _qcolor(
            record.get("fill_color"),
            "#ffffff",
        )
        self._text_color = _qcolor(
            record.get("text_color"),
            "#d00000",
        )
        self._arrow_color = _qcolor(
            record.get(
                "arrow_color",
                record.get("color", "#d00000"),
            ),
            "#d00000",
        )

        self.border_button = QPushButton(self)
        self.fill_button = QPushButton(self)
        self.text_button = QPushButton(self)
        self.arrow_button = QPushButton(self)

        for button, color in (
            (self.border_button, self._border_color),
            (self.fill_button, self._fill_color),
            (self.text_button, self._text_color),
            (self.arrow_button, self._arrow_color),
        ):
            _set_color_button(button, color)

        self.border_button.clicked.connect(
            lambda: self._choose_color(
                "_border_color",
                self.border_button,
                "枠線色",
            )
        )
        self.fill_button.clicked.connect(
            lambda: self._choose_color(
                "_fill_color",
                self.fill_button,
                "背景色",
            )
        )
        self.text_button.clicked.connect(
            lambda: self._choose_color(
                "_text_color",
                self.text_button,
                "文字色",
            )
        )
        self.arrow_button.clicked.connect(
            lambda: self._choose_color(
                "_arrow_color",
                self.arrow_button,
                "引出線色",
            )
        )

        form.addRow("枠線色:", self.border_button)
        form.addRow("背景色:", self.fill_button)
        form.addRow("文字色:", self.text_button)
        form.addRow("引出線色:", self.arrow_button)

        self.arrow_enabled_check = QCheckBox(
            "引出線と矢印を表示",
            self,
        )
        self.arrow_enabled_check.setChecked(
            bool(
                record.get(
                    "arrow_enabled",
                    True,
                )
            )
        )
        form.addRow(
            "引出線:",
            self.arrow_enabled_check,
        )

        self.width_spin = QDoubleSpinBox(self)
        self.width_spin.setRange(28.0, 600.0)
        self.width_spin.setValue(
            max(float(record.get("width", 52.0)), 28.0)
        )
        self.width_spin.setSuffix(" pt")
        form.addRow("幅:", self.width_spin)

        self.height_spin = QDoubleSpinBox(self)
        self.height_spin.setRange(28.0, 600.0)
        self.height_spin.setValue(
            max(float(record.get("height", 52.0)), 28.0)
        )
        self.height_spin.setSuffix(" pt")
        form.addRow("高さ:", self.height_spin)

        self.font_size_spin = QDoubleSpinBox(self)
        self.font_size_spin.setRange(6.0, 96.0)
        self.font_size_spin.setValue(
            max(float(record.get("font_size", 16.0)), 6.0)
        )
        self.font_size_spin.setSuffix(" pt")
        form.addRow("文字サイズ:", self.font_size_spin)

        self.line_width_spin = QDoubleSpinBox(self)
        self.line_width_spin.setRange(0.5, 20.0)
        self.line_width_spin.setValue(
            max(float(record.get("line_width", 2.0)), 0.5)
        )
        self.line_width_spin.setSuffix(" pt")
        form.addRow("線の太さ:", self.line_width_spin)

        self.fill_opacity_spin = QSpinBox(self)
        self.fill_opacity_spin.setRange(0, 100)
        self.fill_opacity_spin.setSuffix("%")
        self.fill_opacity_spin.setValue(
            int(
                max(
                    0.0,
                    min(
                        float(record.get("fill_opacity", 1.0)),
                        1.0,
                    ),
                )
                * 100
            )
        )
        form.addRow("背景の濃さ:", self.fill_opacity_spin)

        layout.addLayout(form)

        hint = QLabel(
            "選択中は四隅でサイズ変更、四角いハンドルで"
            "引出線の出口、丸いハンドルで指示先を変更できます。",
            self,
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _choose_color(self, attr, button, title):
        selected = QColorDialog.getColor(
            getattr(self, attr),
            self,
            title,
        )
        if selected.isValid():
            selected.setAlpha(255)
            setattr(self, attr, selected)
            _set_color_button(button, selected)

    def values(self):
        return {
            "text": self.text_edit.text().strip() or "1",
            "color": self._border_color.name(),
            "fill_color": self._fill_color.name(),
            "text_color": self._text_color.name(),
            "arrow_color": self._arrow_color.name(),
            "arrow_enabled": (
                self.arrow_enabled_check.isChecked()
            ),
            "width": self.width_spin.value(),
            "height": self.height_spin.value(),
            "font_size": self.font_size_spin.value(),
            "line_width": self.line_width_spin.value(),
            "fill_opacity": self.fill_opacity_spin.value() / 100.0,
        }


class BalloonHandleItem(QGraphicsObject):
    def __init__(self, owner, role, square=False):
        super().__init__(owner)
        self.owner = owner
        self.role = role
        self.square = square
        self.radius = 8.0
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setZValue(1000.0)

    def boundingRect(self):
        r = self.radius + 4.0
        return QRectF(-r, -r, r * 2.0, r * 2.0)

    def shape(self):
        path = QPainterPath()
        r = self.radius + 5.0
        if self.square:
            path.addRect(QRectF(-r, -r, r * 2.0, r * 2.0))
        else:
            path.addEllipse(QPointF(0.0, 0.0), r, r)
        return path

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#1e88e5"), 1.5))
        painter.setBrush(QBrush(QColor("#ffffff")))
        if self.square:
            r = self.radius
            painter.drawRect(QRectF(-r, -r, r * 2.0, r * 2.0))
        else:
            painter.drawEllipse(QPointF(0.0, 0.0), self.radius, self.radius)

    def hoverEnterEvent(self, event):
        if self.role in {"tl", "br"}:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif self.role in {"tr", "bl"}:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)
        super().hoverEnterEvent(event)

    def mousePressEvent(self, event):
        self.owner._begin_child_handle_drag(self.role)
        event.accept()

    def mouseMoveEvent(self, event):
        self.owner._drag_child_handle(
            self.role,
            event.scenePos(),
        )
        event.accept()

    def mouseReleaseEvent(self, event):
        self.owner._end_child_handle_drag(self.role)
        event.accept()


class BalloonAnnotationItem(QGraphicsObject):
    MIN_SIZE = 28.0

    def __init__(self, record):
        super().__init__()
        self.record = record
        self._resize_start_rect = QRectF()
        self._resize_start_pos = QPointF()

        self.setAcceptHoverEvents(True)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

        self.record.setdefault("outlet_angle", 90.0)
        self.record.setdefault("arrow_enabled", True)

        self._handles = {
            "tl": BalloonHandleItem(self, "tl"),
            "tr": BalloonHandleItem(self, "tr"),
            "bl": BalloonHandleItem(self, "bl"),
            "br": BalloonHandleItem(self, "br"),
            "tip": BalloonHandleItem(self, "tip"),
            "outlet": BalloonHandleItem(
                self,
                "outlet",
                square=True,
            ),
        }
        self._update_handle_positions()
        self._update_handle_visibility()

    def _rect(self):
        return QRectF(
            0.0,
            0.0,
            max(float(self.record.get("width", 52.0)), self.MIN_SIZE),
            max(float(self.record.get("height", 52.0)), self.MIN_SIZE),
        )

    def _tip(self):
        return QPointF(
            float(self.record.get("leader_dx", -45.0)),
            float(self.record.get("leader_dy", 85.0)),
        )

    def _outlet(self):
        rect = self._rect()
        angle = math.radians(
            float(self.record.get("outlet_angle", 90.0))
        )
        return QPointF(
            rect.center().x()
            + math.cos(angle) * rect.width() / 2.0,
            rect.center().y()
            + math.sin(angle) * rect.height() / 2.0,
        )

    def boundingRect(self):
        rect = self._rect()
        if bool(self.record.get("arrow_enabled", True)):
            rect = rect.united(
                QRectF(self._tip(), self._outlet()).normalized()
            )
        return rect.adjusted(-18.0, -18.0, 18.0, 18.0)

    def shape(self):
        path = QPainterPath()
        path.addEllipse(self._rect())

        if bool(self.record.get("arrow_enabled", True)):
            leader = QPainterPath()
            leader.moveTo(self._outlet())
            leader.lineTo(self._tip())
            stroker = QPainterPathStroker()
            stroker.setWidth(
                max(
                    float(self.record.get("line_width", 2.0)) + 12.0,
                    16.0,
                )
            )
            path = path.united(stroker.createStroke(leader))
        return path

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self._rect()
        outlet = self._outlet()
        tip = self._tip()

        border = _qcolor(self.record.get("color"), "#d00000")
        fill = _qcolor(self.record.get("fill_color"), "#ffffff")
        fill.setAlphaF(
            max(
                0.0,
                min(float(self.record.get("fill_opacity", 1.0)), 1.0),
            )
        )
        text_color = _qcolor(
            self.record.get("text_color"),
            "#d00000",
        )
        arrow_color = _qcolor(
            self.record.get(
                "arrow_color",
                self.record.get("color", "#d00000"),
            )
        )
        line_width = max(
            float(self.record.get("line_width", 2.0)),
            0.5,
        )

        painter.setPen(QPen(border, line_width))
        painter.setBrush(QBrush(fill))
        painter.drawEllipse(rect)

        if bool(self.record.get("arrow_enabled", True)):
            painter.setPen(
                QPen(
                    arrow_color,
                    line_width,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(outlet, tip)

            vector = tip - outlet
            length = max(math.hypot(vector.x(), vector.y()), 0.001)
            ux = vector.x() / length
            uy = vector.y() / length
            px = -uy
            py = ux
            arrow = QPolygonF(
                [
                    tip,
                    QPointF(
                        tip.x() - ux * 10.0 + px * 5.0,
                        tip.y() - uy * 10.0 + py * 5.0,
                    ),
                    QPointF(
                        tip.x() - ux * 10.0 - px * 5.0,
                        tip.y() - uy * 10.0 - py * 5.0,
                    ),
                ]
            )
            painter.setBrush(QBrush(arrow_color))
            painter.drawPolygon(arrow)

        font = QFont()
        font.setBold(True)
        font.setPointSizeF(
            max(float(self.record.get("font_size", 16.0)), 6.0)
        )
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(
            rect.adjusted(4.0, 2.0, -4.0, -2.0),
            Qt.AlignmentFlag.AlignCenter,
            str(self.record.get("text", "1")),
        )

        if self.isSelected():
            painter.setPen(
                QPen(
                    QColor("#1e88e5"),
                    1.0,
                    Qt.PenStyle.DashLine,
                )
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._update_handle_visibility()
        return super().itemChange(change, value)

    def _update_handle_visibility(self):
        visible = self.isSelected()
        arrow_visible = (
            visible
            and bool(self.record.get("arrow_enabled", True))
        )
        for role, handle in self._handles.items():
            handle.setVisible(
                arrow_visible
                if role in {"tip", "outlet"}
                else visible
            )

    def _update_handle_positions(self):
        rect = self._rect()
        positions = {
            "tl": rect.topLeft(),
            "tr": rect.topRight(),
            "bl": rect.bottomLeft(),
            "br": rect.bottomRight(),
            "tip": self._tip(),
            "outlet": self._outlet(),
        }
        for role, point in positions.items():
            self._handles[role].setPos(point)

    def _begin_child_handle_drag(self, role):
        if role in {"tl", "tr", "bl", "br"}:
            self._resize_start_rect = QRectF(self._rect())
            self._resize_start_pos = QPointF(self.pos())

    def _drag_child_handle(self, role, scene_pos):
        local = self.mapFromScene(scene_pos)

        if role == "tip":
            self.prepareGeometryChange()
            self.record["leader_dx"] = float(local.x())
            self.record["leader_dy"] = float(local.y())
            self._update_handle_positions()
            self.update()
            return

        if role == "outlet":
            rect = self._rect()
            center = rect.center()
            delta = local - center
            self.record["outlet_angle"] = math.degrees(
                math.atan2(delta.y(), delta.x())
            )
            self._update_handle_positions()
            self.update()
            return

        rect = QRectF(self._resize_start_rect)
        position = QPointF(self._resize_start_pos)

        if "l" in role:
            new_left = min(
                local.x(),
                rect.right() - self.MIN_SIZE,
            )
            position.setX(
                position.x() + new_left - rect.left()
            )
            rect.setLeft(new_left)

        if "r" in role:
            rect.setRight(
                max(
                    local.x(),
                    rect.left() + self.MIN_SIZE,
                )
            )

        if "t" in role:
            new_top = min(
                local.y(),
                rect.bottom() - self.MIN_SIZE,
            )
            position.setY(
                position.y() + new_top - rect.top()
            )
            rect.setTop(new_top)

        if "b" in role:
            rect.setBottom(
                max(
                    local.y(),
                    rect.top() + self.MIN_SIZE,
                )
            )

        self.prepareGeometryChange()
        self.record["width"] = float(rect.width())
        self.record["height"] = float(rect.height())
        self.setPos(position)
        self._update_handle_positions()
        self.update()

    def _end_child_handle_drag(self, role):
        self._resize_start_rect = QRectF()
        self._resize_start_pos = QPointF()
        self._update_handle_positions()
        self.update()

    def _edit_properties(self):
        dialog = BalloonPropertiesDialog(None, self.record)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.prepareGeometryChange()
            self.record.update(dialog.values())
            self._update_handle_positions()
            self._update_handle_visibility()
            self.update()

    def mouseDoubleClickEvent(self, event):
        self._edit_properties()
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu()
        action = menu.addAction("バルーンのプロパティ...")
        selected = menu.exec(event.screenPos())
        if selected is action:
            self._edit_properties()
        event.accept()

    def refresh_from_record(self):
        self.prepareGeometryChange()
        self.record.setdefault("arrow_enabled", True)
        self._update_handle_positions()
        self._update_handle_visibility()
        self.update()


def _next_balloon_number(view):
    values = []
    for record in getattr(view, "_annotation_records", []):
        if record.get("type") != "balloon":
            continue
        try:
            values.append(int(str(record.get("text", "")).strip()))
        except ValueError:
            continue
    return max(values, default=0) + 1


def install_balloon_annotation(main_window):
    view = main_window.view
    if getattr(view, "_balloon_annotation_installed", False):
        return

    view._balloon_annotation_installed = True
    original_create_item = view._create_annotation_item
    original_mouse_press = view.mousePressEvent
    original_set_mode = view.set_annotation_mode

    def set_mode(mode):
        if mode == "balloon":
            view.annotation_mode = mode
            view.setCursor(Qt.CursorShape.CrossCursor)
            try:
                view.annotation_mode_changed.emit(mode)
            except (AttributeError, RuntimeError):
                pass
            return
        original_set_mode(mode)

    def create_item(record):
        if record.get("type") != "balloon":
            return original_create_item(record)

        view._ensure_annotation_identity(record)
        origin = view._page_origins.get(record["page_index"])
        if origin is None:
            return None

        item = BalloonAnnotationItem(record)
        item.setPos(
            origin[0] + float(record.get("x", 0.0)),
            origin[1] + float(record.get("y", 0.0)),
        )
        item.setZValue(float(record.get("z", 20.0)))
        item.setVisible(bool(record.get("visible", True)))

        locked = bool(record.get("locked", False))
        item.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
            not locked,
        )
        item.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,
            not locked,
        )

        view.scene.addItem(item)
        view._annotation_items.append(item)
        view._refresh_selection_overlay()
        return item

    def add_balloon(page_index, point, text=None):
        before = view._history_snapshot()
        default_text = str(_next_balloon_number(view))
        label = str(text or default_text).strip() or default_text

        defaults = view.annotation_defaults(
            "balloon"
        )
        width = max(
            float(
                defaults.get(
                    "width",
                    52.0,
                )
            ),
            28.0,
        )
        height = max(
            float(
                defaults.get(
                    "height",
                    52.0,
                )
            ),
            28.0,
        )
        border_color = str(
            defaults.get(
                "color",
                "#d00000",
            )
        )

        record = {
            "id": str(uuid.uuid4()),
            "type": "balloon",
            "page_index": int(page_index),
            "x": float(point.x() + 45.0),
            "y": float(point.y() - 85.0),
            "width": width,
            "height": height,
            "text": label,
            "font_size": float(
                defaults.get(
                    "font_size",
                    16.0,
                )
            ),
            "text_color": str(
                defaults.get(
                    "text_color",
                    "#d00000",
                )
            ),
            "color": border_color,
            "fill_color": str(
                defaults.get(
                    "fill_color",
                    "#ffffff",
                )
            ),
            "fill_opacity": float(
                defaults.get(
                    "fill_opacity",
                    1.0,
                )
            ),
            "arrow_color": str(
                defaults.get(
                    "arrow_color",
                    border_color,
                )
            ),
            "arrow_enabled": bool(
                defaults.get(
                    "arrow_enabled",
                    True,
                )
            ),
            "line_width": float(
                defaults.get(
                    "line_width",
                    2.0,
                )
            ),
            "leader_dx": -45.0,
            "leader_dy": 85.0,
            "outlet_angle": 90.0,
            "z": view._next_annotation_z(),
        }

        view._annotation_records.append(record)
        item = view._create_annotation_item(record)
        if item is not None:
            view.scene.clearSelection()
            item.setSelected(True)
            view.annotation_selected.emit(item)
        view._commit_history_change(before)
        return item

    def _balloon_item_at_view_position(view_position):
        scene_position = view.mapToScene(
            view_position.toPoint()
        )

        # Resize and leader handles are painted slightly outside the ellipse.
        # They are inside boundingRect(), but not always inside shape(), so
        # QGraphicsScene.itemAt() / _annotation_item_near() can miss them.
        candidates = list(
            getattr(
                view,
                "_annotation_items",
                [],
            )
        )
        candidates.sort(
            key=lambda item: (
                1 if item.isSelected() else 0,
                item.zValue(),
            ),
            reverse=True,
        )

        for item in candidates:
            if not isinstance(
                item,
                BalloonAnnotationItem,
            ):
                continue
            if not item.isVisible():
                continue

            try:
                local_position = item.mapFromScene(
                    scene_position
                )
                hit_rect = item.boundingRect().adjusted(
                    -4.0,
                    -4.0,
                    4.0,
                    4.0,
                )
                if hit_rect.contains(local_position):
                    return item
            except RuntimeError:
                continue

        return None

    def mouse_press(event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and view.annotation_mode == "balloon"
        ):
            existing_balloon = (
                _balloon_item_at_view_position(
                    event.position()
                )
            )

            if existing_balloon is not None:
                # Pass the original event through QGraphicsView so the
                # BalloonAnnotationItem receives mousePressEvent. This is
                # required for body movement, resize handles, outlet handle,
                # and leader-tip handle.
                original_mouse_press(event)
                return

            nearby = view._annotation_item_near(
                event.position().toPoint()
            )
            if nearby is not None:
                original_mouse_press(event)
                return

            hit = view._page_point_at(
                view.mapToScene(
                    event.position().toPoint()
                )
            )
            if hit is not None:
                page_index, page_point = hit
                default_text = str(
                    _next_balloon_number(view)
                )
                text, accepted = QInputDialog.getText(
                    main_window,
                    "バルーン追加",
                    "番号または文字:",
                    text=default_text,
                )
                if accepted:
                    add_balloon(
                        page_index,
                        page_point,
                        text,
                    )
                event.accept()
                return

        original_mouse_press(event)

    view.set_annotation_mode = set_mode
    view._create_annotation_item = create_item
    view.mousePressEvent = mouse_press
    view.add_balloon_overlay = add_balloon

    action = QAction("⭕ バルーン", main_window)
    action.setCheckable(True)
    action.setToolTip("番号付きバルーンを配置")
    action.triggered.connect(
        lambda _checked=False: view.set_annotation_mode("balloon")
    )
    main_window.annotation_group.addAction(action)

    shape_menu = main_window.shape_tool_button.menu()
    shape_menu.addAction(action)

    main_window.balloon_action = action


def _balloon_pdf_font_name(value):
    text = str(value or "")
    return (
        "japan"
        if any(
            ord(character) > 127
            for character in text
        )
        else "helv"
    )


def _draw_balloon_text(
    page,
    rect,
    value,
    fontsize,
    color,
):
    text = str(value or "")
    size = max(
        float(fontsize),
        6.0,
    )
    text_height = size * 1.45
    top = (
        rect.y0
        + (
            rect.height
            - text_height
        )
        / 2.0
        + size * 0.08
    )
    text_rect = fitz.Rect(
        rect.x0 + 2.0,
        top,
        rect.x1 - 2.0,
        min(
            top + text_height,
            rect.y1,
        ),
    )

    preferred_font = _balloon_pdf_font_name(
        text
    )
    try:
        result = page.insert_textbox(
            text_rect,
            text,
            fontsize=size,
            fontname=preferred_font,
            color=color,
            align=fitz.TEXT_ALIGN_CENTER,
            overlay=True,
        )
        if result >= 0:
            return result
    except Exception:
        pass

    return page.insert_textbox(
        text_rect,
        text,
        fontsize=size,
        fontname=(
            "helv"
            if preferred_font == "japan"
            else "japan"
        ),
        color=color,
        align=fitz.TEXT_ALIGN_CENTER,
        overlay=True,
    )


def draw_balloon_annotation(page, record):
    return draw_raster_annotation(
        page,
        record,
    )


def _fitz_color(value):
    color = _qcolor(value, "#000000")
    return (color.redF(), color.greenF(), color.blueF())
