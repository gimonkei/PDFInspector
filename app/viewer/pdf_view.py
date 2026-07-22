from PySide6.QtWidgets import (
    QLabel,
    QScrollArea
)


class PDFView(QScrollArea):


    def __init__(self):

        super().__init__()


        self.label = QLabel()

        self.label.setScaledContents(
            True
        )


        self.setWidget(
            self.label
        )


        self.setWidgetResizable(
            True
        )


    def show_pixmap(
        self,
        pixmap
    ):

        self.label.setPixmap(
            pixmap
        )