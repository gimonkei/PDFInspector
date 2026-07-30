from collections import OrderedDict
from dataclasses import dataclass
import math

import fitz
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPixmap

from app.pdf.renderer import PDFRenderer


@dataclass(frozen=True)
class PageDisplayData:
    page_index: int
    display_list: object
    page_rect: object


@dataclass(frozen=True)
class RenderedTile:
    page_index: int
    column: int
    row: int
    pixmap: QPixmap
    render_scale: float
    scene_x: float
    scene_y: float
    scene_width: float
    scene_height: float


@dataclass(frozen=True)
class RenderedPage:
    page_index: int
    tiles: tuple[RenderedTile, ...]
    render_scale: float
    scene_width: float
    scene_height: float


class RenderManager:
    MIN_RENDER_SCALE = 2.0
    MAX_RENDER_SCALE = 8.0
    SCALE_STEP = 0.25
    OVERSAMPLE = 1.35

    # Rendered device-pixel size of one tile.
    TILE_PIXEL_SIZE = 768
    MAX_TILE_CACHE_ITEMS = 256

    def __init__(self, renderer: PDFRenderer):
        self.renderer = renderer
        self.hairline_enabled = True
        self._display_list_cache = {}
        self._tile_cache = OrderedDict()

    def clear(self):
        self._display_list_cache.clear()
        self._tile_cache.clear()

    def clear_pixmaps(self):
        self._tile_cache.clear()

    def set_hairline_enabled(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self.hairline_enabled:
            return
        self.hairline_enabled = enabled
        self.clear_pixmaps()

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
        quantized = round(scale / self.SCALE_STEP) * self.SCALE_STEP
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

    def get_page_layouts(self, document) -> list[RenderedPage]:
        """Return lightweight page geometry without rendering any bitmap."""
        layouts = []
        for index in range(document.page_count):
            data = self._get_display_data(document, index)
            layouts.append(
                RenderedPage(
                    page_index=index,
                    tiles=(),
                    render_scale=1.0,
                    scene_width=float(data.page_rect.width),
                    scene_height=float(data.page_rect.height),
                )
            )
        return layouts

    def render_regions(
        self,
        document,
        page_regions: dict[int, QRectF],
        zoom_factor: float,
        device_pixel_ratio: float = 1.0,
    ) -> list[RenderedPage]:
        """
        Render only tiles intersecting the requested page-local rectangles.

        page_regions:
            {page_index: QRectF(x, y, width, height)}
            Coordinates are PDF page-local scene coordinates.
        """
        render_scale = self.target_scale(
            zoom_factor,
            device_pixel_ratio,
        )
        rendered_pages = []

        for page_index, requested_region in sorted(page_regions.items()):
            if page_index < 0 or page_index >= document.page_count:
                continue

            data = self._get_display_data(document, page_index)
            page_rect = data.page_rect
            local_page = QRectF(
                0.0,
                0.0,
                float(page_rect.width),
                float(page_rect.height),
            )
            region = requested_region.intersected(local_page)
            if region.isEmpty():
                continue

            tiles = self._render_region_tiles(
                data,
                region,
                render_scale,
                zoom_factor,
            )
            rendered_pages.append(
                RenderedPage(
                    page_index=page_index,
                    tiles=tuple(tiles),
                    render_scale=render_scale,
                    scene_width=float(page_rect.width),
                    scene_height=float(page_rect.height),
                )
            )

        return rendered_pages

    def _render_region_tiles(
        self,
        display_data: PageDisplayData,
        region: QRectF,
        render_scale: float,
        zoom_factor: float,
    ) -> list[RenderedTile]:
        page_rect = display_data.page_rect
        tile_scene_size = self.TILE_PIXEL_SIZE / render_scale

        max_column = max(
            0,
            math.ceil(float(page_rect.width) / tile_scene_size) - 1,
        )
        max_row = max(
            0,
            math.ceil(float(page_rect.height) / tile_scene_size) - 1,
        )

        first_column = max(
            0,
            min(max_column, math.floor(region.left() / tile_scene_size)),
        )
        last_column = max(
            0,
            min(max_column, math.floor(
                max(region.right() - 1e-7, region.left())
                / tile_scene_size
            )),
        )
        first_row = max(
            0,
            min(max_row, math.floor(region.top() / tile_scene_size)),
        )
        last_row = max(
            0,
            min(max_row, math.floor(
                max(region.bottom() - 1e-7, region.top())
                / tile_scene_size
            )),
        )

        tiles = []
        for row in range(first_row, last_row + 1):
            for column in range(first_column, last_column + 1):
                local_x0 = column * tile_scene_size
                local_y0 = row * tile_scene_size
                local_x1 = min(
                    float(page_rect.width),
                    local_x0 + tile_scene_size,
                )
                local_y1 = min(
                    float(page_rect.height),
                    local_y0 + tile_scene_size,
                )

                clip_rect = fitz.Rect(
                    page_rect.x0 + local_x0,
                    page_rect.y0 + local_y0,
                    page_rect.x0 + local_x1,
                    page_rect.y0 + local_y1,
                )
                tiles.append(
                    self.render_tile(
                        display_data,
                        column,
                        row,
                        clip_rect,
                        render_scale,
                        zoom_factor,
                    )
                )
        return tiles

    def render_tile(
        self,
        display_data: PageDisplayData,
        column: int,
        row: int,
        clip_rect,
        render_scale: float,
        zoom_factor: float,
    ) -> RenderedTile:
        key = (
            int(display_data.page_index),
            int(column),
            int(row),
            round(float(render_scale), 2),
            round(float(zoom_factor), 2),
            self.hairline_enabled,
        )

        cached = self._tile_cache.get(key)
        if cached is not None:
            self._tile_cache.move_to_end(key)
            return cached

        pixmap, actual_scale = self.renderer.render_display_list_tile(
            display_data.display_list,
            display_data.page_rect,
            clip_rect,
            render_scale,
            zoom_factor,
            self.hairline_enabled,
        )

        rendered = RenderedTile(
            page_index=display_data.page_index,
            column=column,
            row=row,
            pixmap=pixmap,
            render_scale=actual_scale,
            scene_x=float(clip_rect.x0 - display_data.page_rect.x0),
            scene_y=float(clip_rect.y0 - display_data.page_rect.y0),
            scene_width=float(clip_rect.width),
            scene_height=float(clip_rect.height),
        )

        self._tile_cache[key] = rendered
        self._tile_cache.move_to_end(key)
        while len(self._tile_cache) > self.MAX_TILE_CACHE_ITEMS:
            self._tile_cache.popitem(last=False)

        return rendered

    def tile_cache_count(self) -> int:
        return len(self._tile_cache)

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
            raise IndexError(f"PDF page does not exist: {page_index}")

        data = PageDisplayData(
            page_index=page_index,
            display_list=page.get_displaylist(),
            page_rect=page.rect,
        )
        self._display_list_cache[page_index] = data
        return data
