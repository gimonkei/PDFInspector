from __future__ import annotations

import math

import fitz
from PySide6.QtCore import QPointF, QRectF, Qt
from app.annotations.pdf_annotation_painter import (
    render_annotation_image,
)

from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)


class PrintRenderer:
    def __init__(self, document, annotations):
        self.document = document
        self.annotations = annotations

    def adaptive_dpi(
        self,
        page_index: int,
        requested_dpi: int,
    ) -> int:
        page = self.document.doc[int(page_index)]
        width_mm = float(page.rect.width) * 25.4 / 72.0
        height_mm = float(page.rect.height) * 25.4 / 72.0
        long_side = max(width_mm, height_mm)

        if long_side <= 300:
            limit = 1200
        elif long_side <= 430:
            limit = 600
        elif long_side <= 610:
            limit = 450
        elif long_side <= 860:
            limit = 300
        else:
            limit = 220

        return max(150, min(int(requested_dpi), limit))

    def render_page(
        self,
        page_index: int,
        requested_dpi: int,
        print_annotations: bool,
    ) -> tuple[QImage, int]:
        dpi = self.adaptive_dpi(page_index, requested_dpi)
        page = self.document.doc[int(page_index)]
        zoom = float(dpi) / 72.0

        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(zoom, zoom),
            alpha=False,
            annots=True,
        )

        image_format = (
            QImage.Format.Format_RGB888
            if pixmap.n == 3
            else QImage.Format.Format_RGBA8888
        )
        image = QImage(
            pixmap.samples,
            pixmap.width,
            pixmap.height,
            pixmap.stride,
            image_format,
        ).copy()

        if print_annotations:
            self._paint_annotations(
                image,
                int(page_index),
                zoom,
            )

        return image, dpi

    def _paint_annotations(
        self,
        image: QImage,
        page_index: int,
        scale: float,
    ) -> None:
        painter = QPainter(image)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )
        painter.setRenderHint(
            QPainter.RenderHint.TextAntialiasing,
            True,
        )

        try:
            for record in self.annotations:
                if int(record.get("page_index", -1)) != page_index:
                    continue
                self._paint_record(painter, record, scale)
        finally:
            painter.end()

    @staticmethod
    def _cloud_path(rect, radius):
        path = QPainterPath()
        radius = max(
            4.0,
            min(
                float(radius),
                min(
                    rect.width(),
                    rect.height(),
                )
                / 4.0,
            ),
        )

        def edge_points(start, end):
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            length = max(
                (
                    dx * dx
                    + dy * dy
                )
                ** 0.5,
                0.001,
            )
            count = max(
                1,
                int(
                    round(
                        length
                        / (
                            radius
                            * 1.55
                        )
                    )
                ),
            )
            return [
                QPointF(
                    start.x()
                    + dx * index / count,
                    start.y()
                    + dy * index / count,
                )
                for index in range(
                    count + 1
                )
            ]

        points = (
            edge_points(
                rect.topLeft(),
                rect.topRight(),
            )
            + edge_points(
                rect.topRight(),
                rect.bottomRight(),
            )[1:]
            + edge_points(
                rect.bottomRight(),
                rect.bottomLeft(),
            )[1:]
            + edge_points(
                rect.bottomLeft(),
                rect.topLeft(),
            )[1:]
        )

        if not points:
            return path

        path.moveTo(points[0])
        center = rect.center()

        for index, current in enumerate(points):
            following = points[
                (index + 1)
                % len(points)
            ]
            midpoint = QPointF(
                (
                    current.x()
                    + following.x()
                )
                * 0.5,
                (
                    current.y()
                    + following.y()
                )
                * 0.5,
            )
            vx = (
                midpoint.x()
                - center.x()
            )
            vy = (
                midpoint.y()
                - center.y()
            )
            distance = max(
                (
                    vx * vx
                    + vy * vy
                )
                ** 0.5,
                0.001,
            )
            control = QPointF(
                midpoint.x()
                + vx
                / distance
                * radius
                * 0.62,
                midpoint.y()
                + vy
                / distance
                * radius
                * 0.62,
            )
            path.quadTo(
                control,
                following,
            )

        path.closeSubpath()
        return path

    def _paint_record(self, painter, record, scale):
        record_type = str(record.get("type", ""))
        x = float(record.get("x", 0.0)) * scale
        y = float(record.get("y", 0.0)) * scale
        color = QColor(str(record.get("color", "#dc0000")))
        if not color.isValid():
            color = QColor("#dc0000")

        color.setAlphaF(
            max(
                0.0,
                min(float(record.get("opacity", 1.0)), 1.0),
            )
        )
        line_width = max(
            float(record.get("line_width", 2.0)) * scale,
            1.0,
        )

        painter.setPen(
            QPen(
                color,
                line_width,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if record_type in {
            "stamp",
            "callout",
            "balloon",
        }:
            rendered, bounds = (
                render_annotation_image(
                    record,
                    scale=max(
                        float(scale),
                        1.0,
                    ),
                )
            )
            if (
                rendered is not None
                and bounds is not None
                and not rendered.isNull()
            ):
                target = QRectF(
                    float(bounds.x0) * scale,
                    float(bounds.y0) * scale,
                    float(bounds.width) * scale,
                    float(bounds.height) * scale,
                )
                painter.drawImage(
                    target,
                    rendered,
                )
            return

        if record_type == "check":
            size = float(
                record.get(
                    "size",
                    15.0,
                )
            ) * scale
            start = QPointF(
                x - size * 0.42,
                y,
            )
            middle = QPointF(
                x - size * 0.10,
                y + size * 0.36,
            )
            end = QPointF(
                x + size * 0.48,
                y - size * 0.42,
            )
            painter.drawLine(
                start,
                middle,
            )
            painter.drawLine(
                middle,
                end,
            )
            return

        if record_type == "text":
            font = QFont(
                str(
                    record.get(
                        "font_family",
                        "Meiryo",
                    )
                )
            )
            font.setPixelSize(
                max(
                    int(
                        round(
                            float(
                                record.get(
                                    "font_size",
                                    11.0,
                                )
                            )
                            * scale
                        )
                    ),
                    6,
                )
            )
            painter.setFont(font)
            text_color = QColor(
                str(record.get("text_color", "#000000"))
            )
            painter.setPen(text_color)
            painter.drawText(
                QPointF(x, y),
                str(record.get("text", "")),
            )
            return

        if record_type == "date_stamp":
            size = float(record.get("size", 72.0)) * scale
            rect = QRectF(
                x - size / 2,
                y - size / 2,
                size,
                size,
            )
            painter.drawEllipse(rect)
            painter.drawLine(
                QPointF(rect.left(), y - size * 0.13),
                QPointF(rect.right(), y - size * 0.13),
            )
            painter.drawLine(
                QPointF(rect.left(), y + size * 0.13),
                QPointF(rect.right(), y + size * 0.13),
            )
            font = QFont("Meiryo")
            font.setPixelSize(
                max(
                    int(round(size * 0.09)),
                    6,
                )
            )
            painter.setFont(font)
            for text, offset in (
                (record.get("top", ""), -size * 0.24),
                (record.get("date", ""), size * 0.02),
                (record.get("bottom", ""), size * 0.27),
            ):
                painter.drawText(
                    QRectF(
                        rect.left(),
                        y + offset - size * 0.08,
                        rect.width(),
                        size * 0.16,
                    ),
                    Qt.AlignmentFlag.AlignCenter,
                    str(text),
                )
            return

        if record_type in {"freehand", "highlighter"}:
            polygon = QPolygonF()
            for point in record.get("points", []):
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    polygon.append(
                        QPointF(
                            x + float(point[0]) * scale,
                            y + float(point[1]) * scale,
                        )
                    )
            if polygon.size() >= 2:
                painter.drawPolyline(polygon)
            return

        if record_type == "arrow":
            end_x = x + float(record.get("dx", 80.0)) * scale
            end_y = y + float(record.get("dy", 0.0)) * scale
            painter.drawLine(
                QPointF(x, y),
                QPointF(end_x, end_y),
            )
            angle = math.atan2(end_y - y, end_x - x)
            head = max(8.0 * scale, line_width * 3.0)
            for delta in (2.55, -2.55):
                painter.drawLine(
                    QPointF(end_x, end_y),
                    QPointF(
                        end_x + head * math.cos(angle + delta),
                        end_y + head * math.sin(angle + delta),
                    ),
                )
            return

        width = float(record.get("width", 80.0)) * scale
        height = float(record.get("height", 50.0)) * scale
        rect = QRectF(x, y, width, height)

        if bool(record.get("fill_enabled", False)):
            fill = QColor(
                str(record.get("fill_color", "#ffff00"))
            )
            fill.setAlphaF(
                max(
                    0.0,
                    min(
                        float(record.get("fill_opacity", 0.25)),
                        1.0,
                    ),
                )
            )
            painter.setBrush(QBrush(fill))

        if record_type == "ellipse":
            painter.drawEllipse(rect)
        elif record_type == "cloud":
            painter.drawPath(
                self._cloud_path(
                    rect,
                    float(
                        record.get(
                            "cloud_radius",
                            8.0,
                        )
                    )
                    * scale,
                )
            )
        elif record_type == "rectangle":
            painter.drawRect(rect)

        text = str(record.get("text", ""))
        if text:
            font = QFont(
                str(
                    record.get(
                        "font_family",
                        "Meiryo",
                    )
                )
            )
            font.setPixelSize(
                max(
                    int(
                        round(
                            float(
                                record.get(
                                    "font_size",
                                    11.0,
                                )
                            )
                            * scale
                        )
                    ),
                    6,
                )
            )
            painter.setFont(font)
            painter.setPen(
                QColor(
                    str(record.get("text_color", "#000000"))
                )
            )
            painter.drawText(
                rect.adjusted(4, 4, -4, -4),
                Qt.AlignmentFlag.AlignCenter
                | Qt.TextFlag.TextWordWrap,
                text,
            )
