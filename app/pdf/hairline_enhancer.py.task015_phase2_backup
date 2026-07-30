from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtGui import QImage


@dataclass(frozen=True)
class HairlineSettings:
    enabled: bool = True
    max_zoom: float = 1.50
    threshold: int = 232
    strength: float = 0.72


class HairlineEnhancer:
    """Display-only enhancement for faint one-pixel CAD strokes."""

    def __init__(self, settings: HairlineSettings | None = None):
        self.settings = settings or HairlineSettings()

    def apply(self, image: QImage, zoom_factor: float) -> QImage:
        if not self.settings.enabled or zoom_factor > self.settings.max_zoom or image.isNull():
            return image

        try:
            import numpy as np
        except ImportError:
            return image

        rgb = image.convertToFormat(QImage.Format.Format_RGB888)
        height = rgb.height()
        width = rgb.width()
        bytes_per_line = rgb.bytesPerLine()
        array = np.frombuffer(
            rgb.bits(), dtype=np.uint8, count=height * bytes_per_line
        ).reshape((height, bytes_per_line))
        pixels = array[:, : width * 3].reshape((height, width, 3))

        gray = (
            pixels[:, :, 0].astype(np.uint16) * 77
            + pixels[:, :, 1].astype(np.uint16) * 150
            + pixels[:, :, 2].astype(np.uint16) * 29
        ) >> 8
        dark = gray < self.settings.threshold

        padded = np.pad(dark, 1, mode='constant', constant_values=False)
        neighbours = np.zeros_like(gray, dtype=np.uint8)
        for dy in range(3):
            for dx in range(3):
                if dx == 1 and dy == 1:
                    continue
                neighbours += padded[dy:dy + height, dx:dx + width]

        candidate = dark & (neighbours >= 1) & (neighbours <= 4)
        expanded = candidate.copy()
        expanded[:-1, :] |= candidate[1:, :]
        expanded[1:, :] |= candidate[:-1, :]
        expanded[:, :-1] |= candidate[:, 1:]
        expanded[:, 1:] |= candidate[:, :-1]

        zoom_weight = 1.0 - min(max(float(zoom_factor), 0.1) / self.settings.max_zoom, 1.0)
        effective = self.settings.strength * (0.45 + zoom_weight * 0.55)
        target = pixels.astype(np.float32)
        target[expanded] *= (1.0 - effective * 0.48)
        pixels[:, :, :] = np.clip(target, 0, 255).astype(np.uint8)
        return rgb.copy()
