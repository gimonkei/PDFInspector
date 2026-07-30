import fitz
from PySide6.QtGui import QImage

from app.pdf.hairline_enhancer import HairlineEnhancer
from app.pdf.vector_hairline_overlay import VectorHairlineOverlay


class PDFRenderer:
    # MuPDF supports matrices below 1.0. Low zoom is deliberately rendered
    # at near-native display resolution to avoid a second destructive shrink.
    MIN_SCALE = 0.20
    MAX_SCALE = 8.0
    MAX_TILE_PIXELS = 4_000_000

    def __init__(self):
        self.hairline_enhancer = HairlineEnhancer()
        self.vector_hairline_overlay = VectorHairlineOverlay()

    def render_display_list_tile(
        self,
        display_list,
        page_rect,
        clip_rect,
        scale: float = 2.0,
        zoom_factor: float = 1.0,
        hairline_enabled: bool = True,
        drawings=(),
    ) -> tuple[QImage, float]:
        """
        Render a tile as QImage.

        QImage is safe to create in a worker thread. QPixmap conversion is
        deliberately deferred to PDFView on the GUI thread.
        """
        scale = self._limit_scale(clip_rect, scale)

        clip = fitz.Rect(
            max(page_rect.x0, clip_rect.x0),
            max(page_rect.y0, clip_rect.y0),
            min(page_rect.x1, clip_rect.x1),
            min(page_rect.y1, clip_rect.y1),
        )

        if clip.is_empty:
            return QImage(), scale

        pix = display_list.get_pixmap(
            matrix=fitz.Matrix(scale, scale),
            clip=clip,
            alpha=False,
        )

        image = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format.Format_RGB888,
        ).copy()

        if hairline_enabled:
            image = self.hairline_enhancer.apply(
                image,
                zoom_factor,
            )
            image = self.vector_hairline_overlay.apply(
                image,
                drawings,
                clip,
                scale,
            )
        return image, scale

    def _limit_scale(self, clip_rect, requested_scale: float) -> float:
        scale = max(
            self.MIN_SCALE,
            min(float(requested_scale), self.MAX_SCALE),
        )

        area = max(0.0, clip_rect.width) * max(0.0, clip_rect.height)
        if area <= 0:
            return scale

        requested_pixels = area * scale * scale
        if requested_pixels <= self.MAX_TILE_PIXELS:
            return scale

        limited = (self.MAX_TILE_PIXELS / area) ** 0.5
        return max(
            self.MIN_SCALE,
            min(limited, scale),
        )
