from PySide6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QToolBar,
    QLabel,
    QWidget,
    QSizePolicy,
    QApplication,
    QComboBox,
    QMessageBox
)

from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from app.viewer.pdf_view import PDFView
from app.pdf.document import (
    PDFDocument,
    PDFOpenError,
    PDFSaveError
)
from app.pdf.renderer import PDFRenderer
from app.pdf.page_cache import PageCache



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

        self.cache = PageCache()


        self.current_page = 0


        self.view = PDFView()

        self.view.page_changed.connect(
            self.update_current_page
        )


        self.setCentralWidget(
            self.view
        )


        self.create_toolbar()



    def create_toolbar(self):

        toolbar = QToolBar()

        self.addToolBar(toolbar)

    #
    # 開く
    #
        open_action = QAction(
            "📂 開く",
            self
        )

        open_action.setToolTip(
            "PDFを開く"
        )

        open_action.triggered.connect(
            self.open_pdf
        )

        toolbar.addAction(
            open_action
        )

        toolbar.addSeparator()

    #
    # 回転
    #
        rotate_left_action = QAction(
            "↺",
            self
        )

        rotate_left_action.setToolTip(
            "クリック：現在ページを左90°回転\nShift+クリック：全ページを左90°回転"
        )

        rotate_left_action.triggered.connect(
            self.rotate_left
        )

        toolbar.addAction(
            rotate_left_action
        )

        rotate_right_action = QAction(
            "↻",
            self
        )

        rotate_right_action.triggered.connect(
            self.rotate_right
        )

        rotate_right_action.setToolTip(
            "クリック：現在ページを右90°回転\nShift+クリック：全ページを右90°回転"
        )


        toolbar.addAction(
            rotate_right_action
        )

        toolbar.addSeparator()

    #
    # ページ送り
    #
        self.prev_action = QAction(
            "◀",
            self
        )

        self.prev_action.setToolTip(
           "前のページ"
        )

        self.prev_action.triggered.connect(
            self.prev_page
        )

        toolbar.addAction(
            self.prev_action
        )

        self.next_action = QAction(
            "▶",
            self
        )

        self.next_action.setToolTip(
            "次のページ"
        )

        self.next_action.triggered.connect(
            self.next_page
        )

        toolbar.addAction(
            self.next_action
        )

        toolbar.addSeparator()

        self.page_label = QLabel(
            "0 / 0"
        )

        toolbar.addWidget(
            self.page_label
        )

    #
    # ここで右側へ寄せる
    #
        spacer = QWidget()

        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )

        toolbar.addWidget(
            spacer
        )

    #
    # 保存
    #
        save_action = QAction(
            "💾 保存",
            self
        )

        save_action.setToolTip(
            "保存 (Ctrl+S)"
        )

        save_action.setShortcut(
            "Ctrl+S"
        )

        save_action.triggered.connect(
            self.save_pdf
        )

        toolbar.addAction(
            save_action
        )

        save_as_action = QAction(
            "💾 名前を付けて保存",
            self
        )

        save_as_action.setToolTip(
            "名前を付けて保存 (Ctrl+Shift+S)"
        )

        save_as_action.setShortcut(
            "Ctrl+Shift+S"
        )

        save_as_action.triggered.connect(
            self.save_as_pdf
        )

        toolbar.addAction(
            save_as_action
        )

        self.view_mode = QComboBox()

        self.view_mode.addItems(
            [
                "1ページ表示",
                "連続表示"
            ]
        )

        self.view_mode.currentIndexChanged.connect(
            self.change_view_mode
        )

        toolbar.addWidget(
            self.view_mode
        )


        self.update_toolbar()



    def update_toolbar(self):

        has_pdf = self.document.has_document()


        self.prev_action.setEnabled(
            has_pdf
            and
            self.current_page > 0
        )


        self.next_action.setEnabled(
            has_pdf
            and
            self.current_page < self.document.page_count - 1
        )


        if has_pdf:

            self.page_label.setText(
                f"{self.current_page + 1} / {self.document.page_count}"
            )

        else:

            self.page_label.setText(
                "0 / 0"
            )



    def render_all_pages(self):

        pixmaps = []


        for i in range(
            self.document.page_count
        ):


            cached = self.cache.get(
                i
            )


            if cached:

                pixmaps.append(
                    cached
                )

                continue



            page = self.document.get_page(
                i
            )


            pixmap = self.renderer.render_page(
                page
            )


            self.cache.set(
                i,
                pixmap
            )


            pixmaps.append(
                pixmap
            )


        return pixmaps



    def show_document(self):

        pixmaps = self.render_all_pages()

        self.view.show_pages(
            pixmaps
        )

    #
    # 現在ページへ戻す
    #
        self.view.scroll_to_page(
            self.current_page
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



        try:
            self.document.open(path)
            self.cache.clear()
            self.current_page = 0
            self.show_document()
        except PDFOpenError as error:
            QMessageBox.critical(
                self,
                "PDFを開けません",
                str(error)
            )



    def next_page(self):

        if not self.document.has_document():

            return


        if self.current_page >= self.document.page_count - 1:

            return



        self.current_page += 1


        self.view.scroll_to_page(
            self.current_page
        )


        self.update_toolbar()



    def prev_page(self):

        if not self.document.has_document():

            return


        if self.current_page <= 0:

            return



        self.current_page -= 1


        self.view.scroll_to_page(
            self.current_page
        )


        self.update_toolbar()

       
    def update_current_page(self, page):

        if page == self.current_page:
            return

        self.current_page = page

        self.update_toolbar()

    def save_pdf(self):

        if not self.document.has_document():
            return

        try:
            self.document.save()
        except PDFSaveError as error:
            QMessageBox.critical(
                self,
                "PDFを保存できません",
                str(error)
            )


    def save_as_pdf(self):

        if not self.document.has_document():
            return


        path, _ = QFileDialog.getSaveFileName(
            self,
            "名前を付けて保存",
            "",
            "PDF (*.pdf)"
        )

        if not path:
          return

        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        try:
            self.document.save_as(path)
        except PDFSaveError as error:
            QMessageBox.critical(
                self,
                "PDFを保存できません",
                str(error)
            )

    def rotate_left(self):

        if not self.document.has_document():
            return

        modifiers = QApplication.keyboardModifiers()

        if modifiers & Qt.KeyboardModifier.ShiftModifier:

            self.document.rotate_all_pages(
                -90
            )

        else:

            self.document.rotate_page(
                self.current_page,
                -90
            )

        self.cache.clear()

        self.show_document()

    def rotate_right(self):

        if not self.document.has_document():
            return

        modifiers = QApplication.keyboardModifiers()

        if modifiers & Qt.KeyboardModifier.ShiftModifier:

            self.document.rotate_all_pages(
                90
            )

        else:

            self.document.rotate_page(
                self.current_page,
                90  
            )

        self.cache.clear()

        self.show_document()

    def closeEvent(self, event):

        self.document.close()
        event.accept()


    def change_view_mode(self,index):

        if index == 0:

            self.view.set_single_mode()

        else:

            self.view.set_continuous_mode()


        self.show_document()