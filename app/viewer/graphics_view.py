from PySide6.QtWidgets import QGraphicsView
from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent, QMouseEvent


class GraphicsView(QGraphicsView):

    def __init__(self):

        super().__init__()


        # ズーム倍率
        self.zoom_factor = 1.0


        # ドラッグ移動用
        self.dragging = False
        self.last_mouse_pos = None


        self.setDragMode(
            QGraphicsView.NoDrag
        )


        # アンチエイリアス
        self.setRenderHints(
            self.renderHints()
        )


    def wheelEvent(
        self,
        event: QWheelEvent
    ):

        # Ctrl押下時のみズーム
        if event.modifiers() & Qt.ControlModifier:

            delta = event.angleDelta().y()


            if delta > 0:
                factor = 1.15

            else:
                factor = 0.85


            self.zoom_factor *= factor


            self.scale(
                factor,
                factor
            )


            event.accept()

        else:

            # 通常スクロール
            super().wheelEvent(
                event
            )


    def mousePressEvent(
        self,
        event: QMouseEvent
    ):

        if event.button() == Qt.MiddleButton:

            self.dragging = True

            self.last_mouse_pos = event.position()

            self.setCursor(
                Qt.ClosedHandCursor
            )

            event.accept()

        else:

            super().mousePressEvent(
                event
            )


    def mouseMoveEvent(
        self,
        event: QMouseEvent
    ):

        if self.dragging:

            delta = (
                event.position()
                -
                self.last_mouse_pos
            )


            self.last_mouse_pos = event.position()


            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value()
                -
                int(delta.x())
            )


            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value()
                -
                int(delta.y())
            )


            event.accept()

        else:

            super().mouseMoveEvent(
                event
            )


    def mouseReleaseEvent(
        self,
        event: QMouseEvent
    ):

        if event.button() == Qt.MiddleButton:

            self.dragging = False

            self.setCursor(
                Qt.ArrowCursor
            )

            event.accept()

        else:

            super().mouseReleaseEvent(
                event
            )