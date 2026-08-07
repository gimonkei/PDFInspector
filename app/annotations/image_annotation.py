from __future__ import annotations

import base64
import uuid

import fitz
from shiboken6 import isValid
from PySide6.QtCore import QByteArray, QEvent, QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QApplication,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


SUPPORTED_IMAGE_FILTER = (
    "画像ファイル (*.png *.jpg *.jpeg *.bmp *.webp)"
)


def _image_to_base64(image: QImage) -> str:
    buffer = QByteArray()
    from PySide6.QtCore import QBuffer, QIODevice

    device = QBuffer(buffer)
    device.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(device, "PNG")
    device.close()
    return bytes(buffer.toBase64()).decode("ascii")


def _image_from_base64(value: str) -> QImage:
    data = QByteArray.fromBase64(
        str(value or "").encode("ascii")
    )
    image = QImage()
    image.loadFromData(data, "PNG")
    return image


def _cropped_aspect_ratio(record, image):
    crop = _crop_rect_from_record(
        record,
        image,
    )
    return max(
        float(crop.width())
        / max(float(crop.height()), 0.001),
        0.001,
    )


def _crop_rect_from_record(record, image):
    width = max(image.width(), 1)
    height = max(image.height(), 1)

    left = max(
        0.0,
        min(float(record.get("crop_left", 0.0)), 0.99),
    )
    top = max(
        0.0,
        min(float(record.get("crop_top", 0.0)), 0.99),
    )
    right = max(
        left + 0.01,
        min(float(record.get("crop_right", 1.0)), 1.0),
    )
    bottom = max(
        top + 0.01,
        min(float(record.get("crop_bottom", 1.0)), 1.0),
    )

    return QRectF(
        left * width,
        top * height,
        (right - left) * width,
        (bottom - top) * height,
    )


class CropPreviewWidget(QWidget):
    cropChanged = Signal()

    HANDLE = 8.0

    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.image = QImage(image)
        self.crop = QRectF(
            0.0,
            0.0,
            float(max(self.image.width(), 1)),
            float(max(self.image.height(), 1)),
        )
        self.zoom = 1.0
        self._drag_mode = None
        self._drag_start = QPointF()
        self._crop_start = QRectF()
        self.setMinimumSize(560, 380)
        self.setMouseTracking(True)

    def set_zoom_percent(self, value):
        self.zoom = max(float(value) / 100.0, 0.1)
        self.update()

    def set_crop_normalized(self, left, top, right, bottom):
        width = max(self.image.width(), 1)
        height = max(self.image.height(), 1)
        self.crop = QRectF(
            float(left) * width,
            float(top) * height,
            max((float(right) - float(left)) * width, 1.0),
            max((float(bottom) - float(top)) * height, 1.0),
        )
        self._clamp_crop()
        self.update()

    def crop_normalized(self):
        width = max(self.image.width(), 1)
        height = max(self.image.height(), 1)
        return (
            self.crop.left() / width,
            self.crop.top() / height,
            self.crop.right() / width,
            self.crop.bottom() / height,
        )

    def reset_crop(self):
        self.crop = QRectF(
            0.0,
            0.0,
            float(max(self.image.width(), 1)),
            float(max(self.image.height(), 1)),
        )
        self.cropChanged.emit()
        self.update()

    def _image_target(self):
        available = self.rect().adjusted(18, 18, -18, -18)
        iw = max(self.image.width(), 1)
        ih = max(self.image.height(), 1)

        scale = min(
            available.width() / iw,
            available.height() / ih,
        ) * self.zoom

        width = iw * scale
        height = ih * scale
        center = available.center()

        return QRectF(
            center.x() - width / 2.0,
            center.y() - height / 2.0,
            width,
            height,
        )

    def _image_to_widget(self, point):
        target = self._image_target()
        return QPointF(
            target.left()
            + point.x()
            / max(self.image.width(), 1)
            * target.width(),
            target.top()
            + point.y()
            / max(self.image.height(), 1)
            * target.height(),
        )

    def _widget_to_image(self, point):
        target = self._image_target()
        return QPointF(
            (point.x() - target.left())
            / max(target.width(), 0.001)
            * max(self.image.width(), 1),
            (point.y() - target.top())
            / max(target.height(), 0.001)
            * max(self.image.height(), 1),
        )

    def _crop_widget_rect(self):
        top_left = self._image_to_widget(self.crop.topLeft())
        bottom_right = self._image_to_widget(
            self.crop.bottomRight()
        )
        return QRectF(top_left, bottom_right).normalized()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())

        if self.image.isNull():
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "画像を読み込めません",
            )
            return

        target = self._image_target()
        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform,
            True,
        )
        painter.drawImage(target, self.image)

        crop_rect = self._crop_widget_rect()
        shade = QColor(0, 0, 0, 115)

        painter.fillRect(
            QRectF(
                target.left(),
                target.top(),
                target.width(),
                max(crop_rect.top() - target.top(), 0.0),
            ),
            shade,
        )
        painter.fillRect(
            QRectF(
                target.left(),
                crop_rect.bottom(),
                target.width(),
                max(target.bottom() - crop_rect.bottom(), 0.0),
            ),
            shade,
        )
        painter.fillRect(
            QRectF(
                target.left(),
                crop_rect.top(),
                max(crop_rect.left() - target.left(), 0.0),
                crop_rect.height(),
            ),
            shade,
        )
        painter.fillRect(
            QRectF(
                crop_rect.right(),
                crop_rect.top(),
                max(target.right() - crop_rect.right(), 0.0),
                crop_rect.height(),
            ),
            shade,
        )

        painter.setPen(QPen(QColor("#1e88e5"), 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(crop_rect)

        painter.setBrush(QBrush(QColor("#ffffff")))
        for point in (
            crop_rect.topLeft(),
            crop_rect.topRight(),
            crop_rect.bottomLeft(),
            crop_rect.bottomRight(),
        ):
            painter.drawRect(
                QRectF(
                    point.x() - self.HANDLE,
                    point.y() - self.HANDLE,
                    self.HANDLE * 2,
                    self.HANDLE * 2,
                )
            )

    def _hit_test(self, point):
        rect = self._crop_widget_rect()
        handles = {
            "tl": rect.topLeft(),
            "tr": rect.topRight(),
            "bl": rect.bottomLeft(),
            "br": rect.bottomRight(),
        }
        for name, handle in handles.items():
            if (
                abs(point.x() - handle.x())
                <= self.HANDLE + 4
                and abs(point.y() - handle.y())
                <= self.HANDLE + 4
            ):
                return name

        if rect.contains(point):
            return "move"
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)

        mode = self._hit_test(event.position())
        if mode is None:
            return super().mousePressEvent(event)

        self._drag_mode = mode
        self._drag_start = self._widget_to_image(
            event.position()
        )
        self._crop_start = QRectF(self.crop)
        event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_mode is None:
            return super().mouseMoveEvent(event)

        current = self._widget_to_image(event.position())
        delta = current - self._drag_start
        rect = QRectF(self._crop_start)

        if self._drag_mode == "move":
            rect.translate(delta)
        else:
            if "l" in self._drag_mode:
                rect.setLeft(
                    min(
                        self._crop_start.left() + delta.x(),
                        rect.right() - 8.0,
                    )
                )
            if "r" in self._drag_mode:
                rect.setRight(
                    max(
                        self._crop_start.right() + delta.x(),
                        rect.left() + 8.0,
                    )
                )
            if "t" in self._drag_mode:
                rect.setTop(
                    min(
                        self._crop_start.top() + delta.y(),
                        rect.bottom() - 8.0,
                    )
                )
            if "b" in self._drag_mode:
                rect.setBottom(
                    max(
                        self._crop_start.bottom() + delta.y(),
                        rect.top() + 8.0,
                    )
                )

        self.crop = rect
        self._clamp_crop()
        self.cropChanged.emit()
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_mode is not None:
            self._drag_mode = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        step = 10 if event.angleDelta().y() > 0 else -10
        percent = int(self.zoom * 100) + step
        self.set_zoom_percent(
            max(10, min(percent, 400))
        )
        event.accept()

    def _clamp_crop(self):
        width = float(max(self.image.width(), 1))
        height = float(max(self.image.height(), 1))

        if self.crop.width() > width:
            self.crop.setWidth(width)
        if self.crop.height() > height:
            self.crop.setHeight(height)

        if self.crop.left() < 0:
            self.crop.moveLeft(0)
        if self.crop.top() < 0:
            self.crop.moveTop(0)
        if self.crop.right() > width:
            self.crop.moveRight(width)
        if self.crop.bottom() > height:
            self.crop.moveBottom(height)


class ImageCropDialog(QDialog):
    def __init__(self, image, record=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("画像のトリミング")
        self.resize(760, 580)

        layout = QVBoxLayout(self)

        self.preview = CropPreviewWidget(image, self)
        layout.addWidget(self.preview, 1)

        controls = QHBoxLayout()

        controls.addWidget(QLabel("表示倍率:", self))
        self.zoom_slider = QSlider(
            Qt.Orientation.Horizontal,
            self,
        )
        self.zoom_slider.setRange(10, 400)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(
            self.preview.set_zoom_percent
        )
        controls.addWidget(self.zoom_slider, 1)

        self.zoom_label = QLabel("100%", self)
        self.zoom_slider.valueChanged.connect(
            lambda value: self.zoom_label.setText(
                f"{value}%"
            )
        )
        controls.addWidget(self.zoom_label)

        reset_button = QPushButton(
            "トリミングをリセット",
            self,
        )
        reset_button.clicked.connect(
            self.preview.reset_crop
        )
        controls.addWidget(reset_button)

        layout.addLayout(controls)

        if record:
            self.preview.set_crop_normalized(
                record.get("crop_left", 0.0),
                record.get("crop_top", 0.0),
                record.get("crop_right", 1.0),
                record.get("crop_bottom", 1.0),
            )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def crop_values(self):
        left, top, right, bottom = (
            self.preview.crop_normalized()
        )
        return {
            "crop_left": left,
            "crop_top": top,
            "crop_right": right,
            "crop_bottom": bottom,
        }


class ImagePropertiesDialog(QDialog):
    def __init__(self, parent, record):
        super().__init__(parent)
        self.setWindowTitle("画像のプロパティ")
        self.setMinimumWidth(390)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.width_spin = QSpinBox(self)
        self.width_spin.setRange(20, 5000)
        self.width_spin.setValue(
            int(record.get("width", 240))
        )
        self.width_spin.setSuffix(" pt")
        form.addRow("幅:", self.width_spin)

        self.height_spin = QSpinBox(self)
        self.height_spin.setRange(20, 5000)
        self.height_spin.setValue(
            int(record.get("height", 180))
        )
        self.height_spin.setSuffix(" pt")
        form.addRow("高さ:", self.height_spin)

        self.opacity_spin = QSpinBox(self)
        self.opacity_spin.setRange(0, 100)
        self.opacity_spin.setValue(
            int(float(record.get("opacity", 1.0)) * 100)
        )
        self.opacity_spin.setSuffix("%")
        form.addRow("不透明度:", self.opacity_spin)

        self.keep_ratio = QCheckBox(
            "縦横比を維持",
            self,
        )
        self.keep_ratio.setChecked(
            bool(record.get("keep_ratio", True))
        )
        form.addRow("", self.keep_ratio)

        self.border_check = QCheckBox(
            "枠線を表示",
            self,
        )
        self.border_check.setChecked(
            bool(record.get("border_enabled", False))
        )
        form.addRow("", self.border_check)

        self._border_color = QColor(
            str(record.get("border_color", "#000000"))
        )
        if not self._border_color.isValid():
            self._border_color = QColor("#000000")

        self.border_color_button = QPushButton(self)
        self._update_color_button()
        self.border_color_button.clicked.connect(
            self._choose_border_color
        )
        form.addRow("枠線色:", self.border_color_button)

        self.border_width_spin = QSpinBox(self)
        self.border_width_spin.setRange(1, 20)
        self.border_width_spin.setValue(
            int(record.get("border_width", 1))
        )
        self.border_width_spin.setSuffix(" pt")
        form.addRow(
            "枠線太さ:",
            self.border_width_spin,
        )

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_color_button(self):
        name = self._border_color.name()
        foreground = (
            "#000000"
            if self._border_color.lightness() > 145
            else "#ffffff"
        )
        self.border_color_button.setText(name.upper())
        self.border_color_button.setStyleSheet(
            "QPushButton {"
            f"background-color: {name};"
            f"color: {foreground};"
            "padding: 5px 12px;"
            "}"
        )

    def _choose_border_color(self):
        color = QColorDialog.getColor(
            self._border_color,
            self,
            "枠線色",
        )
        if color.isValid():
            color.setAlpha(255)
            self._border_color = color
            self._update_color_button()

    def values(self):
        return {
            "width": float(self.width_spin.value()),
            "height": float(self.height_spin.value()),
            "opacity": self.opacity_spin.value() / 100.0,
            "keep_ratio": self.keep_ratio.isChecked(),
            "border_enabled": self.border_check.isChecked(),
            "border_color": self._border_color.name(),
            "border_width": float(
                self.border_width_spin.value()
            ),
        }


class ImageInteractionGuard(QObject):
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self._viewport = view.viewport()
        self._application = QApplication.instance()
        self._reset_scheduled = False
        self._disposed = False

        self._viewport.installEventFilter(self)
        if self._application is not None:
            self._application.installEventFilter(self)

        view.destroyed.connect(self._dispose)

    def eventFilter(self, watched, event):
        if (
            self._disposed
            or self.view is None
            or not isValid(self.view)
        ):
            return False

        try:
            event_type = event.type()
        except RuntimeError:
            return False

        if (
            watched is self._viewport
            and event_type == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            scene_point = self.view.mapToScene(
                event.position().toPoint()
            )
            clicked_item = self.view.scene.itemAt(
                scene_point,
                self.view.transform(),
            )

            if not self._is_image_item(clicked_item):
                for selected in list(
                    self.view.scene.selectedItems()
                ):
                    if isinstance(
                        selected,
                        ImageAnnotationItem,
                    ):
                        selected.setSelected(False)

                self._schedule_reset()

        if (
            event_type == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._schedule_reset()

        if (
            event_type == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
        ):
            for selected in list(
                self.view.scene.selectedItems()
            ):
                if isinstance(
                    selected,
                    ImageAnnotationItem,
                ):
                    selected.setSelected(False)

            self._schedule_reset()

        return False

    @staticmethod
    def _is_image_item(item):
        current = item
        while current is not None:
            if isinstance(
                current,
                ImageAnnotationItem,
            ):
                return True
            current = current.parentItem()
        return False

    def _dispose(self, *args):
        if self._disposed:
            return

        self._disposed = True

        try:
            if (
                self._application is not None
                and isValid(self._application)
            ):
                self._application.removeEventFilter(self)
        except RuntimeError:
            pass

        try:
            if (
                self._viewport is not None
                and isValid(self._viewport)
            ):
                self._viewport.removeEventFilter(self)
        except RuntimeError:
            pass

        self.view = None
        self._viewport = None
        self._application = None

    def _schedule_reset(self):
        if (
            self._disposed
            or self.view is None
            or not isValid(self.view)
            or self._reset_scheduled
        ):
            return

        self._reset_scheduled = True
        QTimer.singleShot(
            0,
            self._reset_view_drag,
        )

    def _reset_view_drag(self):
        self._reset_scheduled = False

        if (
            self._disposed
            or self.view is None
            or not isValid(self.view)
        ):
            return

        try:
            grabber = self.view.scene.mouseGrabberItem()
            if grabber is not None:
                grabber.ungrabMouse()
        except RuntimeError:
            pass

        try:
            drag_mode = self.view.dragMode()
            self.view.setDragMode(
                QGraphicsView.DragMode.NoDrag
            )
            self.view.setDragMode(drag_mode)
        except RuntimeError:
            pass

        try:
            self.view.viewport().releaseMouse()
            self.view.viewport().unsetCursor()
            self.view.unsetCursor()
        except RuntimeError:
            pass


class ImageAnnotationItem(QGraphicsObject):
    HANDLE_RADIUS = 7.0
    MIN_SIZE = 20.0

    def __init__(self, record):
        super().__init__()
        self.record = record
        self.image = _image_from_base64(
            record.get("image_data", "")
        )
        if not self.image.isNull():
            self.record["source_ratio"] = (
                _cropped_aspect_ratio(
                    self.record,
                    self.image,
                )
            )
        self._resize_corner = None
        self._resize_start_rect = QRectF()
        self._resize_start_pos = QPointF()
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
                float(self.record.get("width", 240.0)),
                self.MIN_SIZE,
            ),
            max(
                float(self.record.get("height", 180.0)),
                self.MIN_SIZE,
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
            -12.0,
            -12.0,
            12.0,
            12.0,
        )

    def paint(self, painter, option, widget=None):
        rect = self._rect()
        opacity = max(
            0.0,
            min(float(self.record.get("opacity", 1.0)), 1.0),
        )

        painter.save()
        painter.setOpacity(opacity)

        if not self.image.isNull():
            source = _crop_rect_from_record(
                self.record,
                self.image,
            )
            painter.setRenderHint(
                QPainter.RenderHint.SmoothPixmapTransform,
                True,
            )
            painter.drawImage(rect, self.image, source)

        painter.restore()

        if bool(self.record.get("border_enabled", False)):
            color = QColor(
                str(self.record.get("border_color", "#000000"))
            )
            if not color.isValid():
                color = QColor("#000000")
            painter.setPen(
                QPen(
                    color,
                    max(
                        float(self.record.get("border_width", 1.0)),
                        0.5,
                    ),
                )
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

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

            painter.setPen(QPen(QColor("#1e88e5"), 1.5))
            painter.setBrush(QBrush(QColor("#ffffff")))
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
                <= (self.HANDLE_RADIUS + 4.0) ** 2
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
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif handle in {"tr", "bl"}:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        handle = (
            self._handle_at(event.pos())
            if self.isSelected()
            else None
        )
        if (
            event.button() == Qt.MouseButton.LeftButton
            and handle is not None
        ):
            self._resize_corner = handle
            self._resize_start_rect = self._rect()
            self._resize_start_pos = QPointF(self.pos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resize_corner is None:
            return super().mouseMoveEvent(event)

        if not (event.buttons() & Qt.MouseButton.LeftButton):
            self._resize_corner = None
            self._resize_start_rect = QRectF()
            self._resize_start_pos = QPointF()
            event.ignore()
            return

        point = event.pos()
        rect = QRectF(self._resize_start_rect)
        position = QPointF(self._resize_start_pos)

        if "l" in self._resize_corner:
            new_left = min(
                point.x(),
                rect.right() - self.MIN_SIZE,
            )
            position.setX(
                position.x() + new_left - rect.left()
            )
            rect.setLeft(new_left)

        if "r" in self._resize_corner:
            rect.setRight(
                max(
                    point.x(),
                    rect.left() + self.MIN_SIZE,
                )
            )

        if "t" in self._resize_corner:
            new_top = min(
                point.y(),
                rect.bottom() - self.MIN_SIZE,
            )
            position.setY(
                position.y() + new_top - rect.top()
            )
            rect.setTop(new_top)

        if "b" in self._resize_corner:
            rect.setBottom(
                max(
                    point.y(),
                    rect.top() + self.MIN_SIZE,
                )
            )

        if bool(self.record.get("keep_ratio", True)):
            ratio = max(
                float(self.record.get("source_ratio", 1.0)),
                0.001,
            )
            width = rect.width()
            height = width / ratio
            if height > rect.height():
                height = rect.height()
                width = height * ratio

            if "l" in self._resize_corner:
                rect.setLeft(rect.right() - width)
            else:
                rect.setRight(rect.left() + width)

            if "t" in self._resize_corner:
                rect.setTop(rect.bottom() - height)
            else:
                rect.setBottom(rect.top() + height)

        self.prepareGeometryChange()
        self.record["width"] = float(rect.width())
        self.record["height"] = float(rect.height())
        self.setPos(position)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._resize_corner is not None:
            self._resize_corner = None
            self._resize_start_rect = QRectF()
            self._resize_start_pos = QPointF()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if (
            change
            == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged
            and not bool(value)
        ):
            self._resize_corner = None
            self._resize_start_rect = QRectF()
            self._resize_start_pos = QPointF()
            self.unsetCursor()
        return super().itemChange(change, value)

    def _edit_crop(self):
        dialog = ImageCropDialog(
            self.image,
            self.record,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            old_width = max(
                float(
                    self.record.get(
                        "width",
                        240.0,
                    )
                ),
                self.MIN_SIZE,
            )
            old_height = max(
                float(
                    self.record.get(
                        "height",
                        180.0,
                    )
                ),
                self.MIN_SIZE,
            )

            self.record.update(
                dialog.crop_values()
            )

            crop_ratio = _cropped_aspect_ratio(
                self.record,
                self.image,
            )
            self.record["source_ratio"] = crop_ratio

            if bool(
                self.record.get(
                    "keep_ratio",
                    True,
                )
            ):
                current_area_ratio = (
                    old_width / old_height
                )
                if crop_ratio >= current_area_ratio:
                    self.record["width"] = old_width
                    self.record["height"] = max(
                        old_width / crop_ratio,
                        self.MIN_SIZE,
                    )
                else:
                    self.record["height"] = old_height
                    self.record["width"] = max(
                        old_height * crop_ratio,
                        self.MIN_SIZE,
                    )

            self.prepareGeometryChange()
            self.update()

    def _edit_properties(self):
        dialog = ImagePropertiesDialog(
            None,
            self.record,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.prepareGeometryChange()
            self.record.update(dialog.values())
            self.update()

    def mouseDoubleClickEvent(self, event):
        self._edit_crop()
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu()
        crop_action = menu.addAction("画像をトリミング...")
        property_action = menu.addAction("画像のプロパティ...")
        selected = menu.exec(event.screenPos())

        if selected is crop_action:
            self._edit_crop()
        elif selected is property_action:
            self._edit_properties()

        event.accept()

    def refresh_from_record(self):
        self.prepareGeometryChange()
        self.image = _image_from_base64(
            self.record.get("image_data", "")
        )
        if not self.image.isNull():
            self.record["source_ratio"] = (
                _cropped_aspect_ratio(
                    self.record,
                    self.image,
                )
            )
        self.update()


def _restore_image_previous_mode(view):
    mode = getattr(
        view,
        "_image_previous_annotation_mode",
        None,
    )
    if not mode:
        return

    try:
        view.set_annotation_mode(mode)
    except (AttributeError, RuntimeError):
        try:
            view.annotation_mode = mode
        except (AttributeError, RuntimeError):
            pass


class AnnotationEscapeGuard(QObject):
    """Two-stage Escape handling shared by all annotation modes."""

    def __init__(self, main_window, view):
        super().__init__(view)
        self.main_window = main_window
        self.view = view
        view.installEventFilter(self)
        view.viewport().installEventFilter(self)

    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
        ):
            selected = list(
                self.view.scene.selectedItems()
            )

            if selected:
                self.view.scene.clearSelection()

                try:
                    self.view.annotation_selected.emit(None)
                except (AttributeError, RuntimeError):
                    pass

                guard = getattr(
                    self.view,
                    "_image_interaction_guard",
                    None,
                )
                if guard is not None:
                    reset = getattr(
                        guard,
                        "_schedule_reset",
                        None,
                    )
                    if callable(reset):
                        reset()

                event.accept()
                return True

            try:
                self.view.set_annotation_mode("hand")
            except (AttributeError, RuntimeError):
                try:
                    self.view.annotation_mode = "hand"
                except (AttributeError, RuntimeError):
                    pass

            hand_action = getattr(
                self.main_window,
                "hand_action",
                None,
            )
            if hand_action is not None:
                try:
                    hand_action.setChecked(True)
                except RuntimeError:
                    pass

            action_group = getattr(
                self.main_window,
                "annotation_group",
                None,
            )
            if action_group is not None:
                try:
                    for action in action_group.actions():
                        if action is not hand_action:
                            action.setChecked(False)
                except RuntimeError:
                    pass

            event.accept()
            return True

        return False


def install_image_annotation(main_window):
    view = main_window.view
    if getattr(view, "_image_annotation_installed", False):
        return

    view._image_annotation_installed = True

    original_create_item = view._create_annotation_item

    def create_item(record):
        if record.get("type") != "image":
            return original_create_item(record)

        view._ensure_annotation_identity(record)
        origin = view._page_origins.get(
            record["page_index"]
        )
        if origin is None:
            return None

        item = ImageAnnotationItem(record)
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

    def add_image(page_index, page_point, image):
        if image.isNull():
            return None

        before = view._history_snapshot()

        max_size = 280.0
        ratio = image.width() / max(image.height(), 1)

        if ratio >= 1.0:
            width = max_size
            height = max_size / max(ratio, 0.001)
        else:
            height = max_size
            width = max_size * ratio

        record = {
            "id": str(uuid.uuid4()),
            "type": "image",
            "page_index": int(page_index),
            "x": float(page_point.x() - width / 2.0),
            "y": float(page_point.y() - height / 2.0),
            "width": width,
            "height": height,
            "source_ratio": ratio,
            "keep_ratio": True,
            "opacity": 1.0,
            "border_enabled": False,
            "border_color": "#000000",
            "border_width": 1.0,
            "crop_left": 0.0,
            "crop_top": 0.0,
            "crop_right": 1.0,
            "crop_bottom": 1.0,
            "image_data": _image_to_base64(image),
            "z": view._next_annotation_z(),
        }

        crop_dialog = ImageCropDialog(
            image,
            record,
            main_window,
        )
        if crop_dialog.exec() != QDialog.DialogCode.Accepted:
            _restore_image_previous_mode(view)
            return None

        record.update(
            crop_dialog.crop_values()
        )

        crop_ratio = _cropped_aspect_ratio(
            record,
            image,
        )
        record["source_ratio"] = crop_ratio

        if crop_ratio >= 1.0:
            width = max_size
            height = max_size / crop_ratio
        else:
            height = max_size
            width = max_size * crop_ratio

        record["width"] = width
        record["height"] = height
        record["x"] = float(
            page_point.x() - width / 2.0
        )
        record["y"] = float(
            page_point.y() - height / 2.0
        )

        view._annotation_records.append(record)

        item = view._create_annotation_item(record)
        if item is not None:
            # Leave a newly inserted image unselected. Selecting a movable
            # QGraphicsItem during the dialog-closing mouse event can make Qt
            # continue that event as an item drag.
            view.scene.clearSelection()
            view.annotation_selected.emit(None)

        view._commit_history_change(before)
        return item

    def choose_and_place_image():
        view._image_previous_annotation_mode = getattr(
            view,
            "annotation_mode",
            "hand",
        )
        path, _ = QFileDialog.getOpenFileName(
            main_window,
            "画像を選択",
            "",
            SUPPORTED_IMAGE_FILTER,
        )
        if not path:
            _restore_image_previous_mode(view)
            return

        image = QImage(path)
        if image.isNull():
            _restore_image_previous_mode(view)
            return

        page_index = int(
            getattr(
                main_window,
                "current_page",
                0,
            )
        )

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
            pdf_document is None
            or not (
                0
                <= page_index
                < len(pdf_document)
            )
        ):
            _restore_image_previous_mode(view)
            return

        page_rect = pdf_document[
            page_index
        ].rect

        page_point = QPointF(
            float(page_rect.width) / 2.0,
            float(page_rect.height) / 2.0,
        )
        add_image(
            page_index,
            page_point,
            image,
        )
        _restore_image_previous_mode(view)

    view._create_annotation_item = create_item
    view.add_image_overlay = add_image

    image_action = QAction(
        "🖼 画像を貼り付け...",
        main_window,
    )
    image_action.setToolTip(
        "画像を選択し、トリミングしてPDFへ配置"
    )
    image_action.triggered.connect(
        choose_and_place_image
    )

    shape_menu = main_window.shape_tool_button.menu()
    shape_menu.addSeparator()
    shape_menu.addAction(image_action)

    main_window.image_annotation_action = image_action


def draw_image_annotation(page, record):
    image = _image_from_base64(
        record.get("image_data", "")
    )
    if image.isNull():
        return False

    crop = _crop_rect_from_record(record, image)
    crop_int = crop.toAlignedRect()
    cropped = image.copy(crop_int)

    buffer = QByteArray()
    from PySide6.QtCore import QBuffer, QIODevice

    device = QBuffer(buffer)
    device.open(QIODevice.OpenModeFlag.WriteOnly)
    cropped.save(device, "PNG")
    device.close()

    x = float(record.get("x", 0.0))
    y = float(record.get("y", 0.0))
    rect = fitz.Rect(
        x,
        y,
        x + float(record.get("width", 240.0)),
        y + float(record.get("height", 180.0)),
    )

    page.insert_image(
        rect,
        stream=bytes(buffer),
        keep_proportion=False,
        overlay=True,
    )

    if bool(record.get("border_enabled", False)):
        color = QColor(
            str(record.get("border_color", "#000000"))
        )
        if not color.isValid():
            color = QColor("#000000")

        fitz_color = (
            color.redF(),
            color.greenF(),
            color.blueF(),
        )
        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(
            color=fitz_color,
            width=max(
                float(record.get("border_width", 1.0)),
                0.5,
            ),
        )
        shape.commit()

    return True
