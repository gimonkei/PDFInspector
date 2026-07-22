from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsPixmapItem
)

from PySide6.QtGui import QPixmap
from app.viewer.graphics_view import GraphicsView



class PDFView(GraphicsView):


    def __init__(self):

        super().__init__()


        self.scene = QGraphicsScene()


        self.setScene(
            self.scene
        )


        self.pixmap_item = None



    def show_pixmap(
        self,
        pixmap: QPixmap
    ):


        self.scene.clear()


        self.pixmap_item = QGraphicsPixmapItem(
            pixmap
        )


        self.scene.addItem(
            self.pixmap_item
        )


        self.scene.setSceneRect(
            pixmap.rect()
        )


        self.resetTransform()


        self.zoom_factor = 1.0