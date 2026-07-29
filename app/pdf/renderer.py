import fitz
from PySide6.QtGui import QImage, QPixmap


class PDFRenderer:
    MIN_SCALE = 1.0
    MAX_SCALE = 8.0
    MAX_PIXELS = 48_000_000

    def render_display_list(
        self,
        display_list,
        page_rect,
        scale: float = 2.0,
    ) -> tuple[QPixmap, float]:
        scale = self._limit_scale(page_rect, scale)

        pix = display_list.get_pixmap(
            matrix=fitz.Matrix(scale, scale),
            alpha=False,
        )

        image = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format.Format_RGB888,
        ).copy()

        return QPixmap.fromImage(image), scale

    def _limit_scale(self, page_rect, requested_scale: float) -> float:
        scale = max(
            self.MIN_SCALE,
            min(float(requested_scale), self.MAX_SCALE),
        )

        page_area = page_rect.width * page_rect.height
        if page_area <= 0:
            return scale

        requested_pixels = page_area * scale * scale
        if requested_pixels <= self.MAX_PIXELS:
            return scale

        limited = (self.MAX_PIXELS / page_area) ** 0.5
        return max(
            self.MIN_SCALE,
            min(limited, scale),
        )
