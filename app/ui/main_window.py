from PySide6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QToolBar,
    QLabel
)

from PySide6.QtGui import QAction

from app.viewer.pdf_view import PDFView
from app.pdf.document import PDFDocument
from app.pdf.renderer import PDFRenderer
from app.pdf.page_cache import PageCache


class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("PDFInspector")
        self.resize(1200, 800)

        self.document = PDFDocument()
        self.renderer = PDFRenderer()
        self.cache = PageCache()

        self.current_page = 0

        self.view = PDFView()
        self.setCentralWidget(self.view)

        self.create_toolbar()

    def create_toolbar(self):

        toolbar = QToolBar()
        self.addToolBar(toolbar)

        open_action = QAction("PDFを開く", self)
        open_action.triggered.connect(self.open_pdf)
        toolbar.addAction(open_action)

        toolbar.addSeparator()

        self.prev_action = QAction("◀", self)
        self.prev_action.triggered.connect(self.prev_page)
        toolbar.addAction(self.prev_action)

        self.next_action = QAction("▶", self)
        self.next_action.triggered.connect(self.next_page)
        toolbar.addAction(self.next_action)

        toolbar.addSeparator()

        self.page_label = QLabel("0 / 0")
        toolbar.addWidget(self.page_label)

        self.update_toolbar()

    def update_toolbar(self):

        has_pdf = self.document.has_document()

        self.prev_action.setEnabled(
            has_pdf and self.current_page > 0
        )

        self.next_action.setEnabled(
            has_pdf and self.current_page < self.document.page_count - 1
        )

        if has_pdf:
            self.page_label.setText(
                f"{self.current_page + 1} / {self.document.page_count}"
            )
        else:
            self.page_label.setText("0 / 0")

    def show_page(self):

        pixmap = self.cache.get(
            self.current_page
        )


        if pixmap is None:

                page = self.document.get_page(
                self.current_page
                )


                pixmap = self.renderer.render_page(
                   page
                )


                self.cache.set(
                self.current_page,
                pixmap
           )


        self.view.show_pixmap(
          pixmap
        )


        self.update_toolbar()

    def open_pdf(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "PDF選択",
            "",
            "PDF (*.pdf)"
        )

        if not path:
            return

        self.document.open(path)

        self.cache.clear()

        self.current_page = 0

        self.show_page()

    def next_page(self):

        if self.current_page >= self.document.page_count - 1:
            return

        self.current_page += 1

        self.show_page()

    def prev_page(self):

        if self.current_page <= 0:
            return

        self.current_page -= 1

        self.show_page()