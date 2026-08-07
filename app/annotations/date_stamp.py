import math

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen


COLORS = {
    "black": QColor(0, 0, 0),
    "blue": QColor(0, 70, 220),
    "red": QColor(220, 0, 0),
}


def stamp_color(name):
    return COLORS.get(str(name), COLORS["black"])


def separator_geometry(rect, line_width):
    radius = rect.width() / 2.0
    center = rect.center()
    result = []
    for ratio in (0.34, 0.66):
        y = rect.top() + rect.height() * ratio
        dy = y - center.y()
        half = math.sqrt(max(radius * radius - dy * dy, 0.0))
        inset = max(float(line_width) * 0.75, 1.0)
        half = max(half - inset, 0.0)
        result.append((y, center.x() - half, center.x() + half))
    return result


def _draw_visually_centered_text(painter, rect, text, color, font_size):
    value = str(text or "")
    if not value:
        return
    font = QFont(painter.font())
    font.setBold(True)
    font.setPointSizeF(max(float(font_size), 5.0))
    painter.setFont(font)
    painter.setPen(color)
    bounds = painter.fontMetrics().tightBoundingRect(value)
    x = rect.center().x() - bounds.center().x()
    y = rect.center().y() - bounds.center().y()
    painter.drawText(QPointF(x, y), value)


def draw_date_stamp(painter, rect, record):
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    color = stamp_color(record.get("color", "black"))
    width = max(float(record.get("line_width", 1.5)), 0.5)
    painter.setPen(QPen(color, width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(rect)

    separators = separator_geometry(rect, width)
    for y, left, right in separators:
        painter.drawLine(QPointF(left, y), QPointF(right, y))

    y1 = separators[0][0]
    y2 = separators[1][0]
    text_inset = rect.width() * 0.08
    top_rect = QRectF(rect.left() + text_inset, rect.top(), rect.width() - text_inset * 2, y1 - rect.top())
    date_rect = QRectF(rect.left() + text_inset, y1, rect.width() - text_inset * 2, y2 - y1)
    bottom_rect = QRectF(rect.left() + text_inset, y2, rect.width() - text_inset * 2, rect.bottom() - y2)

    base_size = max(6.0, rect.height() * 0.13)
    _draw_visually_centered_text(painter, top_rect, record.get("top", ""), color, base_size)
    _draw_visually_centered_text(painter, date_rect, record.get("date", ""), color, base_size * 0.82)
    _draw_visually_centered_text(painter, bottom_rect, record.get("bottom", ""), color, base_size)
    painter.restore()


def render_date_stamp_image(record, scale=4.0):
    size_pt = max(float(record.get("size", 72.0)), 42.0)
    scale = max(float(scale), 1.0)
    pixels = max(int(round(size_pt * scale)), 1)
    image = QImage(pixels, pixels, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.scale(scale, scale)
        margin = max(float(record.get("line_width", 1.5)), 0.5) / 2.0 + 0.75
        rect = QRectF(margin, margin, size_pt-margin*2.0, size_pt-margin*2.0)
        draw_date_stamp(painter, rect, record)
    finally:
        painter.end()
    return image


def render_date_stamp_png(record, scale=4.0):
    image = render_date_stamp_image(record, scale=scale)
    data=QByteArray(); buffer=QBuffer(data)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("could not open date stamp PNG buffer")
    try:
        if not image.save(buffer, "PNG"):
            raise RuntimeError("could not encode date stamp PNG")
    finally:
        buffer.close()
    return bytes(data)
