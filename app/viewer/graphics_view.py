from PySide6.QtWidgets import QGraphicsView
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QWheelEvent, QMouseEvent


class GraphicsView(QGraphicsView):


    def __init__(self):

        super().__init__()


        self.zoom_factor = 1.0


        self._dragging = False

        self._last_mouse_pos = QPoint()



        self.setTransformationAnchor(
            QGraphicsView.AnchorUnderMouse
        )

        self.setResizeAnchor(
            QGraphicsView.AnchorUnderMouse
        )


        self.setDragMode(
            QGraphicsView.NoDrag
        )


        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )


        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )



    # -------------------------
    # マウスドラッグ
    # -------------------------

    def mousePressEvent(
        self,
        event: QMouseEvent
    ):


        if event.button() == Qt.LeftButton:

            self._dragging = True

            self._last_mouse_pos = (
                event.position()
                .toPoint()
            )


            self.setCursor(
                Qt.ClosedHandCursor
            )


            event.accept()

            return


        super().mousePressEvent(
            event
        )



    def mouseMoveEvent(
        self,
        event: QMouseEvent
    ):


        if self._dragging:


            current = (
                event.position()
                .toPoint()
            )


            delta = (
                current
                -
                self._last_mouse_pos
            )


            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value()
                -
                delta.x()
            )


            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value()
                -
                delta.y()
            )


            self._last_mouse_pos = current


            event.accept()

            return


        super().mouseMoveEvent(
            event
        )



    def mouseReleaseEvent(
        self,
        event: QMouseEvent
    ):


        if event.button() == Qt.LeftButton:


            self._dragging = False


            self.setCursor(
                Qt.ArrowCursor
            )


            event.accept()

            return


        super().mouseReleaseEvent(
            event
        )



    # -------------------------
    # ホイール操作
    # -------------------------

    def wheelEvent(
        self,
        event: QWheelEvent
    ):


        delta = event.angleDelta().y()


        # Ctrl + ホイール = ズーム

        if (
            event.modifiers()
            &
            Qt.ControlModifier
        ):


            if delta > 0:

                factor = 1.15

            else:

                factor = 0.85



            new_zoom = (
                self.zoom_factor
                *
                factor
            )


            if 0.1 <= new_zoom <= 8.0:


                self.scale(
                    factor,
                    factor
                )


                self.zoom_factor = new_zoom


            event.accept()

            return



        # Shift + ホイール = 横移動

        if (
            event.modifiers()
            &
            Qt.ShiftModifier
        ):


            value = (
                self.horizontalScrollBar()
                .value()
            )


            self.horizontalScrollBar().setValue(
                value
                -
                delta
            )


            event.accept()

            return



        # 通常ホイール = 縦移動

        value = (
            self.verticalScrollBar()
            .value()
        )


        self.verticalScrollBar().setValue(
            value
            -
            delta
        )


        event.accept()