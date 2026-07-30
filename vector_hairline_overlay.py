from __future__ import annotations

import re

import fitz
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen


class VectorHairlineOverlay:
    """Redraw thin vector strokes that can disappear after rasterization."""

    MIN_DEVICE_WIDTH = 1.0
    MAX_SOURCE_WIDTH = 1.5

    def apply(
        self,
        image: QImage,
        drawings,
        clip_rect,
        render_scale: float,
    ) -> QImage:
        if image.isNull() or not drawings or render_scale <= 0:
            return image

        painter = QPainter(image)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setClipRect(QRectF(0.0, 0.0, image.width(), image.height()))

            for drawing in drawings:
                self._paint_drawing(
                    painter,
                    drawing,
                    clip_rect,
                    render_scale,
                )
        finally:
            painter.end()

        return image

    def _paint_drawing(
        self,
        painter: QPainter,
        drawing: dict,
        clip_rect,
        render_scale: float,
    ) -> None:
        stroke = drawing.get("color")
        if stroke is None:
            return

        source_width = float(drawing.get("width") or 0.0)
        device_width = source_width * render_scale

        # Only reinforce genuinely thin strokes. Thicker geometry is already
        # represented reliably by the normal PDF rasterizer.
        if source_width > self.MAX_SOURCE_WIDTH:
            return
        if device_width >= self.MIN_DEVICE_WIDTH:
            return

        drawing_rect = drawing.get("rect")
        if drawing_rect is not None:
            try:
                if not fitz.Rect(drawing_rect).intersects(clip_rect):
                    return
            except Exception:
                pass

        pen = QPen(self._to_qcolor(stroke))
        pen.setCosmetic(True)
        pen.setWidthF(self.MIN_DEVICE_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)

        dash_pattern = self._parse_dash_pattern(drawing.get("dashes"))
        if dash_pattern:
            pen.setDashPattern(dash_pattern)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for item in drawing.get("items", ()):
            if not item:
                continue

            command = item[0]
            if command == "l" and len(item) >= 3:
                painter.drawLine(
                    self._map_point(item[1], clip_rect, render_scale),
                    self._map_point(item[2], clip_rect, render_scale),
                )
            elif command == "re" and len(item) >= 2:
                painter.drawRect(
                    self._map_rect(item[1], clip_rect, render_scale)
                )
            elif command == "qu" and len(item) >= 2:
                quad = item[1]
                points = [
                    self._map_point(point, clip_rect, render_scale)
                    for point in (
                        quad.ul,
                        quad.ur,
                        quad.lr,
                        quad.ll,
                    )
                ]
                for start, end in zip(points, points[1:] + points[:1]):
                    painter.drawLine(start, end)

    @staticmethod
    def _to_qcolor(value) -> QColor:
        try:
            red, green, blue = value[:3]
            return QColor.fromRgbF(
                max(0.0, min(float(red), 1.0)),
                max(0.0, min(float(green), 1.0)),
                max(0.0, min(float(blue), 1.0)),
            )
        except Exception:
            return QColor(Qt.GlobalColor.black)

    @staticmethod
    def _map_point(point, clip_rect, scale: float) -> QPointF:
        return QPointF(
            (float(point.x) - float(clip_rect.x0)) * scale,
            (float(point.y) - float(clip_rect.y0)) * scale,
        )

    @classmethod
    def _map_rect(cls, rect, clip_rect, scale: float) -> QRectF:
        source = fitz.Rect(rect)
        left_top = cls._map_point(source.tl, clip_rect, scale)
        right_bottom = cls._map_point(source.br, clip_rect, scale)
        return QRectF(left_top, right_bottom).normalized()

    @staticmethod
    def _parse_dash_pattern(value) -> list[float]:
        if not value or str(value).strip() in {"[] 0", "[]0", "[]"}:
            return []

        numbers = re.findall(r"-?\d+(?:\.\d+)?", str(value))
        if len(numbers) <= 1:
            return []

        # The final number is normally the dash phase, not a dash length.
        pattern = [max(float(number), 0.1) for number in numbers[:-1]]
        return pattern if len(pattern) >= 2 else []
