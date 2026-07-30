from dataclasses import dataclass
from time import perf_counter

from PySide6.QtCore import QRectF

from app.pdf.render_manager import RenderedPage, RenderManager


@dataclass(frozen=True)
class PageRenderRegion:
    """Immutable page-local region used by the render pipeline."""

    page_index: int
    x: float
    y: float
    width: float
    height: float

    @classmethod
    def from_qrect(
        cls,
        page_index: int,
        rect: QRectF,
    ) -> "PageRenderRegion":
        return cls(
            page_index=int(page_index),
            x=float(rect.x()),
            y=float(rect.y()),
            width=float(rect.width()),
            height=float(rect.height()),
        )

    def to_qrect(self) -> QRectF:
        return QRectF(
            self.x,
            self.y,
            self.width,
            self.height,
        )


@dataclass(frozen=True)
class RenderRequest:
    """Immutable description of one visible-tile render pass."""

    generation: int
    regions: tuple[PageRenderRegion, ...]
    zoom_factor: float
    device_pixel_ratio: float


@dataclass(frozen=True)
class RenderResult:
    """Result envelope returned by the render pipeline."""

    generation: int
    pages: tuple[RenderedPage, ...]
    elapsed_ms: float


class RenderPipeline:
    """
    Request/result boundary around RenderManager.

    Task014 Phase3-1 intentionally remains synchronous. The immutable
    request/result objects and generation checks form the boundary needed
    to move execute() to QThreadPool safely in Phase3-2.
    """

    def __init__(self, render_manager: RenderManager):
        self.render_manager = render_manager
        self._generation = 0

    @property
    def generation(self) -> int:
        return self._generation

    def invalidate(self) -> int:
        """Invalidate all requests created before this call."""
        self._generation += 1
        return self._generation

    def create_request(
        self,
        page_regions: dict[int, QRectF],
        zoom_factor: float,
        device_pixel_ratio: float = 1.0,
    ) -> RenderRequest:
        generation = self.invalidate()
        regions = tuple(
            PageRenderRegion.from_qrect(page_index, rect)
            for page_index, rect in sorted(page_regions.items())
            if not rect.isEmpty()
        )
        return RenderRequest(
            generation=generation,
            regions=regions,
            zoom_factor=max(float(zoom_factor), 0.01),
            device_pixel_ratio=max(float(device_pixel_ratio), 1.0),
        )

    def execute(
        self,
        document,
        request: RenderRequest,
    ) -> RenderResult:
        started = perf_counter()
        page_regions = {
            region.page_index: region.to_qrect()
            for region in request.regions
        }
        pages = self.render_manager.render_regions(
            document,
            page_regions,
            request.zoom_factor,
            request.device_pixel_ratio,
        )
        return RenderResult(
            generation=request.generation,
            pages=tuple(pages),
            elapsed_ms=(perf_counter() - started) * 1000.0,
        )

    def is_current(self, generation: int) -> bool:
        return int(generation) == self._generation
