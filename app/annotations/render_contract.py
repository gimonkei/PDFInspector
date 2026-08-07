from __future__ import annotations

from dataclasses import dataclass

import fitz
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF
from PySide6.QtGui import QImage


@dataclass(frozen=True)
class RenderedAnnotation:
    image: QImage
    bounds: QRectF

    def __post_init__(self):
        if not isinstance(self.image, QImage):
            raise TypeError(f"image must be QImage, got {type(self.image).__name__}")
        if self.image.isNull():
            raise ValueError("image must not be null")
        if not isinstance(self.bounds, QRectF):
            raise TypeError(f"bounds must be QRectF, got {type(self.bounds).__name__}")
        if self.bounds.width() <= 0 or self.bounds.height() <= 0:
            raise ValueError("bounds must have positive size")


def image_to_png_bytes(image: QImage) -> bytes:
    if not isinstance(image, QImage):
        raise TypeError(f"QImage required, got {type(image).__name__}")
    if image.isNull():
        raise ValueError("cannot encode null QImage")
    data=QByteArray(); buffer=QBuffer(data)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("could not open PNG buffer")
    try:
        if not image.save(buffer, "PNG"):
            raise RuntimeError("could not encode PNG")
    finally:
        buffer.close()
    return bytes(data)


def qrectf_to_fitz_rect(bounds: QRectF) -> fitz.Rect:
    if not isinstance(bounds, QRectF):
        raise TypeError(f"QRectF required, got {type(bounds).__name__}")
    return fitz.Rect(float(bounds.left()), float(bounds.top()), float(bounds.right()), float(bounds.bottom()))
