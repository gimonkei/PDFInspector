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
    QFontMetricsF,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsObject,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


STAMP_PRESETS = (
    "見積用",
    "社外秘",
    "CONFIDENTIAL",
    "仮",
    "参考",
)


def _qcolor(value, fallback="#d00000"):
    color = QColor(str(value or fallback))
    return color if color.isValid() else QColor(fallback)


def _set_color_button(button, color):
    name = color.name(QColor.NameFormat.HexRgb)
    foreground = (
        "#000000"
        if color.lightness() > 145
        else "#ffffff"
    )
    button.setText(name.upper())
    button.setStyleSheet(
        "QPushButton {"
        f"background-color: {name};"
        f"color: {foreground};"
        "padding: 5px 12px;"
        "}"
    )


class StampPropertiesDialog(QDialog):
    def __init__(self, parent, record):
        super().__init__(parent)
        self.setWindowTitle("スタンプのプロパティ")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.text = str(record.get("text", ""))
        self._color = _qcolor(
            record.get("color"),
            "#d00000",
        )

        self.color_button = QPushButton(self)
        _set_color_button(
            self.color_button,
            self._color,
        )
        self.color_button.clicked.connect(
            self._choose_color
        )
        form.addRow("色:", self.color_button)

        self.width_spin = QDoubleSpinBox(self)
        self.width_spin.setRange(30.0, 1000.0)
        self.width_spin.setValue(
            max(
                float(record.get("width", 92.0)),
                30.0,
            )
        )
        self.width_spin.setSuffix(" pt")
        form.addRow("幅:", self.width_spin)

        self.height_spin = QDoubleSpinBox(self)
        self.height_spin.setRange(20.0, 500.0)
        self.height_spin.setValue(
            max(
                float(record.get("height", 34.0)),
                20.0,
            )
        )
        self.height_spin.setSuffix(" pt")
        form.addRow("高さ:", self.height_spin)

        self.font_spin = QDoubleSpinBox(self)
        self.font_spin.setRange(6.0, 144.0)
        self.font_spin.setValue(
            max(
                float(record.get("font_size", 14.0)),
                6.0,
            )
        )
        self.font_spin.setSuffix(" pt")
        form.addRow("文字サイズ:", self.font_spin)

        self.line_spin = QDoubleSpinBox(self)
        self.line_spin.setRange(0.5, 20.0)
        self.line_spin.setValue(
            max(
                float(record.get("line_width", 2.5)),
                0.5,
            )
        )
        self.line_spin.setSuffix(" pt")
        form.addRow("枠線の太さ:", self.line_spin)

        layout.addLayout(form)

        note = QLabel(
            "選択中は四隅の青いハンドルをドラッグして"
            "サイズを直接変更できます。",
            self,
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _choose_color(self):
        selected = QColorDialog.getColor(
            self._color,
            self,
            "スタンプの色",
        )
        if selected.isValid():
            selected.setAlpha(255)
            self._color = selected
            _set_color_button(
                self.color_button,
                selected,
            )

    def values(self):
        return {
            "color": self._color.name(
                QColor.NameFormat.HexRgb
            ),
            "width": self.width_spin.value(),
            "height": self.height_spin.value(),
            "font_size": self.font_spin.value(),
            "line_width": self.line_spin.value(),
        }


class StampAnnotationItem(QGraphicsObject):
    HANDLE_RADIUS = 6.0
    MIN_WIDTH = 30.0
    MIN_HEIGHT = 20.0

    def __init__(self, record):
        super().__init__()
        self.record = record
        self._resize_corner = None
        self._resize_start_rect = None
        self._resize_start_pos = None
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
            max(
                float(
                    self.record.get(
                        "width",
                        92.0,
                    )
                ),
                self.MIN_WIDTH,
            ),
            max(
                float(
                    self.record.get(
                        "height",
                        34.0,
                    )
                ),
                self.MIN_HEIGHT,
            ),
        )

    def _handles(self):
        rect = self._rect()
        return {
            "tl": rect.topLeft(),
            "tr": rect.topRight(),
            "bl": rect.bottomLeft(),
            "br": rect.bottomRight(),
        }

    def boundingRect(self):
        return self._rect().adjusted(
            -10.0,
            -10.0,
            10.0,
            10.0,
        )

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )
        rect = self._rect()
        color = _qcolor(
            self.record.get("color")
        )
        color.setAlphaF(
            max(
                0.0,
                min(
                    float(
                        self.record.get(
                            "opacity",
                            1.0,
                        )
                    ),
                    1.0,
                ),
            )
        )

        painter.setPen(
            QPen(
                color,
                max(
                    float(
                        self.record.get(
                            "line_width",
                            2.5,
                        )
                    ),
                    0.5,
                ),
            )
        )
        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )
        painter.drawRoundedRect(
            rect,
            3.0,
            3.0,
        )

        font = QFont()
        font.setBold(True)
        font.setPointSizeF(
            max(
                float(
                    self.record.get(
                        "font_size",
                        14.0,
                    )
                ),
                6.0,
            )
        )
        painter.setFont(font)
        painter.drawText(
            rect.adjusted(
                3.0,
                1.0,
                -3.0,
                -1.0,
            ),
            Qt.AlignmentFlag.AlignCenter,
            str(
                self.record.get(
                    "text",
                    "",
                )
            ),
        )

        if self.isSelected():
            painter.setPen(
                QPen(
                    QColor(0, 120, 215),
                    1.0,
                    Qt.PenStyle.DashLine,
                )
            )
            painter.drawRect(rect)

            painter.setPen(
                QPen(
                    QColor(0, 120, 215),
                    1.4,
                )
            )
            painter.setBrush(
                QBrush(QColor(255, 255, 255))
            )
            for point in self._handles().values():
                painter.drawEllipse(
                    point,
                    self.HANDLE_RADIUS,
                    self.HANDLE_RADIUS,
                )

    def _handle_at(self, point):
        for name, handle in self._handles().items():
            delta = point - handle
            if (
                delta.x() * delta.x()
                + delta.y() * delta.y()
                <= (
                    self.HANDLE_RADIUS + 4.0
                )
                ** 2
            ):
                return name
        return None

    def hoverMoveEvent(self, event):
        handle = (
            self._handle_at(event.pos())
            if self.isSelected()
            else None
        )
        if handle in {"tl", "br"}:
            self.setCursor(
                Qt.CursorShape.SizeFDiagCursor
            )
        elif handle in {"tr", "bl"}:
            self.setCursor(
                Qt.CursorShape.SizeBDiagCursor
            )
        else:
            self.setCursor(
                Qt.CursorShape.SizeAllCursor
            )
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        handle = (
            self._handle_at(event.pos())
            if self.isSelected()
            else None
        )
        if (
            event.button()
            == Qt.MouseButton.LeftButton
            and handle is not None
        ):
            self._resize_corner = handle
            self._resize_start_rect = self._rect()
            self._resize_start_pos = QPointF(
                self.pos()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resize_corner is None:
            super().mouseMoveEvent(event)
            return

        self.prepareGeometryChange()
        point = event.pos()
        rect = QRectF(
            self._resize_start_rect
        )
        position = QPointF(
            self._resize_start_pos
        )

        if "l" in self._resize_corner:
            new_left = min(
                point.x(),
                rect.right()
                - self.MIN_WIDTH,
            )
            delta = new_left - rect.left()
            position.setX(
                position.x() + delta
            )
            rect.setLeft(new_left)

        if "r" in self._resize_corner:
            rect.setRight(
                max(
                    point.x(),
                    rect.left()
                    + self.MIN_WIDTH,
                )
            )

        if "t" in self._resize_corner:
            new_top = min(
                point.y(),
                rect.bottom()
                - self.MIN_HEIGHT,
            )
            delta = new_top - rect.top()
            position.setY(
                position.y() + delta
            )
            rect.setTop(new_top)

        if "b" in self._resize_corner:
            rect.setBottom(
                max(
                    point.y(),
                    rect.top()
                    + self.MIN_HEIGHT,
                )
            )

        old_width = max(
            float(
                self.record.get(
                    "width",
                    rect.width(),
                )
            ),
            1.0,
        )
        old_height = max(
            float(
                self.record.get(
                    "height",
                    rect.height(),
                )
            ),
            1.0,
        )
        scale = min(
            rect.width() / old_width,
            rect.height() / old_height,
        )

        self.record["width"] = float(
            rect.width()
        )
        self.record["height"] = float(
            rect.height()
        )
        self.record["font_size"] = max(
            6.0,
            float(
                self.record.get(
                    "font_size",
                    14.0,
                )
            )
            * scale,
        )
        self.setPos(position)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._resize_corner is not None:
            self._resize_corner = None
            self._resize_start_rect = None
            self._resize_start_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        dialog = StampPropertiesDialog(
            None,
            self.record,
        )
        if (
            dialog.exec()
            == QDialog.DialogCode.Accepted
        ):
            self.record.update(
                dialog.values()
            )
            self.refresh_from_record()
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu()
        action = menu.addAction(
            "スタンプのプロパティ..."
        )
        selected = menu.exec(
            event.screenPos()
        )
        if selected is action:
            dialog = StampPropertiesDialog(
                None,
                self.record,
            )
            if (
                dialog.exec()
                == QDialog.DialogCode.Accepted
            ):
                self.record.update(
                    dialog.values()
                )
                self.refresh_from_record()
        event.accept()

    def refresh_from_record(self):
        self.prepareGeometryChange()
        self.update()


class CalloutPropertiesDialog(QDialog):
    def __init__(self, parent, record):
        super().__init__(parent)
        self.setWindowTitle(
            "吹き出しのプロパティ"
        )
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._border_color = _qcolor(
            record.get("color"),
            "#d00000",
        )
        self._fill_color = _qcolor(
            record.get("fill_color"),
            "#fff8c6",
        )
        self._text_color = _qcolor(
            record.get("text_color"),
            "#000000",
        )
        self._arrow_color = _qcolor(
            record.get(
                "arrow_color",
                record.get(
                    "color",
                    "#d00000",
                ),
            ),
            "#d00000",
        )

        self.border_button = QPushButton(self)
        self.fill_button = QPushButton(self)
        self.text_button = QPushButton(self)
        self.arrow_button = QPushButton(self)

        for button, color in (
            (
                self.border_button,
                self._border_color,
            ),
            (
                self.fill_button,
                self._fill_color,
            ),
            (
                self.text_button,
                self._text_color,
            ),
            (
                self.arrow_button,
                self._arrow_color,
            ),
        ):
            _set_color_button(button, color)

        self.border_button.clicked.connect(
            lambda: self._choose_color(
                "_border_color",
                self.border_button,
                "枠線の色",
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
                "矢印の色",
            )
        )

        form.addRow(
            "枠線の色:",
            self.border_button,
        )
        form.addRow(
            "矢印の色:",
            self.arrow_button,
        )
        form.addRow(
            "背景色:",
            self.fill_button,
        )
        form.addRow(
            "文字色:",
            self.text_button,
        )

        self.line_width = QDoubleSpinBox(self)
        self.line_width.setRange(
            0.5,
            12.0,
        )
        self.line_width.setDecimals(1)
        self.line_width.setSingleStep(0.5)
        self.line_width.setSuffix(" pt")
        self.line_width.setValue(
            max(
                float(
                    record.get(
                        "line_width",
                        2.0,
                    )
                ),
                0.5,
            )
        )
        form.addRow(
            "線の太さ:",
            self.line_width,
        )

        self.corner_radius = QDoubleSpinBox(self)
        self.corner_radius.setRange(0.0, 80.0)
        self.corner_radius.setDecimals(1)
        self.corner_radius.setSingleStep(1.0)
        self.corner_radius.setSuffix(" pt")
        self.corner_radius.setValue(
            max(
                float(
                    record.get(
                        "corner_radius",
                        10.0,
                    )
                ),
                0.0,
            )
        )
        form.addRow(
            "角の丸み:",
            self.corner_radius,
        )

        self.font_size = QDoubleSpinBox(self)
        self.font_size.setRange(
            6.0,
            72.0,
        )
        self.font_size.setDecimals(1)
        self.font_size.setSuffix(" pt")
        self.font_size.setValue(
            max(
                float(
                    record.get(
                        "font_size",
                        11.0,
                    )
                ),
                6.0,
            )
        )
        form.addRow(
            "文字サイズ:",
            self.font_size,
        )

        self.fill_opacity = QSpinBox(self)
        self.fill_opacity.setRange(
            0,
            100,
        )
        self.fill_opacity.setSuffix("%")
        self.fill_opacity.setValue(
            int(
                max(
                    0.0,
                    min(
                        float(
                            record.get(
                                "fill_opacity",
                                0.72,
                            )
                        ),
                        1.0,
                    ),
                )
                * 100
            )
        )
        form.addRow(
            "背景の濃さ:",
            self.fill_opacity,
        )

        layout.addLayout(form)

        note = QLabel(
            "選択中は四隅のハンドルで吹き出しサイズを変更できます。"
            "枠上の出口ハンドルと矢印先端ハンドルも個別に移動できます。",
            self,
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(
            self.accept
        )
        buttons.rejected.connect(
            self.reject
        )
        layout.addWidget(buttons)

    def _choose_color(
        self,
        attribute,
        button,
        title,
    ):
        selected = QColorDialog.getColor(
            getattr(self, attribute),
            self,
            title,
        )
        if selected.isValid():
            selected.setAlpha(255)
            setattr(
                self,
                attribute,
                selected,
            )
            _set_color_button(
                button,
                selected,
            )

    def values(self):
        return {
            "color": self._border_color.name(
                QColor.NameFormat.HexRgb
            ),
            "arrow_color": self._arrow_color.name(
                QColor.NameFormat.HexRgb
            ),
            "fill_color": self._fill_color.name(
                QColor.NameFormat.HexRgb
            ),
            "text_color": self._text_color.name(
                QColor.NameFormat.HexRgb
            ),
            "line_width": (
                self.line_width.value()
            ),
            "corner_radius": (
                self.corner_radius.value()
            ),
            "font_size": (
                self.font_size.value()
            ),
            "fill_opacity": (
                self.fill_opacity.value()
                / 100.0
            ),
        }


class CalloutAnnotationItem(QGraphicsObject):
    TIP_RADIUS = 7.0
    OUTLET_RADIUS = 6.0
    RESIZE_RADIUS = 6.0
    MIN_WIDTH = 90.0
    MIN_HEIGHT = 46.0

    def __init__(self, record):
        super().__init__()
        self.record = record
        self._drag_handle = None
        self._resize_corner = None
        self._resize_start_rect = QRectF()
        self._resize_start_pos = QPointF()
        self._resize_start_tip = QPointF()
        self.setAcceptHoverEvents(True)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self._ensure_outlet_defaults()
        self.record.setdefault(
            "corner_radius",
            10.0,
        )

    def _rect(self):
        return QRectF(
            0.0,
            0.0,
            max(
                float(
                    self.record.get(
                        "width",
                        180.0,
                    )
                ),
                self.MIN_WIDTH,
            ),
            max(
                float(
                    self.record.get(
                        "height",
                        74.0,
                    )
                ),
                self.MIN_HEIGHT,
            ),
        )

    def _resize_handles(self):
        rect = self._rect()
        return {
            "tl": rect.topLeft(),
            "tr": rect.topRight(),
            "bl": rect.bottomLeft(),
            "br": rect.bottomRight(),
        }

    def _tip(self):
        return QPointF(
            float(
                self.record.get(
                    "leader_dx",
                    -42.0,
                )
            ),
            float(
                self.record.get(
                    "leader_dy",
                    92.0,
                )
            ),
        )

    def _ensure_outlet_defaults(self):
        self.record.setdefault(
            "outlet_edge",
            "bottom",
        )
        self.record.setdefault(
            "outlet_t",
            0.5,
        )

    def _outlet(self):
        rect = self._rect()
        edge = str(
            self.record.get(
                "outlet_edge",
                "bottom",
            )
        )
        t = max(
            0.0,
            min(
                float(
                    self.record.get(
                        "outlet_t",
                        0.5,
                    )
                ),
                1.0,
            ),
        )

        if edge == "top":
            return QPointF(
                rect.left()
                + rect.width() * t,
                rect.top(),
            )
        if edge == "left":
            return QPointF(
                rect.left(),
                rect.top()
                + rect.height() * t,
            )
        if edge == "right":
            return QPointF(
                rect.right(),
                rect.top()
                + rect.height() * t,
            )
        return QPointF(
            rect.left()
            + rect.width() * t,
            rect.bottom(),
        )

    def boundingRect(self):
        rect = self._rect()
        leader_rect = QRectF(
            self._tip(),
            self._outlet(),
        ).normalized()
        return rect.united(
            leader_rect
        ).adjusted(
            -12.0,
            -12.0,
            12.0,
            12.0,
        )

    def paint(
        self,
        painter,
        option,
        widget=None,
    ):
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )
        rect = self._rect()
        tip = self._tip()
        outlet = self._outlet()

        border_color = _qcolor(
            self.record.get("color")
        )
        arrow_color = _qcolor(
            self.record.get(
                "arrow_color",
                self.record.get(
                    "color",
                    "#d00000",
                ),
            )
        )
        fill = _qcolor(
            self.record.get(
                "fill_color",
                "#fff8c6",
            ),
            "#fff8c6",
        )
        fill.setAlphaF(
            max(
                0.0,
                min(
                    float(
                        self.record.get(
                            "fill_opacity",
                            0.72,
                        )
                    ),
                    1.0,
                ),
            )
        )
        line_width = max(
            float(
                self.record.get(
                    "line_width",
                    2.0,
                )
            ),
            0.5,
        )

        painter.setPen(
            QPen(
                border_color,
                line_width,
            )
        )
        painter.setBrush(
            QBrush(fill)
        )
        corner_radius = max(
            float(
                self.record.get(
                    "corner_radius",
                    10.0,
                )
            ),
            0.0,
        )
        painter.drawRoundedRect(
            rect,
            corner_radius,
            corner_radius,
        )

        painter.setPen(
            QPen(
                arrow_color,
                line_width,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )
        painter.drawLine(
            outlet,
            tip,
        )

        vector = tip - outlet
        length = max(
            math.hypot(
                vector.x(),
                vector.y(),
            ),
            0.001,
        )
        ux = vector.x() / length
        uy = vector.y() / length
        px = -uy
        py = ux
        arrow = QPolygonF(
            [
                tip,
                QPointF(
                    tip.x()
                    - ux * 10.0
                    + px * 5.0,
                    tip.y()
                    - uy * 10.0
                    + py * 5.0,
                ),
                QPointF(
                    tip.x()
                    - ux * 10.0
                    - px * 5.0,
                    tip.y()
                    - uy * 10.0
                    - py * 5.0,
                ),
            ]
        )
        painter.setBrush(
            QBrush(arrow_color)
        )
        painter.drawPolygon(arrow)

        font = QFont()
        font.setPointSizeF(
            max(
                float(
                    self.record.get(
                        "font_size",
                        11.0,
                    )
                ),
                6.0,
            )
        )
        painter.setFont(font)
        painter.setPen(
            _qcolor(
                self.record.get(
                    "text_color",
                    "#000000",
                )
            )
        )
        painter.drawText(
            rect.adjusted(
                8.0,
                6.0,
                -8.0,
                -6.0,
            ),
            Qt.AlignmentFlag.AlignCenter
            | Qt.TextFlag.TextWordWrap,
            str(
                self.record.get(
                    "text",
                    "",
                )
            ),
        )

        if self.isSelected():
            painter.setPen(
                QPen(
                    QColor(0, 120, 215),
                    1.0,
                    Qt.PenStyle.DashLine,
                )
            )
            painter.setBrush(
                Qt.BrushStyle.NoBrush
            )
            painter.drawRect(rect)

            painter.setPen(
                QPen(
                    QColor(0, 120, 215),
                    1.5,
                )
            )
            painter.setBrush(
                QBrush(
                    QColor(255, 255, 255)
                )
            )
            painter.drawEllipse(
                tip,
                self.TIP_RADIUS,
                self.TIP_RADIUS,
            )
            painter.drawRect(
                QRectF(
                    outlet.x()
                    - self.OUTLET_RADIUS,
                    outlet.y()
                    - self.OUTLET_RADIUS,
                    self.OUTLET_RADIUS * 2.0,
                    self.OUTLET_RADIUS * 2.0,
                )
            )
            for point in self._resize_handles().values():
                painter.drawRect(
                    QRectF(
                        point.x() - self.RESIZE_RADIUS,
                        point.y() - self.RESIZE_RADIUS,
                        self.RESIZE_RADIUS * 2.0,
                        self.RESIZE_RADIUS * 2.0,
                    )
                )

    @staticmethod
    def _contains_handle(
        point,
        handle,
        radius,
    ):
        delta = point - handle
        return (
            delta.x() * delta.x()
            + delta.y() * delta.y()
            <= (
                radius + 4.0
            )
            ** 2
        )

    def _handle_at(self, point):
        if self._contains_handle(
            point,
            self._tip(),
            self.TIP_RADIUS,
        ):
            return "tip"
        if self._contains_handle(
            point,
            self._outlet(),
            self.OUTLET_RADIUS,
        ):
            return "outlet"

        for name, handle in self._resize_handles().items():
            if self._contains_handle(
                point,
                handle,
                self.RESIZE_RADIUS,
            ):
                return f"resize_{name}"

        return None

    def hoverMoveEvent(self, event):
        handle = (
            self._handle_at(
                event.pos()
            )
            if self.isSelected()
            else None
        )
        if handle in {"resize_tl", "resize_br"}:
            cursor = Qt.CursorShape.SizeFDiagCursor
        elif handle in {"resize_tr", "resize_bl"}:
            cursor = Qt.CursorShape.SizeBDiagCursor
        elif handle is not None:
            cursor = Qt.CursorShape.CrossCursor
        else:
            cursor = Qt.CursorShape.SizeAllCursor

        self.setCursor(cursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        handle = (
            self._handle_at(
                event.pos()
            )
            if self.isSelected()
            else None
        )
        if (
            event.button()
            == Qt.MouseButton.LeftButton
            and handle is not None
        ):
            if handle.startswith("resize_"):
                self._resize_corner = handle.removeprefix("resize_")
                self._resize_start_rect = QRectF(self._rect())
                self._resize_start_pos = QPointF(self.pos())
                self._resize_start_tip = QPointF(self._tip())
            else:
                self._drag_handle = handle
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resize_corner is not None:
            self._resize_callout(event.pos())
            event.accept()
            return

        if self._drag_handle == "tip":
            self.prepareGeometryChange()
            self.record["leader_dx"] = float(
                event.pos().x()
            )
            self.record["leader_dy"] = float(
                event.pos().y()
            )
            self.update()
            event.accept()
            return

        if self._drag_handle == "outlet":
            self.prepareGeometryChange()
            self._set_outlet_from_point(
                event.pos()
            )
            self.update()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resize_corner is not None:
            self._resize_corner = None
            self._resize_start_rect = QRectF()
            self._resize_start_pos = QPointF()
            self._resize_start_tip = QPointF()
            self.update()
            event.accept()
            return

        if self._drag_handle is not None:
            self._drag_handle = None
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _resize_callout(self, point):
        self.prepareGeometryChange()

        rect = QRectF(self._resize_start_rect)
        position = QPointF(self._resize_start_pos)
        corner = self._resize_corner

        if "l" in corner:
            new_left = min(
                point.x(),
                rect.right() - self.MIN_WIDTH,
            )
            shift_x = new_left - rect.left()
            rect.setLeft(new_left)
            position.setX(position.x() + shift_x)
        if "r" in corner:
            rect.setRight(
                max(point.x(), rect.left() + self.MIN_WIDTH)
            )
        if "t" in corner:
            new_top = min(
                point.y(),
                rect.bottom() - self.MIN_HEIGHT,
            )
            shift_y = new_top - rect.top()
            rect.setTop(new_top)
            position.setY(position.y() + shift_y)
        if "b" in corner:
            rect.setBottom(
                max(point.y(), rect.top() + self.MIN_HEIGHT)
            )

        position_delta = position - self._resize_start_pos

        self.record["width"] = float(rect.width())
        self.record["height"] = float(rect.height())

        # Keep the arrow tip at the same scene position when resizing from
        # the left or top edge.
        self.record["leader_dx"] = float(
            self._resize_start_tip.x() - position_delta.x()
        )
        self.record["leader_dy"] = float(
            self._resize_start_tip.y() - position_delta.y()
        )

        self.setPos(position)
        self.update()

    def _set_outlet_from_point(
        self,
        point,
    ):
        rect = self._rect()
        distances = {
            "top": abs(
                point.y() - rect.top()
            ),
            "bottom": abs(
                point.y() - rect.bottom()
            ),
            "left": abs(
                point.x() - rect.left()
            ),
            "right": abs(
                point.x() - rect.right()
            ),
        }
        edge = min(
            distances,
            key=distances.get,
        )

        if edge in {"top", "bottom"}:
            t = (
                point.x() - rect.left()
            ) / max(
                rect.width(),
                0.001,
            )
        else:
            t = (
                point.y() - rect.top()
            ) / max(
                rect.height(),
                0.001,
            )

        self.record["outlet_edge"] = edge
        self.record["outlet_t"] = max(
            0.0,
            min(float(t), 1.0),
        )

    def _edit_properties(self):
        dialog = CalloutPropertiesDialog(
            None,
            self.record,
        )
        if (
            dialog.exec()
            == QDialog.DialogCode.Accepted
        ):
            values = dialog.values()
            self.record.update(values)
            self.refresh_from_record()

            try:
                scene = self.scene()
                views = (
                    scene.views()
                    if scene is not None
                    else []
                )
                if views:
                    window = views[0].window()
                    remember = getattr(
                        window,
                        "_remember_annotation_defaults",
                        None,
                    )
                    if callable(remember):
                        remember(
                            "callout",
                            {
                                **values,
                                "width": float(
                                    self.record.get(
                                        "width",
                                        180.0,
                                    )
                                ),
                                "height": float(
                                    self.record.get(
                                        "height",
                                        74.0,
                                    )
                                ),
                            },
                        )
            except RuntimeError:
                pass

    def mouseDoubleClickEvent(self, event):
        self._edit_properties()
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu()
        action = menu.addAction(
            "吹き出しのプロパティ..."
        )
        selected = menu.exec(
            event.screenPos()
        )
        if selected is action:
            self._edit_properties()
        event.accept()

    def refresh_from_record(self):
        self.prepareGeometryChange()
        self._ensure_outlet_defaults()
        self.update()


def install_stamp_callout(main_window):
    view = main_window.view
    if getattr(
        view,
        "_stamp_callout_installed",
        False,
    ):
        return

    view._stamp_callout_installed = True
    view._stamp_text = STAMP_PRESETS[0]

    original_set_mode = (
        view.set_annotation_mode
    )
    original_create_item = (
        view._create_annotation_item
    )
    original_mouse_press = (
        view.mousePressEvent
    )

    def set_mode(mode):
        if mode in {
            "stamp",
            "callout",
        }:
            view.annotation_mode = mode
            view.setCursor(
                Qt.CursorShape.CrossCursor
            )
            return
        original_set_mode(mode)

    def create_item(record):
        if record.get("type") not in {
            "stamp",
            "callout",
        }:
            return original_create_item(
                record
            )

        view._ensure_annotation_identity(
            record
        )
        origin = view._page_origins.get(
            record["page_index"]
        )
        if origin is None:
            return None

        item = (
            StampAnnotationItem(record)
            if record["type"] == "stamp"
            else CalloutAnnotationItem(record)
        )
        item.setPos(
            origin[0]
            + float(
                record.get("x", 0.0)
            ),
            origin[1]
            + float(
                record.get("y", 0.0)
            ),
        )
        item.setZValue(
            float(record.get("z", 20.0))
        )
        item.setVisible(
            bool(
                record.get(
                    "visible",
                    True,
                )
            )
        )

        locked = bool(
            record.get(
                "locked",
                False,
            )
        )
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

    def add_stamp(
        page_index,
        point,
        text,
    ):
        text = str(text).strip()
        if not text:
            return None

        before = view._history_snapshot()

        font = QFont()
        font.setBold(True)
        font_size = (
            14.0
            if len(text) <= 8
            else 12.0
        )
        font.setPointSizeF(font_size)
        metrics = QFontMetricsF(font)

        width = max(
            48.0,
            min(
                280.0,
                metrics.horizontalAdvance(text)
                + 14.0,
            ),
        )
        height = max(
            28.0,
            metrics.height() + 8.0,
        )

        record = {
            "id": str(uuid.uuid4()),
            "type": "stamp",
            "page_index": int(page_index),
            "x": float(
                point.x() - width / 2.0
            ),
            "y": float(
                point.y() - height / 2.0
            ),
            "width": width,
            "height": height,
            "text": text,
            "font_size": font_size,
            "color": "#d00000",
            "line_width": 2.5,
            "opacity": 1.0,
            "z": view._next_annotation_z(),
        }

        view._annotation_records.append(
            record
        )
        item = view._create_annotation_item(
            record
        )
        if item:
            view.scene.clearSelection()
            item.setSelected(True)
            view.annotation_selected.emit(
                item
            )
        view._commit_history_change(before)
        return item

    def add_callout(
        page_index,
        point,
        text,
    ):
        text = str(text).strip()
        if not text:
            return None

        before = view._history_snapshot()
        defaults = view.annotation_defaults(
            "callout"
        )

        width = max(
            float(
                defaults.get(
                    "width",
                    180.0,
                )
            ),
            90.0,
        )
        height = max(
            float(
                defaults.get(
                    "height",
                    74.0,
                )
            ),
            46.0,
        )

        tip_x = float(point.x())
        tip_y = float(point.y())

        margin = 12.0
        offset_x = 28.0
        offset_y = 28.0

        page_width = None
        page_height = None
        try:
            document = getattr(
                main_window,
                "document",
                None,
            )
            pdf_document = getattr(
                document,
                "doc",
                None,
            )
            if (
                pdf_document is not None
                and 0 <= int(page_index) < len(pdf_document)
            ):
                page_rect = pdf_document[
                    int(page_index)
                ].rect
                page_width = float(page_rect.width)
                page_height = float(page_rect.height)
        except (AttributeError, RuntimeError):
            page_width = None
            page_height = None

        body_x = tip_x + offset_x
        body_y = tip_y + offset_y

        if (
            page_width is not None
            and body_x + width > page_width - margin
        ):
            body_x = tip_x - width - offset_x

        if (
            page_height is not None
            and body_y + height > page_height - margin
        ):
            body_y = tip_y - height - offset_y

        if page_width is not None:
            body_x = max(
                margin,
                min(
                    body_x,
                    page_width - width - margin,
                ),
            )
        if page_height is not None:
            body_y = max(
                margin,
                min(
                    body_y,
                    page_height - height - margin,
                ),
            )

        record = {
            "id": str(uuid.uuid4()),
            "type": "callout",
            "page_index": int(page_index),
            "x": float(body_x),
            "y": float(body_y),
            "width": width,
            "height": height,
            "leader_dx": float(
                tip_x - body_x
            ),
            "leader_dy": float(
                tip_y - body_y
            ),
            "outlet_edge": "bottom",
            "outlet_t": 0.5,
            "text": text,
            "font_size": float(
                defaults.get(
                    "font_size",
                    11.0,
                )
            ),
            "text_color": str(
                defaults.get(
                    "text_color",
                    "#000000",
                )
            ),
            "color": str(
                defaults.get(
                    "color",
                    "#d00000",
                )
            ),
            "arrow_color": str(
                defaults.get(
                    "arrow_color",
                    defaults.get(
                        "color",
                        "#d00000",
                    ),
                )
            ),
            "line_width": float(
                defaults.get(
                    "line_width",
                    2.0,
                )
            ),
            "corner_radius": float(
                defaults.get(
                    "corner_radius",
                    10.0,
                )
            ),
            "fill_color": str(
                defaults.get(
                    "fill_color",
                    "#fff8c6",
                )
            ),
            "fill_opacity": float(
                defaults.get(
                    "fill_opacity",
                    0.72,
                )
            ),
            "z": view._next_annotation_z(),
        }

        view._annotation_records.append(
            record
        )
        item = view._create_annotation_item(
            record
        )
        if item:
            view.scene.clearSelection()
            item.setSelected(True)
            view.annotation_selected.emit(
                item
            )
        view._commit_history_change(before)
        return item

    def mouse_press(event):
        if (
            event.button()
            == Qt.MouseButton.LeftButton
            and view.annotation_mode
            in {"stamp", "callout"}
        ):
            nearby = view._annotation_item_near(
                event.position().toPoint()
            )

            if nearby is not None:
                # Existing annotations must be handled by PDFView so the
                # QGraphicsItem receives the original press and can move or
                # resize normally.
                original_mouse_press(event)
                return

            hit = view._page_point_at(
                view.mapToScene(
                    event.position().toPoint()
                )
            )
            if hit is not None:
                page_index, page_point = hit
                if (
                    view.annotation_mode
                    == "stamp"
                ):
                    add_stamp(
                        page_index,
                        page_point,
                        view._stamp_text,
                    )
                else:
                    text, accepted = (
                        QInputDialog.getMultiLineText(
                            main_window,
                            "吹き出し",
                            "吹き出しに表示する文字:",
                            "",
                        )
                    )
                    if (
                        accepted
                        and str(text).strip()
                    ):
                        add_callout(
                            page_index,
                            page_point,
                            text,
                        )

                event.accept()
                return

        original_mouse_press(event)

    view.set_annotation_mode = set_mode
    view._create_annotation_item = (
        create_item
    )
    view.mousePressEvent = mouse_press
    view.add_stamp_overlay = add_stamp
    view.add_callout_overlay = add_callout

    shape_menu = (
        main_window.shape_tool_button.menu()
    )
    shape_menu.addSeparator()

    stamp_menu = QMenu(
        "スタンプ",
        shape_menu,
    )
    shape_menu.addMenu(stamp_menu)

    def activate_stamp(text):
        view._stamp_text = str(text)
        view.set_annotation_mode("stamp")

    for preset in STAMP_PRESETS:
        action = QAction(
            preset,
            main_window,
        )
        action.triggered.connect(
            lambda _checked=False, value=preset: (
                activate_stamp(value)
            )
        )
        stamp_menu.addAction(action)

    stamp_menu.addSeparator()
    custom_action = QAction(
        "任意文字スタンプ...",
        main_window,
    )

    def choose_custom():
        text, accepted = QInputDialog.getText(
            main_window,
            "任意文字スタンプ",
            "スタンプ文字:",
        )
        if (
            accepted
            and str(text).strip()
        ):
            activate_stamp(
                str(text).strip()
            )

    custom_action.triggered.connect(
        choose_custom
    )
    stamp_menu.addAction(custom_action)

    callout_action = QAction(
        "💬 吹き出し",
        main_window,
    )
    callout_action.setCheckable(True)
    callout_action.setToolTip(
        "指示位置をクリックして吹き出し文字を入力"
    )
    callout_action.triggered.connect(
        lambda _checked=False: (
            view.set_annotation_mode(
                "callout"
            )
        )
    )
    main_window.annotation_group.addAction(
        callout_action
    )
    shape_menu.addAction(callout_action)

    main_window.callout_action = (
        callout_action
    )
    main_window.stamp_menu = stamp_menu


def commit_annotation_to_document(
    document,
    annotation,
):
    if document.doc is None:
        return False

    page_index = int(
        annotation.get(
            "page_index",
            -1,
        )
    )
    if not (
        0 <= page_index < len(document.doc)
    ):
        return False

    return draw_pdf_annotation(
        document.doc[page_index],
        annotation,
    )


def _callout_outlet(record):
    x = float(record.get("x", 0.0))
    y = float(record.get("y", 0.0))
    width = float(
        record.get("width", 180.0)
    )
    height = float(
        record.get("height", 74.0)
    )
    edge = str(
        record.get(
            "outlet_edge",
            "bottom",
        )
    )
    t = max(
        0.0,
        min(
            float(
                record.get(
                    "outlet_t",
                    0.5,
                )
            ),
            1.0,
        ),
    )

    if edge == "top":
        return fitz.Point(
            x + width * t,
            y,
        )
    if edge == "left":
        return fitz.Point(
            x,
            y + height * t,
        )
    if edge == "right":
        return fitz.Point(
            x + width,
            y + height * t,
        )
    return fitz.Point(
        x + width * t,
        y + height,
    )


def _pdf_text_font_name(value):
    text = str(value or "")
    return (
        "japan"
        if any(
            ord(character) > 127
            for character in text
        )
        else "helv"
    )


def _centered_text_rect(
    rect,
    value,
    fontsize,
):
    text = str(value or "")
    line_count = max(
        len(text.splitlines()),
        1,
    )
    line_height = max(
        float(fontsize) * 1.25,
        7.0,
    )
    text_height = (
        line_count * line_height
    )

    available_height = max(
        float(rect.height),
        1.0,
    )
    target_height = min(
        text_height + float(fontsize) * 0.35,
        available_height,
    )
    top = (
        float(rect.y0)
        + (
            available_height
            - target_height
        )
        / 2.0
        + float(fontsize) * 0.08
    )

    return fitz.Rect(
        rect.x0,
        top,
        rect.x1,
        min(
            top + target_height,
            rect.y1,
        ),
    )


def _insert_pdf_textbox(
    page,
    rect,
    value,
    *,
    fontsize,
    color,
    align=fitz.TEXT_ALIGN_CENTER,
):
    text = str(value or "")
    preferred_font = _pdf_text_font_name(text)
    text_rect = _centered_text_rect(
        rect,
        text,
        fontsize,
    )

    try:
        result = page.insert_textbox(
            text_rect,
            text,
            fontsize=fontsize,
            fontname=preferred_font,
            color=color,
            align=align,
            overlay=True,
        )
        if result >= 0:
            return result
    except Exception:
        pass

    fallback_font = (
        "helv"
        if preferred_font == "japan"
        else "japan"
    )
    return page.insert_textbox(
        text_rect,
        text,
        fontsize=fontsize,
        fontname=fallback_font,
        color=color,
        align=align,
        overlay=True,
    )


def draw_pdf_annotation(page, record):
    kind = str(record.get("type", ""))
    if kind not in {"stamp", "callout"}:
        return False
    return draw_raster_annotation(
        page,
        record,
    )


def _fitz_color(value):
    text = str(
        value or "#000000"
    ).strip()
    named = {
        "black": "#000000",
        "red": "#ff0000",
        "blue": "#0000ff",
        "green": "#008000",
        "white": "#ffffff",
        "yellow": "#ffff00",
    }
    text = named.get(
        text.lower(),
        text,
    )

    if (
        len(text) == 7
        and text.startswith("#")
    ):
        try:
            return tuple(
                int(
                    text[index:index + 2],
                    16,
                )
                / 255.0
                for index in (
                    1,
                    3,
                    5,
                )
            )
        except ValueError:
            pass

    return (0.0, 0.0, 0.0)
