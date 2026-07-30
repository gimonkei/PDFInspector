from collections import OrderedDict
from dataclasses import dataclass
import math

import fitz
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage

from app.pdf.renderer import PDFRenderer


@dataclass(frozen=True)
class PageDisplayData:
    page_index: int
    display_list: object
    page_rect: object
    drawings: tuple


@dataclass(frozen=True)
class RenderedTile:
    page_index: int
    column: int
    row: int
    image: QImage
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
    # At low zoom, render close to the final device resolution instead of
    # producing a 2x bitmap and shrinking it again in QGraphicsView. This keeps
    # a recovered one-pixel CAD line as one display pixel.
    MIN_RENDER_SCALE = 0.20
    MAX_RENDER_SCALE = 8.0
    LOW_ZOOM_LIMIT = 1.50
    LOW_ZOOM_SCALE_STEP = 0.05
    HIGH_ZOOM_SCALE_STEP = 0.25
    HIGH_ZOOM_OVERSAMPLE = 1.35

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
        zoom = max(float(zoom_factor), self.MIN_RENDER_SCALE)
        device_ratio = max(float(device_pixel_ratio), 1.0)
        native_scale = zoom * device_ratio

        if zoom <= self.LOW_ZOOM_LIMIT:
            # Native-resolution mode: after the graphics-view transform,
            # roughly one rendered pixel maps to one physical display pixel.
            raw_scale = native_scale
            step = self.LOW_ZOOM_SCALE_STEP
        else:
            raw_scale = native_scale * self.HIGH_ZOOM_OVERSAMPLE
            step = self.HIGH_ZOOM_SCALE_STEP

        scale = max(
            self.MIN_RENDER_SCALE,
            min(raw_scale, self.MAX_RENDER_SCALE),
        )
        quantized = round(scale / step) * step
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
        Render requested tiles in viewport-center-first order.

        All tile candidates are collected before rendering. Their priority is
        the squared distance from the requested region center to the tile
        center, so the area the user is looking at becomes sharp first.
        """
        render_scale = self.target_scale(
            zoom_factor,
            device_pixel_ratio,
        )

        page_contexts = {}
        tile_requests = []

        for page_index, requested_region in page_regions.items():
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

            page_contexts[page_index] = data
            tile_requests.extend(
                self._collect_region_tiles(
                    data,
                    region,
                    render_scale,
                )
            )

        # Lowest distance is rendered first. Stable secondary keys keep the
        # order deterministic when multiple tiles have equal priority.
        tile_requests.sort(
            key=lambda request: (
                request[0],
                request[1],
                request[3],
                request[2],
            )
        )

        tiles_by_page = {
            page_index: []
            for page_index in page_contexts
        }

        for (
            _priority,
            page_index,
            column,
            row,
            clip_rect,
        ) in tile_requests:
            data = page_contexts[page_index]
            tiles_by_page[page_index].append(
                self.render_tile(
                    data,
                    column,
                    row,
                    clip_rect,
                    render_scale,
                    zoom_factor,
                )
            )

        rendered_pages = []
        for page_index, data in page_contexts.items():
            page_rect = data.page_rect
            rendered_pages.append(
                RenderedPage(
                    page_index=page_index,
                    tiles=tuple(tiles_by_page[page_index]),
                    render_scale=render_scale,
                    scene_width=float(page_rect.width),
                    scene_height=float(page_rect.height),
                )
            )

        return rendered_pages

    def _collect_region_tiles(
        self,
        display_data: PageDisplayData,
        region: QRectF,
        render_scale: float,
    ) -> list[tuple[float, int, int, int, object]]:
        """Collect tile render requests with center-distance priorities."""
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
            min(
                max_column,
                math.floor(
                    max(region.right() - 1e-7, region.left())
                    / tile_scene_size
                ),
            ),
        )
        first_row = max(
            0,
            min(max_row, math.floor(region.top() / tile_scene_size)),
        )
        last_row = max(
            0,
            min(
                max_row,
                math.floor(
                    max(region.bottom() - 1e-7, region.top())
                    / tile_scene_size
                ),
            ),
        )

        focus_x = float(region.center().x())
        focus_y = float(region.center().y())
        requests = []

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

                tile_center_x = (local_x0 + local_x1) * 0.5
                tile_center_y = (local_y0 + local_y1) * 0.5
                delta_x = tile_center_x - focus_x
                delta_y = tile_center_y - focus_y
                priority = delta_x * delta_x + delta_y * delta_y

                clip_rect = fitz.Rect(
                    page_rect.x0 + local_x0,
                    page_rect.y0 + local_y0,
                    page_rect.x0 + local_x1,
                    page_rect.y0 + local_y1,
                )
                requests.append(
                    (
                        priority,
                        display_data.page_index,
                        column,
                        row,
                        clip_rect,
                    )
                )

        return requests

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

        image, actual_scale = self.renderer.render_display_list_tile(
            display_data.display_list,
            display_data.page_rect,
            clip_rect,
            render_scale,
            zoom_factor,
            self.hairline_enabled,
            display_data.drawings,
        )

        rendered = RenderedTile(
            page_index=display_data.page_index,
            column=column,
            row=row,
            image=image,
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
            drawings=tuple(page.get_drawings()),
        )
        self._display_list_cache[page_index] = data
        return data
