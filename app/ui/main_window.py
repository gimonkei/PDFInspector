from PySide6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QToolBar
)

from PySide6.QtGui import QAction


from app.viewer.pdf_view import PDFView
from app.pdf.document import PDFDocument
from app.pdf.renderer import PDFRenderer



class MainWindow(QMainWindow):


    def __init__(self):

        super().__init__()


        self.setWindowTitle(
            "PDFInspector"
        )


        self.resize(
            1200,
            800
        )


        self.document = PDFDocument()

        self.renderer = PDFRenderer()


        self.view = PDFView()


        self.setCentralWidget(
            self.view
        )


        self.create_toolbar()



    def create_toolbar(self):

        toolbar = QToolBar()

        self.addToolBar(
            toolbar
        )


        open_action = QAction(
            "PDFを開く",
            self
        )


        open_action.triggered.connect(
            self.open_pdf
        )


        toolbar.addAction(
            open_action
        )



    def open_pdf(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "PDF選択",
            "",
            "PDF (*.pdf)"
        )


        if path:

            self.document.open(
                path
            )


            page = self.document.get_page(
                0
            )


            pixmap = self.renderer.render_page(
                page
            )


            self.view.show_pixmap(
                pixmap
            )