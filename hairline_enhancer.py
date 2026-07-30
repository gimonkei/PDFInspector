from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QImage


@dataclass(frozen=True)
class HairlineSettings:
    enabled: bool = True
    max_zoom: float = 2.00
    threshold: int = 244
    strength: float = 0.82
    min_run: int = 10
    max_gap: int = 3


class HairlineEnhancer:
    """Display-only recovery for faint and interrupted CAD hairlines."""

    def __init__(self, settings: HairlineSettings | None = None):
        self.settings = settings or HairlineSettings()

    def apply(self, image: QImage, zoom_factor: float) -> QImage:
        if (
            not self.settings.enabled
            or zoom_factor > self.settings.max_zoom
            or image.isNull()
        ):
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
            rgb.bits(),
            dtype=np.uint8,
            count=height * bytes_per_line,
        ).reshape((height, bytes_per_line))
        pixels = array[:, : width * 3].reshape((height, width, 3))

        gray = (
            pixels[:, :, 0].astype(np.uint16) * 77
            + pixels[:, :, 1].astype(np.uint16) * 150
            + pixels[:, :, 2].astype(np.uint16) * 29
        ) >> 8

        dark = gray < self.settings.threshold

        # Preserve the original generic one-pixel enhancement.
        padded = np.pad(
            dark,
            1,
            mode="constant",
            constant_values=False,
        )
        neighbours = np.zeros_like(gray, dtype=np.uint8)
        for dy in range(3):
            for dx in range(3):
                if dx == 1 and dy == 1:
                    continue
                neighbours += padded[
                    dy:dy + height,
                    dx:dx + width,
                ]

        sparse = dark & (neighbours >= 1) & (neighbours <= 4)
        expanded = sparse.copy()
        expanded[:-1, :] |= sparse[1:, :]
        expanded[1:, :] |= sparse[:-1, :]
        expanded[:, :-1] |= sparse[:, 1:]
        expanded[:, 1:] |= sparse[:, :-1]

        # Recover long horizontal and vertical CAD strokes separately.
        # This closes tiny antialiasing gaps without broadly thickening text.
        horizontal = self._directional_runs(
            dark,
            axis=1,
            min_run=self.settings.min_run,
            max_gap=self.settings.max_gap,
        )
        vertical = self._directional_runs(
            dark,
            axis=0,
            min_run=self.settings.min_run,
            max_gap=self.settings.max_gap,
        )
        line_mask = horizontal | vertical

        # Give recovered lines a single neighbouring pixel in the direction
        # perpendicular to the stroke. This makes border corners continuous.
        line_expanded = line_mask.copy()
        line_expanded[:-1, :] |= horizontal[1:, :]
        line_expanded[1:, :] |= horizontal[:-1, :]
        line_expanded[:, :-1] |= vertical[:, 1:]
        line_expanded[:, 1:] |= vertical[:, :-1]

        zoom_weight = 1.0 - min(
            max(float(zoom_factor), 0.1) / self.settings.max_zoom,
            1.0,
        )
        effective = self.settings.strength * (
            0.55 + zoom_weight * 0.45
        )

        target = pixels.astype(np.float32)
        target[expanded] *= 1.0 - effective * 0.32

        # Directionally detected lines receive stronger contrast recovery.
        target[line_expanded] *= 1.0 - effective * 0.68

        pixels[:, :, :] = np.clip(
            target,
            0,
            255,
        ).astype(np.uint8)
        return rgb.copy()

    @staticmethod
    def _directional_runs(
        mask,
        axis: int,
        min_run: int,
        max_gap: int,
    ):
        """
        Find long line-like runs and bridge short gaps.

        axis=1 detects horizontal lines; axis=0 detects vertical lines.
        """
        import numpy as np

        work = mask if axis == 1 else mask.T
        result = np.zeros_like(work, dtype=bool)
        length = work.shape[1]

        for offset in range(-max_gap, max_gap + 1):
            shifted = np.zeros_like(work, dtype=bool)
            if offset < 0:
                shifted[:, :offset] = work[:, -offset:]
            elif offset > 0:
                shifted[:, offset:] = work[:, :-offset]
            else:
                shifted = work.copy()
            result |= shifted

        # Rolling-window density: long CAD lines remain dense even when a few
        # pixels vanished, whereas ordinary text strokes are usually shorter.
        window = max(min_run, 3)
        padded = np.pad(
            result.astype(np.uint16),
            ((0, 0), (window // 2, window - 1 - window // 2)),
            mode="constant",
        )
        cumulative = np.cumsum(padded, axis=1, dtype=np.uint32)
        cumulative = np.pad(
            cumulative,
            ((0, 0), (1, 0)),
            mode="constant",
        )
        counts = cumulative[:, window:] - cumulative[:, :-window]
        dense = counts >= max(3, window - max_gap * 2)

        # Extend dense windows through the exact source/recovered run.
        recovered = result & dense
        for offset in range(1, max_gap + 2):
            left = np.zeros_like(recovered)
            right = np.zeros_like(recovered)
            left[:, offset:] = recovered[:, :-offset]
            right[:, :-offset] = recovered[:, offset:]
            recovered |= result & (left | right)

        return recovered if axis == 1 else recovered.T
