from PySide6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtCore import Signal

from app.viewer.graphics_view import GraphicsView
from app.viewer.page_manager import PageManager


class PDFView(GraphicsView):
    page_changed = Signal(int)

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.page_manager = PageManager()
        self.pages = []
        self.current_page_index = 0
        self.single_page_mode = True
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)

    def clear_pages(self):
        self.scene.clear()
        self.page_manager.clear()

    def add_page(self, rendered_page, page_index: int, y_position: float):
        item = QGraphicsPixmapItem(rendered_page.pixmap)
        inverse_scale = 1.0 / rendered_page.render_scale if rendered_page.render_scale > 0 else 1.0
        item.setScale(inverse_scale)
        item.setPos(0, y_position)
        self.scene.addItem(item)
        rect = item.sceneBoundingRect()
        self.page_manager.add_page(
            page_index,
            rendered_page.pixmap,
            item,
            rect.top(),
            rect.bottom(),
        )

    def show_pages(self, pages):
        self.pages = list(pages)
        if not self.pages:
            self.clear_pages()
            return

        self.current_page_index = min(self.current_page_index, len(self.pages) - 1)
        if self.single_page_mode:
            self._show_single_page(self.current_page_index)
        else:
            self._show_continuous_pages()

    def refresh_pages(self, pages):
        center = self.mapToScene(self.viewport().rect().center())
        page_index = self.current_page_index
        self.show_pages(pages)
        self.current_page_index = min(page_index, max(0, len(self.pages) - 1))
        self.centerOn(center)

    def set_single_mode(self):
        self.single_page_mode = True
        if self.pages:
            self._show_single_page(self.current_page_index)

    def set_continuous_mode(self):
        self.single_page_mode = False
        if self.pages:
            self._show_continuous_pages()
            self.scroll_to_page(self.current_page_index)

    def _show_single_page(self, page_index):
        if page_index < 0 or page_index >= len(self.pages):
            return

        current_zoom = self.zoom_factor
        self.clear_pages()
        self.current_page_index = page_index
        self.add_page(self.pages[page_index], page_index, 0)
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self._restore_zoom(current_zoom)

    def _show_continuous_pages(self):
        current_zoom = self.zoom_factor
        self.clear_pages()
        y = 0.0
        margin = 20.0

        for index, rendered_page in enumerate(self.pages):
            self.add_page(rendered_page, index, y)
            y += rendered_page.scene_height + margin

        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self._restore_zoom(current_zoom)

    def _restore_zoom(self, zoom):
        self.resetTransform()
        self.scale(zoom, zoom)
        self.zoom_factor = zoom

    def scroll_to_page(self, page_index):
        if page_index < 0 or page_index >= len(self.pages):
            return

        self.current_page_index = page_index
        if self.single_page_mode:
            self._show_single_page(page_index)
            return

        for page in self.page_manager.pages:
            if page.page == page_index:
                self.verticalScrollBar().setValue(int(page.top * self.zoom_factor))
                return

    def get_visible_page(self):
        if self.single_page_mode:
            return self.current_page_index

        point = self.mapToScene(self.viewport().rect().topLeft())
        y = point.y() + (
            self.viewport().height() / max(self.zoom_factor, 0.01) * 0.2
        )
        return self.page_manager.visible_page(y)

    def on_scroll(self):
        if self.single_page_mode:
            return
        page = self.get_visible_page()
        self.current_page_index = page
        self.page_changed.emit(page)

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.on_scroll()
