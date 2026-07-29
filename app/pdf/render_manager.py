from collections import OrderedDict
from dataclasses import dataclass

from PySide6.QtGui import QPixmap

from app.pdf.renderer import PDFRenderer


@dataclass(frozen=True)
class PageDisplayData:
    page_index: int
    display_list: object
    page_rect: object


@dataclass(frozen=True)
class RenderedPage:
    page_index: int
    pixmap: QPixmap
    render_scale: float
    scene_width: float
    scene_height: float


class RenderManager:
    MIN_RENDER_SCALE = 2.0
    MAX_RENDER_SCALE = 8.0
    SCALE_STEP = 0.25
    OVERSAMPLE = 1.35
    MAX_PIXMAP_CACHE_ITEMS = 32

    def __init__(self, renderer: PDFRenderer):
        self.renderer = renderer
        self._display_list_cache = {}
        self._pixmap_cache = OrderedDict()

    def clear(self):
        self._display_list_cache.clear()
        self._pixmap_cache.clear()

    def clear_pixmaps(self):
        self._pixmap_cache.clear()

    def target_scale(
        self,
        zoom_factor: float,
        device_pixel_ratio: float = 1.0,
    ) -> float:
        raw_scale = (
            max(float(zoom_factor), 0.1)
            * max(float(device_pixel_ratio), 1.0)
            * self.OVERSAMPLE
        )

        scale = max(
            self.MIN_RENDER_SCALE,
            min(raw_scale, self.MAX_RENDER_SCALE),
        )

        quantized = round(
            scale / self.SCALE_STEP
        ) * self.SCALE_STEP

        return max(
            self.MIN_RENDER_SCALE,
            min(quantized, self.MAX_RENDER_SCALE),
        )

    def prepare_document(self, document):
        valid_indexes = set(range(document.page_count))

        stale_indexes = [
            index
            for index in self._display_list_cache
            if index not in valid_indexes
        ]

        for index in stale_indexes:
            del self._display_list_cache[index]

        for index in range(document.page_count):
            self._get_display_data(document, index)

    def render_document(
        self,
        document,
        zoom_factor: float,
        device_pixel_ratio: float = 1.0,
    ):
        scale = self.target_scale(
            zoom_factor,
            device_pixel_ratio,
        )

        return [
            self.render_page(document, index, scale)
            for index in range(document.page_count)
        ]

    def render_page(
        self,
        document,
        page_index: int,
        render_scale: float,
    ) -> RenderedPage:
        key = (
            int(page_index),
            round(float(render_scale), 2),
        )

        cached = self._pixmap_cache.get(key)
        if cached is not None:
            self._pixmap_cache.move_to_end(key)
            return cached

        display_data = self._get_display_data(
            document,
            page_index,
        )

        pixmap, actual_scale = self.renderer.render_display_list(
            display_data.display_list,
            display_data.page_rect,
            render_scale,
        )

        rendered = RenderedPage(
            page_index=page_index,
            pixmap=pixmap,
            render_scale=actual_scale,
            scene_width=float(display_data.page_rect.width),
            scene_height=float(display_data.page_rect.height),
        )

        self._pixmap_cache[key] = rendered
        self._pixmap_cache.move_to_end(key)

        while (
            len(self._pixmap_cache)
            > self.MAX_PIXMAP_CACHE_ITEMS
        ):
            self._pixmap_cache.popitem(last=False)

        return rendered

    def _get_display_data(
        self,
        document,
        page_index: int,
    ) -> PageDisplayData:
        cached = self._display_list_cache.get(page_index)
        if cached is not None:
            return cached

        page = document.get_page(page_index)

        if page is None:
            raise IndexError(
                f"PDF page does not exist: {page_index}"
            )

        data = PageDisplayData(
            page_index=page_index,
            display_list=page.get_displaylist(),
            page_rect=page.rect,
        )

        self._display_list_cache[page_index] = data
        return data
