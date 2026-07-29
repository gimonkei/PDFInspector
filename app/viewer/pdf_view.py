from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsPixmapItem
)

from PySide6.QtGui import QPixmap
from PySide6.QtCore import Signal

from app.viewer.graphics_view import GraphicsView
from app.viewer.page_manager import PageManager


class PDFView(GraphicsView):

    page_changed = Signal(int)

    def __init__(self):

        super().__init__()

        self.scene = QGraphicsScene()

        self.setScene(
            self.scene
        )

        self.page_manager = PageManager()

        self.pages = []

        self.current_page_index = 0

        self.single_page_mode = True

        self.verticalScrollBar().valueChanged.connect(
            self.on_scroll
        )

    def clear_pages(self):

        self.scene.clear()

        self.page_manager.clear()

    def add_page(
        self,
        pixmap: QPixmap,
        page_index: int,
        y_position: int
    ):

        item = QGraphicsPixmapItem(
            pixmap
        )

        item.setPos(
            0,
            y_position
        )

        self.scene.addItem(
            item
        )

        rect = item.sceneBoundingRect()

        self.page_manager.add_page(
            page_index,
            pixmap,
            item,
            rect.top(),
            rect.bottom()
        )

    def show_pages(
        self,
        pages
    ):

        self.pages = list(pages)

        if not self.pages:

            self.clear_pages()

            return

        self.current_page_index = min(
            self.current_page_index,
            len(self.pages) - 1
        )

        if self.single_page_mode:

            self._show_single_page(
                self.current_page_index
            )

        else:

            self._show_continuous_pages()

    def set_single_mode(self):

        self.single_page_mode = True

        if self.pages:

            self._show_single_page(
                self.current_page_index
            )

    def set_continuous_mode(self):

        self.single_page_mode = False

        if self.pages:

            self._show_continuous_pages()

            self.scroll_to_page(
                self.current_page_index
            )

    def _show_single_page(
        self,
        page_index
    ):

        if (
            page_index < 0
            or
            page_index >= len(self.pages)
        ):

            return

        current_zoom = self.zoom_factor

        self.clear_pages()

        self.current_page_index = page_index

        self.add_page(
            self.pages[page_index],
            page_index,
            0
        )

        self.scene.setSceneRect(
            self.scene.itemsBoundingRect()
        )

        self._restore_zoom(
            current_zoom
        )

    def _show_continuous_pages(self):

        current_zoom = self.zoom_factor

        self.clear_pages()

        y = 0

        margin = 20

        for index, pixmap in enumerate(self.pages):

            self.add_page(
                pixmap,
                index,
                y
            )

            y += pixmap.height()

            y += margin

        self.scene.setSceneRect(
            self.scene.itemsBoundingRect()
        )

        self._restore_zoom(
            current_zoom
        )

    def _restore_zoom(
        self,
        zoom
    ):

        self.resetTransform()

        self.scale(
            zoom,
            zoom
        )

        self.zoom_factor = zoom

    def scroll_to_page(
        self,
        page_index
    ):

        if (
            page_index < 0
            or
            page_index >= len(self.pages)
        ):

            return

        self.current_page_index = page_index

        if self.single_page_mode:

            self._show_single_page(
                page_index
            )

            return

        for page in self.page_manager.pages:

            if page.page == page_index:

                self.verticalScrollBar().setValue(
                    int(page.top)
                )

                return

    def get_visible_page(self):

        if self.single_page_mode:

            return self.current_page_index

        point = self.mapToScene(
            self.viewport().rect().topLeft()
        )

        y = point.y() + (
            self.viewport().height() * 0.2
        )

        return self.page_manager.visible_page(
            y
        )

    def on_scroll(self):

        if self.single_page_mode:

            return

        page = self.get_visible_page()

        self.current_page_index = page

        self.page_changed.emit(
            page
        )

    def scrollContentsBy(
        self,
        dx,
        dy
    ):

        super().scrollContentsBy(
            dx,
            dy
        )

        self.on_scroll()
