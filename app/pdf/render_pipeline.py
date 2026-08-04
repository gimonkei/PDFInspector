from dataclasses import dataclass
from time import perf_counter
import traceback

from PySide6.QtCore import (
    QObject,
    QRectF,
    QRunnable,
    QThreadPool,
    Signal,
    Slot,
)

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
    render_scale_override: float | None = None


@dataclass(frozen=True)
class RenderResult:
    """Result envelope returned by the render worker."""

    generation: int
    pages: tuple[RenderedPage, ...]
    elapsed_ms: float


class RenderWorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(int, str)


class RenderWorker(QRunnable):
    """Execute one render request outside the GUI thread."""

    def __init__(
        self,
        render_manager: RenderManager,
        document,
        request: RenderRequest,
    ):
        super().__init__()
        self.render_manager = render_manager
        self.document = document
        self.request = request
        self.signals = RenderWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        started = perf_counter()
        try:
            page_regions = {
                region.page_index: region.to_qrect()
                for region in self.request.regions
            }
            pages = self.render_manager.render_regions(
                self.document,
                page_regions,
                self.request.zoom_factor,
                self.request.device_pixel_ratio,
                render_scale_override=(
                    self.request.render_scale_override
                ),
            )
            result = RenderResult(
                generation=self.request.generation,
                pages=tuple(pages),
                elapsed_ms=(perf_counter() - started) * 1000.0,
            )
            self.signals.finished.emit(result)
        except Exception:
            self.signals.failed.emit(
                self.request.generation,
                traceback.format_exc(),
            )


class RenderPipeline(QObject):
    """
    Asynchronous request/result boundary around RenderManager.

    A single worker thread is used initially because the current DisplayList
    and tile cache are shared. This removes rendering work from the GUI thread
    without introducing concurrent cache mutations.
    """

    result_ready = Signal(object)
    render_failed = Signal(int, str)
    busy_changed = Signal(bool)

    def __init__(
        self,
        render_manager: RenderManager,
        parent=None,
    ):
        super().__init__(parent)
        self.render_manager = render_manager
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(1)

        self._generation = 0
        self._active_workers = 0
        self._pending_request = None
        self._pending_document = None
        self._closed = False

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def is_busy(self) -> bool:
        return self._active_workers > 0

    def invalidate(self) -> int:
        """Invalidate all requests created before this call."""
        self._generation += 1
        self._pending_request = None
        self._pending_document = None
        return self._generation

    def create_request(
        self,
        page_regions: dict[int, QRectF],
        zoom_factor: float,
        device_pixel_ratio: float = 1.0,
        render_scale_override=None,
    ) -> RenderRequest:
        generation = self.invalidate()
        regions = tuple(
            PageRenderRegion.from_qrect(
                page_index,
                rect,
            )
            for page_index, rect in sorted(
                page_regions.items()
            )
            if not rect.isEmpty()
        )

        override = None
        if render_scale_override is not None:
            override = max(
                float(render_scale_override),
                0.5,
            )

        return RenderRequest(
            generation=generation,
            regions=regions,
            zoom_factor=max(
                float(zoom_factor),
                0.01,
            ),
            device_pixel_ratio=max(
                float(device_pixel_ratio),
                1.0,
            ),
            render_scale_override=override,
        )


    def submit(self, document, request: RenderRequest):
        """
        Submit the newest request.

        While one render is running, only the most recent request is retained.
        This suppresses duplicate/stale scroll requests and prevents an
        unbounded QThreadPool queue.
        """
        if self._closed or not request.regions:
            return

        if self._active_workers > 0:
            self._pending_document = document
            self._pending_request = request
            return

        self._start_worker(document, request)

    def _start_worker(self, document, request: RenderRequest):
        worker = RenderWorker(
            self.render_manager,
            document,
            request,
        )
        worker.signals.finished.connect(self._on_worker_finished)
        worker.signals.failed.connect(self._on_worker_failed)

        self._active_workers += 1
        if self._active_workers == 1:
            self.busy_changed.emit(True)
        self.thread_pool.start(worker)

    @Slot(object)
    def _on_worker_finished(self, result: RenderResult):
        self._worker_completed()
        if self.is_current(result.generation):
            self.result_ready.emit(result)
        self._start_pending_request()

    @Slot(int, str)
    def _on_worker_failed(self, generation: int, details: str):
        self._worker_completed()
        if self.is_current(generation):
            self.render_failed.emit(generation, details)
        self._start_pending_request()

    def _worker_completed(self):
        self._active_workers = max(0, self._active_workers - 1)
        if self._active_workers == 0:
            self.busy_changed.emit(False)

    def _start_pending_request(self):
        if self._closed:
            self._pending_document = None
            self._pending_request = None
            return

        document = self._pending_document
        request = self._pending_request
        self._pending_document = None
        self._pending_request = None

        if (
            document is not None
            and request is not None
            and self.is_current(request.generation)
        ):
            self._start_worker(document, request)

    def is_current(self, generation: int) -> bool:
        return int(generation) == self._generation

    def shutdown(self):
        self._closed = True
        self.invalidate()
        self.thread_pool.clear()
        self.thread_pool.waitForDone()
