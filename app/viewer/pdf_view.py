from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsPixmapItem
)

from PySide6.QtGui import QPixmap
from PySide6.QtCore import Signal

from app.viewer.graphics_view import GraphicsView



class PDFView(GraphicsView):


    page_changed = Signal(int)




    def __init__(self):

        super().__init__()


        self.scene = QGraphicsScene()

        self.setScene(
            self.scene
        )


        self.page_items = []

        self.page_positions = []


        self.verticalScrollBar().valueChanged.connect(
            self.on_scroll
        )



    def clear_pages(self):

        self.scene.clear()

        self.page_items.clear()

        self.page_positions.clear()



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


        self.page_items.append(
            item
        )


        rect = item.sceneBoundingRect()


        self.page_positions.append(
            {
                "page": page_index,
                "top": rect.top(),
                "bottom": rect.bottom()
            }
        )



    def show_pages(
        self,
        pages
    ):


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


        self.resetTransform()

        self.zoom_factor = 1.0



    def scroll_to_page(
        self,
        page_index
    ):


        if page_index < 0:

            return


        if page_index >= len(
            self.page_items
        ):

            return



        item = self.page_items[
            page_index
        ]


        self.ensureVisible(
            item,
            0,
            0
        )



    def get_visible_page(self):


        scene_point = self.mapToScene(
            self.viewport().rect().center()
        )


        y = scene_point.y()


        for page in self.page_positions:


            if (
                page["top"]
                <=
                y
                <=
                page["bottom"]
            ):

                return page["page"]


        return 0



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