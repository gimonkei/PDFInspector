from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
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

from app.annotations.date_stamp import draw_date_stamp
from app.annotations.pdf_annotation_painter import (
    render_annotation_image as render_special_annotation,
)


DEFAULT_SCALE = 4.0
DEFAULT_MARGIN = 12.0


def _color(value, fallback="#dc0000"):
    color = QColor(str(value or fallback))
    if not color.isValid():
        color = QColor(fallback)
    return color


def _points(record):
    result = []
    for raw in record.get("points", []):
        if (
            isinstance(raw, (list, tuple))
            and len(raw) >= 2
        ):
            result.append(
                QPointF(
                    float(raw[0]),
                    float(raw[1]),
                )
            )
    return result


def _absolute_points(record):
    origin_x = float(record.get("x", 0.0))
    origin_y = float(record.get("y", 0.0))
    return [
        QPointF(
            origin_x + point.x(),
            origin_y + point.y(),
        )
        for point in _points(record)
    ]


def _freehand_path(points, origin, scale):
    path = QPainterPath()
    converted = [
        QPointF(
            (point.x() - origin.x()) * scale,
            (point.y() - origin.y()) * scale,
        )
        for point in points
    ]

    if not converted:
        return path

    path.moveTo(converted[0])

    if len(converted) == 2:
        path.lineTo(converted[1])
    elif len(converted) > 2:
        for index in range(
            1,
            len(converted) - 1,
        ):
            current = converted[index]
            following = converted[index + 1]
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
            path.quadTo(
                current,
                midpoint,
            )
        path.lineTo(converted[-1])

    return path


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
            math.hypot(dx, dy),
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
                + dx
                * index
                / count,
                start.y()
                + dy
                * index
                / count,
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
            math.hypot(vx, vy),
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


def _arrow_bounds(record):
    x = float(record.get("x", 0.0))
    y = float(record.get("y", 0.0))
    dx = float(record.get("dx", 80.0))
    dy = float(record.get("dy", 0.0))
    width = max(
        float(
            record.get(
                "line_width",
                2.0,
            )
        ),
        0.5,
    )
    margin = max(
        DEFAULT_MARGIN,
        width * 6.0,
    )
    return QRectF(
        min(x, x + dx) - margin,
        min(y, y + dy) - margin,
        abs(dx) + margin * 2.0,
        abs(dy) + margin * 2.0,
    )


def _record_bounds(record):
    kind = str(record.get("type", ""))

    if kind in {
        "stamp",
        "callout",
        "balloon",
    }:
        image, bounds = render_special_annotation(
            record,
            scale=DEFAULT_SCALE,
        )
        return image, bounds

    if kind == "arrow":
        return None, _arrow_bounds(record)

    if kind == "check":
        x = float(record.get("x", 0.0))
        y = float(record.get("y", 0.0))
        size = max(
            float(
                record.get(
                    "size",
                    15.0,
                )
            ),
            6.0,
        )
        margin = max(
            DEFAULT_MARGIN,
            float(
                record.get(
                    "line_width",
                    2.2,
                )
            )
            * 5.0,
        )
        return None, QRectF(
            x - size * 0.55 - margin,
            y - size * 0.55 - margin,
            size * 1.2 + margin * 2.0,
            size * 1.1 + margin * 2.0,
        )

    if kind == "date_stamp":
        x = float(record.get("x", 0.0))
        y = float(record.get("y", 0.0))
        size = max(
            float(
                record.get(
                    "size",
                    72.0,
                )
            ),
            24.0,
        )
        margin = DEFAULT_MARGIN
        return None, QRectF(
            x - size / 2.0 - margin,
            y - size / 2.0 - margin,
            size + margin * 2.0,
            size + margin * 2.0,
        )

    if kind in {
        "freehand",
        "highlighter",
    }:
        points = _absolute_points(record)
        if not points:
            return None, None
        xs = [
            point.x()
            for point in points
        ]
        ys = [
            point.y()
            for point in points
        ]
        width = max(
            float(
                record.get(
                    "line_width",
                    2.0,
                )
            ),
            0.5,
        )
        margin = max(
            DEFAULT_MARGIN,
            width * 6.0,
            16.0,
        )
        return None, QRectF(
            min(xs) - margin,
            min(ys) - margin,
            max(xs) - min(xs) + margin * 2.0,
            max(ys) - min(ys) + margin * 2.0,
        )

    if kind == "text":
        x = float(record.get("x", 0.0))
        y = float(record.get("y", 0.0))
        value = str(record.get("text", ""))
        font_size = max(
            float(record.get("font_size", 11.0)),
            4.0,
        )
        lines = value.splitlines() or [""]
        # Conservative PDF-point bounds. Actual text is measured again during draw.
        estimated_width = max(
            max((len(line) for line in lines), default=1)
            * font_size
            * 1.05,
            font_size * 2.0,
        )
        estimated_height = max(
            len(lines) * font_size * 1.55,
            font_size * 1.55,
        )
        padding_x = max(
            float(record.get("border_padding_x", 2.0)),
            0.0,
        )
        padding_y = max(
            float(record.get("border_padding_y", 1.0)),
            0.0,
        )
        margin = max(DEFAULT_MARGIN, 6.0)
        return None, QRectF(
            x - padding_x - margin,
            y - padding_y - margin,
            estimated_width + (padding_x + margin) * 2.0,
            estimated_height + (padding_y + margin) * 2.0,
        )

    x = float(record.get("x", 0.0))
    y = float(record.get("y", 0.0))
    width = max(
        float(
            record.get(
                "width",
                1.0,
            )
        ),
        1.0,
    )
    height = max(
        float(
            record.get(
                "height",
                1.0,
            )
        ),
        1.0,
    )
    margin = max(
        DEFAULT_MARGIN,
        float(
            record.get(
                "line_width",
                2.0,
            )
        )
        * 4.0,
    )
    return None, QRectF(
        x - margin,
        y - margin,
        width + margin * 2.0,
        height + margin * 2.0,
    )


def _font(record, scale):
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
                    max(
                        float(
                            record.get(
                                "font_size",
                                11.0,
                            )
                        ),
                        4.0,
                    )
                    * scale
                )
            ),
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


def _fitted_font(
    rect,
    text,
    record,
    scale,
):
    font = _font(
        record,
        scale,
    )
    value = str(text or "")
    minimum = max(
        int(round(5.0 * scale)),
        1,
    )

    while font.pixelSize() > minimum:
        metrics = QFontMetricsF(font)
        measured = metrics.boundingRect(
            rect,
            int(
                Qt.AlignmentFlag.AlignCenter
                | Qt.TextFlag.TextWordWrap
            ),
            value,
        )
        if (
            measured.width()
            <= rect.width() + 0.5
            and measured.height()
            <= rect.height() + 0.5
        ):
            break
        font.setPixelSize(
            max(
                minimum,
                font.pixelSize()
                - max(
                    1,
                    int(round(scale * 0.5)),
                ),
            )
        )

    return font


def _draw_check(
    painter,
    record,
    origin,
    scale,
):
    x = (
        float(record.get("x", 0.0))
        - origin.x()
    ) * scale
    y = (
        float(record.get("y", 0.0))
        - origin.y()
    ) * scale
    size = max(
        float(
            record.get(
                "size",
                15.0,
            )
        ),
        6.0,
    ) * scale
    width = max(
        float(
            record.get(
                "line_width",
                2.2,
            )
        ),
        0.5,
    ) * scale

    path = QPainterPath()
    path.moveTo(
        x - size * 0.48,
        y,
    )
    path.lineTo(
        x - size * 0.12,
        y + size * 0.38,
    )
    path.lineTo(
        x + size * 0.55,
        y - size * 0.48,
    )

    painter.setPen(
        QPen(
            _color(
                record.get("color"),
                "#dc0000",
            ),
            width,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    painter.setBrush(
        Qt.BrushStyle.NoBrush
    )
    painter.drawPath(path)


def _draw_arrow(
    painter,
    record,
    origin,
    scale,
):
    start = QPointF(
        (
            float(
                record.get(
                    "x",
                    0.0,
                )
            )
            - origin.x()
        )
        * scale,
        (
            float(
                record.get(
                    "y",
                    0.0,
                )
            )
            - origin.y()
        )
        * scale,
    )
    vector = QPointF(
        float(
            record.get(
                "dx",
                80.0,
            )
        )
        * scale,
        float(
            record.get(
                "dy",
                0.0,
            )
        )
        * scale,
    )
    end = start + vector
    line_width = max(
        float(
            record.get(
                "line_width",
                2.0,
            )
        ),
        0.5,
    ) * scale
    color = _color(
        record.get("color"),
        "#dc0000",
    )

    length = max(
        math.hypot(
            vector.x(),
            vector.y(),
        ),
        0.001,
    )
    ux = vector.x() / length
    uy = vector.y() / length
    head = min(
        max(
            line_width * 4.2,
            10.0 * scale,
        ),
        length * 0.45,
    )
    wing = head * 0.52
    base_x = end.x() - ux * head
    base_y = end.y() - uy * head
    perp_x = -uy
    perp_y = ux
    wing1 = QPointF(
        base_x + perp_x * wing,
        base_y + perp_y * wing,
    )
    wing2 = QPointF(
        base_x - perp_x * wing,
        base_y - perp_y * wing,
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
    painter.setBrush(
        Qt.BrushStyle.NoBrush
    )
    painter.drawLine(start, end)
    painter.drawLine(end, wing1)
    painter.drawLine(end, wing2)


def _draw_shape(
    painter,
    record,
    origin,
    scale,
):
    rect = QRectF(
        (
            float(
                record.get(
                    "x",
                    0.0,
                )
            )
            - origin.x()
        )
        * scale,
        (
            float(
                record.get(
                    "y",
                    0.0,
                )
            )
            - origin.y()
        )
        * scale,
        max(
            float(
                record.get(
                    "width",
                    80.0,
                )
            ),
            1.0,
        )
        * scale,
        max(
            float(
                record.get(
                    "height",
                    50.0,
                )
            ),
            1.0,
        )
        * scale,
    )
    kind = str(
        record.get(
            "type",
            "rectangle",
        )
    )
    line_width = max(
        float(
            record.get(
                "line_width",
                2.0,
            )
        ),
        0.5,
    ) * scale
    path = QPainterPath()

    if kind == "ellipse":
        path.addEllipse(rect)
    elif kind == "cloud":
        path = _cloud_path(
            rect,
            float(
                record.get(
                    "cloud_radius",
                    8.0,
                )
            )
            * scale,
        )
    else:
        path.addRect(rect)

    if bool(
        record.get(
            "fill_enabled",
            False,
        )
    ):
        fill = _color(
            record.get(
                "fill_color",
                "#ffff00",
            ),
            "#ffff00",
        )
        fill.setAlphaF(
            max(
                0.0,
                min(
                    float(
                        record.get(
                            "fill_opacity",
                            0.25,
                        )
                    ),
                    1.0,
                ),
            )
        )
        painter.save()
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Multiply
        )
        painter.setPen(
            Qt.PenStyle.NoPen
        )
        painter.setBrush(
            QBrush(fill)
        )
        painter.drawPath(path)
        painter.restore()

    painter.setCompositionMode(
        QPainter.CompositionMode.CompositionMode_SourceOver
    )
    painter.setPen(
        QPen(
            _color(
                record.get("color"),
                "#dc0000",
            ),
            line_width,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    painter.setBrush(
        Qt.BrushStyle.NoBrush
    )
    painter.drawPath(path)

    text = str(
        record.get(
            "text",
            "",
        )
    ).strip()
    if (
        text
        and kind
        in {
            "rectangle",
            "cloud",
        }
    ):
        margin = max(
            5.0 * scale,
            line_width * 2.0,
        )
        text_rect = rect.adjusted(
            margin,
            margin,
            -margin,
            -margin,
        )
        painter.setFont(
            _fitted_font(
                text_rect,
                text,
                record,
                scale,
            )
        )
        painter.setPen(
            _color(
                record.get(
                    "text_color",
                    "#000000",
                ),
                "#000000",
            )
        )
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter
            | Qt.TextFlag.TextWordWrap,
            text,
        )


def _draw_freehand(
    painter,
    record,
    origin,
    scale,
):
    path = _freehand_path(
        _absolute_points(record),
        origin,
        scale,
    )
    color = _color(
        record.get("color"),
        "#dc0000",
    )
    line_width = max(
        float(
            record.get(
                "line_width",
                2.0,
            )
        ),
        0.5,
    ) * scale
    opacity = max(
        0.05,
        min(
            float(record.get("opacity", 1.0)),
            1.0,
        ),
    )
    painter.setOpacity(opacity)
    if str(record.get("tool", "freehand")) == "highlighter":
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Multiply
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
    painter.setBrush(
        Qt.BrushStyle.NoBrush
    )
    painter.drawPath(path)
    painter.setOpacity(1.0)
    painter.setCompositionMode(
        QPainter.CompositionMode.CompositionMode_SourceOver
    )


def _draw_text(
    painter,
    record,
    origin,
    scale,
):
    x = (
        float(record.get("x", 0.0))
        - origin.x()
    ) * scale
    y = (
        float(record.get("y", 0.0))
        - origin.y()
    ) * scale
    value = str(record.get("text", ""))
    font = _font(record, scale)
    metrics = QFontMetricsF(font)

    lines = value.splitlines() or [""]
    width = max(
        [metrics.horizontalAdvance(line) for line in lines]
        + [font.pixelSize() * 2.0]
    ) + 4.0 * scale
    height = max(
        metrics.lineSpacing() * len(lines),
        metrics.height(),
    ) + 4.0 * scale

    text_rect = QRectF(x, y, width, height)
    padding_x = max(
        float(record.get("border_padding_x", 2.0)) * scale,
        0.0,
    )
    padding_y = max(
        float(record.get("border_padding_y", 1.0)) * scale,
        0.0,
    )

    if bool(record.get("border_enabled", False)):
        border_rect = text_rect.adjusted(
            -padding_x,
            -padding_y,
            padding_x,
            padding_y,
        )
        painter.setPen(
            QPen(
                _color(record.get("border_color"), "#dc0000"),
                max(float(record.get("border_width", 1.5)), 0.5)
                * scale,
            )
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(border_rect)

    painter.setFont(font)
    painter.setPen(
        _color(record.get("text_color"), "#dc0000")
    )
    painter.drawText(
        text_rect,
        Qt.AlignmentFlag.AlignLeft
        | Qt.AlignmentFlag.AlignTop,
        value,
    )


def _draw_date_stamp(
    painter,
    record,
    origin,
    scale,
):
    size = max(
        float(
            record.get(
                "size",
                72.0,
            )
        ),
        24.0,
    ) * scale
    center = QPointF(
        (
            float(
                record.get(
                    "x",
                    0.0,
                )
            )
            - origin.x()
        )
        * scale,
        (
            float(
                record.get(
                    "y",
                    0.0,
                )
            )
            - origin.y()
        )
        * scale,
    )
    rect = QRectF(
        center.x() - size / 2.0,
        center.y() - size / 2.0,
        size,
        size,
    )
    scaled = dict(record)
    scaled["size"] = size
    draw_date_stamp(
        painter,
        rect,
        scaled,
    )


def render_annotation_image(
    record,
    scale=DEFAULT_SCALE,
):
    special_image, bounds = _record_bounds(
        record
    )
    if special_image is not None:
        return special_image, bounds

    if bounds is None:
        return None, None

    width = max(
        int(
            math.ceil(
                bounds.width()
                * scale
            )
        ),
        1,
    )
    height = max(
        int(
            math.ceil(
                bounds.height()
                * scale
            )
        ),
        1,
    )

    image = QImage(
        width,
        height,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(
        Qt.GlobalColor.transparent
    )

    painter = QPainter(image)
    painter.setRenderHint(
        QPainter.RenderHint.Antialiasing,
        True,
    )
    painter.setRenderHint(
        QPainter.RenderHint.TextAntialiasing,
        True,
    )
    painter.setRenderHint(
        QPainter.RenderHint.SmoothPixmapTransform,
        True,
    )

    origin = bounds.topLeft()
    kind = str(
        record.get(
            "type",
            "",
        )
    )

    if kind == "check":
        _draw_check(
            painter,
            record,
            origin,
            scale,
        )
    elif kind == "arrow":
        _draw_arrow(
            painter,
            record,
            origin,
            scale,
        )
    elif kind in {
        "rectangle",
        "ellipse",
        "cloud",
    }:
        _draw_shape(
            painter,
            record,
            origin,
            scale,
        )
    elif kind in {
        "freehand",
        "highlighter",
    }:
        _draw_freehand(
            painter,
            record,
            origin,
            scale,
        )
    elif kind == "text":
        _draw_text(
            painter,
            record,
            origin,
            scale,
        )
    elif kind == "date_stamp":
        _draw_date_stamp(
            painter,
            record,
            origin,
            scale,
        )
    else:
        painter.end()
        return None, None

    painter.end()
    return image, bounds
