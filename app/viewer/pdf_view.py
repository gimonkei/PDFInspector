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

    #
    # 現在のズーム倍率を保存
    #
        current_zoom = self.zoom_factor

    #
    # ページを作り直す
    #
        self.clear_pages()

        y = 0

        margin = 20

        for index, pixmap in enumerate(pages):

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

    #
    # ズームを復元
    #
        self.resetTransform()

        self.scale(
            current_zoom,
            current_zoom
        )

        self.zoom_factor = current_zoom


    def scroll_to_page(
        self,
        page_index
    ):

        page = self.page_manager.get(
            page_index
        )

        if page is None:
            return

        self.verticalScrollBar().setValue(
            int(page.top)
        )



    def get_visible_page(self):

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


        page = self.get_visible_page()


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