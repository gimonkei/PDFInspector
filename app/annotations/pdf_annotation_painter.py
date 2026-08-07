from __future__ import annotations

import math

import fitz
from app.annotations.render_contract import image_to_png_bytes, qrectf_to_fitz_rect
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)


DEFAULT_SCALE = 4.0
DEFAULT_MARGIN = 10.0


def _color(value, fallback):
    color = QColor(str(value or fallback))
    if not color.isValid():
        color = QColor(fallback)
    return color


def _callout_outlet(record):
    x = float(record.get("x", 0.0))
    y = float(record.get("y", 0.0))
    width = max(float(record.get("width", 180.0)), 1.0)
    height = max(float(record.get("height", 74.0)), 1.0)

    edge = str(record.get("outlet_edge", "bottom"))
    t = max(0.0, min(float(record.get("outlet_t", 0.5)), 1.0))

    if edge == "top":
        return QPointF(x + width * t, y)
    if edge == "left":
        return QPointF(x, y + height * t)
    if edge == "right":
        return QPointF(x + width, y + height * t)
    return QPointF(x + width * t, y + height)


def _balloon_outlet(record):
    x = float(record.get("x", 0.0))
    y = float(record.get("y", 0.0))
    width = max(float(record.get("width", 52.0)), 1.0)
    height = max(float(record.get("height", 52.0)), 1.0)
    angle = math.radians(float(record.get("outlet_angle", 90.0)))

    return QPointF(
        x + width / 2.0 + math.cos(angle) * width / 2.0,
        y + height / 2.0 + math.sin(angle) * height / 2.0,
    )


def _annotation_bounds(record):
    kind = str(record.get("type", ""))
    x = float(record.get("x", 0.0))
    y = float(record.get("y", 0.0))
    width = max(float(record.get("width", 1.0)), 1.0)
    height = max(float(record.get("height", 1.0)), 1.0)

    left = x
    top = y
    right = x + width
    bottom = y + height

    if kind == "callout":
        tip_x = x + float(record.get("leader_dx", -42.0))
        tip_y = y + float(record.get("leader_dy", 92.0))
        left = min(left, tip_x)
        top = min(top, tip_y)
        right = max(right, tip_x)
        bottom = max(bottom, tip_y)

    if kind == "balloon" and bool(record.get("arrow_enabled", True)):
        tip_x = x + float(record.get("leader_dx", -45.0))
        tip_y = y + float(record.get("leader_dy", 85.0))
        left = min(left, tip_x)
        top = min(top, tip_y)
        right = max(right, tip_x)
        bottom = max(bottom, tip_y)

    if kind == "date_stamp":
        size = max(float(record.get("size", 72.0)), 42.0)
        left = x - size / 2.0
        top = y - size / 2.0
        right = x + size / 2.0
        bottom = y + size / 2.0

    margin = max(
        DEFAULT_MARGIN,
        float(record.get("line_width", 2.0)) * 4.0,
    )
    return QRectF(
        left - margin,
        top - margin,
        right - left + margin * 2.0,
        bottom - top + margin * 2.0,
    )


def _arrow_polygon(outlet, tip, scale, size=10.0):
    vector = tip - outlet
    length = max(math.hypot(vector.x(), vector.y()), 0.001)
    ux = vector.x() / length
    uy = vector.y() / length
    px = -uy
    py = ux

    head = size * scale
    half = size * 0.5 * scale
    return QPolygonF(
        [
            tip,
            QPointF(
                tip.x() - ux * head + px * half,
                tip.y() - uy * head + py * half,
            ),
            QPointF(
                tip.x() - ux * head - px * half,
                tip.y() - uy * head - py * half,
            ),
        ]
    )


def _font(
    record,
    scale,
    default_size,
    *,
    pixel_size=None,
):
    font = QFont(
        str(
            record.get(
                "font_family",
                "Meiryo",
            )
        )
    )

    if pixel_size is None:
        # PDF annotation dimensions are stored in PDF points.
        # Rendering uses `scale` pixels per PDF point, so using pixel size
        # avoids the image device DPI making saved text about 33% larger.
        pixel_size = (
            max(
                float(
                    record.get(
                        "font_size",
                        default_size,
                    )
                ),
                6.0,
            )
            * scale
        )

    font.setPixelSize(
        max(
            int(round(pixel_size)),
            1,
        )
    )
    font.setBold(
        bool(
            record.get(
                "bold",
                False,
            )
        )
    )
    font.setItalic(
        bool(
            record.get(
                "italic",
                False,
            )
        )
    )
    font.setUnderline(
        bool(
            record.get(
                "underline",
                False,
            )
        )
    )
    return font


def _text_flags():
    return (
        Qt.AlignmentFlag.AlignCenter
        | Qt.TextFlag.TextWordWrap
    )


def _fitted_font(
    rect,
    value,
    record,
    scale,
    default_size,
):
    requested_pixels = (
        max(
            float(
                record.get(
                    "font_size",
                    default_size,
                )
            ),
            6.0,
        )
        * scale
    )
    minimum_pixels = min(
        requested_pixels,
        5.0 * scale,
    )

    font = _font(
        record,
        scale,
        default_size,
        pixel_size=requested_pixels,
    )
    text = str(value or "")
    flags = _text_flags()

    # Reduce only when the text would be clipped. This preserves the
    # requested size for short comments while keeping long comments inside.
    pixel_size = requested_pixels
    while pixel_size > minimum_pixels:
        metrics = QFontMetricsF(font)
        measured = metrics.boundingRect(
            rect,
            int(flags),
            text,
        )
        if (
            measured.width()
            <= rect.width() + 0.5
            and measured.height()
            <= rect.height() + 0.5
        ):
            break

        pixel_size = max(
            minimum_pixels,
            pixel_size - max(1.0, scale * 0.5),
        )
        font = _font(
            record,
            scale,
            default_size,
            pixel_size=pixel_size,
        )

    return font


def _draw_text(
    painter,
    rect,
    text,
    record,
    scale,
    default_size,
    color,
):
    painter.save()
    painter.setPen(color)
    painter.setFont(
        _fitted_font(
            rect,
            text,
            record,
            scale,
            default_size,
        )
    )
    painter.drawText(
        rect,
        _text_flags(),
        str(text or ""),
    )
    painter.restore()


def _render_stamp(painter, record, origin, scale):
    x = (float(record.get("x", 0.0)) - origin.x()) * scale
    y = (float(record.get("y", 0.0)) - origin.y()) * scale
    width = float(record.get("width", 92.0)) * scale
    height = float(record.get("height", 34.0)) * scale
    rect = QRectF(x, y, width, height)

    color = _color(record.get("color"), "#d00000")
    line_width = max(float(record.get("line_width", 2.5)), 0.5) * scale

    painter.setPen(QPen(color, line_width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(rect)

    _draw_text(
        painter,
        rect.adjusted(3.0 * scale, 1.0 * scale, -3.0 * scale, -1.0 * scale),
        record.get("text", ""),
        record,
        scale,
        14.0,
        color,
    )


def _render_callout(painter, record, origin, scale):
    x_pdf = float(record.get("x", 0.0))
    y_pdf = float(record.get("y", 0.0))
    width_pdf = float(record.get("width", 180.0))
    height_pdf = float(record.get("height", 74.0))

    rect = QRectF(
        (x_pdf - origin.x()) * scale,
        (y_pdf - origin.y()) * scale,
        width_pdf * scale,
        height_pdf * scale,
    )

    border = _color(record.get("color"), "#d00000")
    fill = _color(record.get("fill_color"), "#fff8c6")
    fill.setAlphaF(
        max(0.0, min(float(record.get("fill_opacity", 0.72)), 1.0))
    )
    text_color = _color(record.get("text_color"), "#000000")
    arrow_color = _color(
        record.get("arrow_color", record.get("color", "#d00000")),
        "#d00000",
    )
    line_width = max(float(record.get("line_width", 2.0)), 0.5) * scale

    painter.setPen(QPen(border, line_width))
    painter.setBrush(QBrush(fill))
    corner_radius = max(
        float(
            record.get(
                "corner_radius",
                10.0,
            )
        ),
        0.0,
    ) * scale
    painter.drawRoundedRect(
        rect,
        corner_radius,
        corner_radius,
    )

    outlet_pdf = _callout_outlet(record)
    tip_pdf = QPointF(
        x_pdf + float(record.get("leader_dx", -42.0)),
        y_pdf + float(record.get("leader_dy", 92.0)),
    )
    outlet = QPointF(
        (outlet_pdf.x() - origin.x()) * scale,
        (outlet_pdf.y() - origin.y()) * scale,
    )
    tip = QPointF(
        (tip_pdf.x() - origin.x()) * scale,
        (tip_pdf.y() - origin.y()) * scale,
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
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawLine(outlet, tip)
    painter.setBrush(QBrush(arrow_color))
    painter.drawPolygon(_arrow_polygon(outlet, tip, scale))

    _draw_text(
        painter,
        rect.adjusted(
            6.0 * scale,
            5.0 * scale,
            -6.0 * scale,
            -5.0 * scale,
        ),
        record.get("text", ""),
        record,
        scale,
        11.0,
        text_color,
    )


def _render_balloon(painter, record, origin, scale):
    x_pdf = float(record.get("x", 0.0))
    y_pdf = float(record.get("y", 0.0))
    width_pdf = float(record.get("width", 52.0))
    height_pdf = float(record.get("height", 52.0))

    rect = QRectF(
        (x_pdf - origin.x()) * scale,
        (y_pdf - origin.y()) * scale,
        width_pdf * scale,
        height_pdf * scale,
    )

    border = _color(record.get("color"), "#d00000")
    fill = _color(record.get("fill_color"), "#ffffff")
    fill.setAlphaF(
        max(0.0, min(float(record.get("fill_opacity", 1.0)), 1.0))
    )
    text_color = _color(record.get("text_color"), "#d00000")
    arrow_color = _color(
        record.get("arrow_color", record.get("color", "#d00000")),
        "#d00000",
    )
    line_width = max(float(record.get("line_width", 2.0)), 0.5) * scale

    painter.setPen(QPen(border, line_width))
    painter.setBrush(QBrush(fill))
    painter.drawEllipse(rect)

    if bool(record.get("arrow_enabled", True)):
        outlet_pdf = _balloon_outlet(record)
        tip_pdf = QPointF(
            x_pdf + float(record.get("leader_dx", -45.0)),
            y_pdf + float(record.get("leader_dy", 85.0)),
        )
        outlet = QPointF(
            (outlet_pdf.x() - origin.x()) * scale,
            (outlet_pdf.y() - origin.y()) * scale,
        )
        tip = QPointF(
            (tip_pdf.x() - origin.x()) * scale,
            (tip_pdf.y() - origin.y()) * scale,
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
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(outlet, tip)
        painter.setBrush(QBrush(arrow_color))
        painter.drawPolygon(_arrow_polygon(outlet, tip, scale))

    balloon_record = dict(record)
    balloon_record["bold"] = True
    _draw_text(
        painter,
        rect.adjusted(
            3.0 * scale,
            2.0 * scale,
            -3.0 * scale,
            -2.0 * scale,
        ),
        record.get("text", "1"),
        balloon_record,
        scale,
        16.0,
        text_color,
    )



def _render_date_stamp(painter, record, origin, scale):
    x = (float(record.get("x", 0.0)) - origin.x()) * scale
    y = (float(record.get("y", 0.0)) - origin.y()) * scale
    size = max(float(record.get("size", 72.0)), 42.0) * scale
    rect = QRectF(
        x - size / 2.0,
        y - size / 2.0,
        size,
        size,
    )

    color = _color(record.get("color"), "#000000")
    line_width = max(float(record.get("line_width", 1.5)), 0.5) * scale

    painter.setPen(QPen(color, line_width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(rect)

    upper_y = y - size * 0.13
    lower_y = y + size * 0.13
    painter.drawLine(QPointF(rect.left(), upper_y), QPointF(rect.right(), upper_y))
    painter.drawLine(QPointF(rect.left(), lower_y), QPointF(rect.right(), lower_y))

    stamp_record = dict(record)
    stamp_record["font_family"] = str(record.get("font_family", "Meiryo"))
    stamp_record["font_size"] = max(float(record.get("font_size", size / scale * 0.09)), 5.0)

    rows = (
        (
            record.get("top", ""),
            QRectF(rect.left(), rect.top() + size * 0.05, rect.width(), upper_y - rect.top() - size * 0.05),
        ),
        (
            record.get("date", ""),
            QRectF(rect.left(), upper_y, rect.width(), lower_y - upper_y),
        ),
        (
            record.get("bottom", ""),
            QRectF(rect.left(), lower_y, rect.width(), rect.bottom() - lower_y - size * 0.04),
        ),
    )
    for value, text_rect in rows:
        _draw_text(
            painter,
            text_rect,
            value,
            stamp_record,
            scale,
            stamp_record["font_size"],
            color,
        )


def _cloud_path(rect, radius):
    path = QPainterPath()
    radius = max(
        3.0,
        min(
            float(radius),
            min(rect.width(), rect.height()) / 3.0,
        ),
    )

    def edge_points(start, end):
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = max(math.hypot(dx, dy), 0.001)
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

    center = rect.center()
    path.moveTo(points[0])
    for index, current in enumerate(points):
        following = points[(index + 1) % len(points)]
        midpoint = QPointF(
            (current.x() + following.x()) * 0.5,
            (current.y() + following.y()) * 0.5,
        )
        vx = midpoint.x() - center.x()
        vy = midpoint.y() - center.y()
        distance = max(math.hypot(vx, vy), 0.001)
        control = QPointF(
            midpoint.x() + vx / distance * radius * 0.62,
            midpoint.y() + vy / distance * radius * 0.62,
        )
        path.quadTo(control, following)

    path.closeSubpath()
    return path


def _render_cloud(painter, record, origin, scale):
    x = (float(record.get("x", 0.0)) - origin.x()) * scale
    y = (float(record.get("y", 0.0)) - origin.y()) * scale
    width = max(float(record.get("width", 80.0)), 1.0) * scale
    height = max(float(record.get("height", 50.0)), 1.0) * scale
    rect = QRectF(x, y, width, height)

    color = _color(record.get("color"), "#dc0000")
    line_width = max(float(record.get("line_width", 2.0)), 0.5) * scale
    painter.setPen(QPen(color, line_width))
    if bool(record.get("fill_enabled", False)):
        fill = _color(record.get("fill_color"), "#ffff00")
        fill.setAlphaF(max(0.0, min(float(record.get("fill_opacity", 0.25)), 1.0)))
        painter.setBrush(QBrush(fill))
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)

    painter.drawPath(
        _cloud_path(
            rect,
            float(record.get("cloud_radius", 8.0)) * scale,
        )
    )

    text = str(record.get("text", ""))
    if text:
        _draw_text(
            painter,
            rect.adjusted(6.0 * scale, 6.0 * scale, -6.0 * scale, -6.0 * scale),
            text,
            record,
            scale,
            11.0,
            _color(record.get("text_color"), "#000000"),
        )

def render_annotation_image(record, scale=DEFAULT_SCALE):
    bounds = _annotation_bounds(record)
    width = max(int(math.ceil(bounds.width() * scale)), 1)
    height = max(int(math.ceil(bounds.height() * scale)), 1)

    image = QImage(
        width,
        height,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    origin = bounds.topLeft()
    kind = str(record.get("type", ""))
    if kind == "stamp":
        _render_stamp(painter, record, origin, scale)
    elif kind == "callout":
        _render_callout(painter, record, origin, scale)
    elif kind == "balloon":
        _render_balloon(painter, record, origin, scale)
    elif kind == "date_stamp":
        _render_date_stamp(painter, record, origin, scale)
    elif kind == "cloud":
        _render_cloud(painter, record, origin, scale)
    else:
        painter.end()
        return None, None

    painter.end()
    return image, bounds


def draw_raster_annotation(page, record, scale=DEFAULT_SCALE):
    image, bounds = render_annotation_image(record, scale=scale)
    if image is None or bounds is None or image.isNull():
        return False
    page.insert_image(qrectf_to_fitz_rect(bounds), stream=image_to_png_bytes(image), keep_proportion=False, overlay=True)
    return True
