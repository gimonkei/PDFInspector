from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QToolBar,
    QWidget,
)

from app.pdf.document import PDFDocument, PDFOpenError, PDFSaveError
from app.pdf.page_cache import PageCache
from app.pdf.renderer import PDFRenderer
from app.viewer.pdf_view import PDFView


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
        self.view.page_changed.connect(self.update_current_page)
        self.view.zoom_changed.connect(self.update_zoom_display)
        self.setCentralWidget(self.view)

        self.create_toolbar()

    def create_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        open_action = QAction("📂 開く", self)
        open_action.setToolTip("PDFを開く")
        open_action.triggered.connect(self.open_pdf)
        toolbar.addAction(open_action)
        toolbar.addSeparator()

        rotate_left_action = QAction("↺", self)
        rotate_left_action.setToolTip("クリック：現在ページを左90°回転\nShift+クリック：全ページを左90°回転")
        rotate_left_action.triggered.connect(self.rotate_left)
        toolbar.addAction(rotate_left_action)

        rotate_right_action = QAction("↻", self)
        rotate_right_action.setToolTip("クリック：現在ページを右90°回転\nShift+クリック：全ページを右90°回転")
        rotate_right_action.triggered.connect(self.rotate_right)
        toolbar.addAction(rotate_right_action)
        toolbar.addSeparator()

        self.prev_action = QAction("◀", self)
        self.prev_action.setToolTip("前のページ")
        self.prev_action.triggered.connect(self.prev_page)
        toolbar.addAction(self.prev_action)

        self.next_action = QAction("▶", self)
        self.next_action.setToolTip("次のページ")
        self.next_action.triggered.connect(self.next_page)
        toolbar.addAction(self.next_action)

        self.page_label = QLabel("0 / 0")
        toolbar.addWidget(self.page_label)
        toolbar.addSeparator()

        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.setMinimumWidth(80)
        self.zoom_combo.addItems(["50%", "75%", "100%", "125%", "150%", "200%", "300%"])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setToolTip("ズーム倍率（10%～800%）")
        self.zoom_combo.activated.connect(self.change_zoom)
        self.zoom_combo.lineEdit().editingFinished.connect(self.apply_typed_zoom)
        toolbar.addWidget(self.zoom_combo)

        fit_width_action = QAction("幅に合わせる", self)
        fit_width_action.setToolTip(
            "PDFを表示領域の幅に合わせる (Ctrl+2)"
        )
        fit_width_action.setShortcut("Ctrl+2")
        fit_width_action.triggered.connect(self.fit_to_width)
        toolbar.addAction(fit_width_action)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        save_action = QAction("💾 保存", self)
        save_action.setToolTip("保存 (Ctrl+S)")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_pdf)
        toolbar.addAction(save_action)

        save_as_action = QAction("💾 名前を付けて保存", self)
        save_as_action.setToolTip("名前を付けて保存 (Ctrl+Shift+S)")
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_as_pdf)
        toolbar.addAction(save_as_action)

        self.view_mode = QComboBox()
        self.view_mode.addItems(["1ページ表示", "連続表示"])
        self.view_mode.currentIndexChanged.connect(self.change_view_mode)
        toolbar.addWidget(self.view_mode)

        self.update_toolbar()

    def update_toolbar(self):
        has_pdf = self.document.has_document()
        self.prev_action.setEnabled(has_pdf and self.current_page > 0)
        self.next_action.setEnabled(has_pdf and self.current_page < self.document.page_count - 1)
        self.page_label.setText(
            f"{self.current_page + 1} / {self.document.page_count}" if has_pdf else "0 / 0"
        )

    def render_all_pages(self):
        pixmaps = []
        for index in range(self.document.page_count):
            cached = self.cache.get(index)
            if cached:
                pixmaps.append(cached)
                continue
            page = self.document.get_page(index)
            pixmap = self.renderer.render_page(page)
            self.cache.set(index, pixmap)
            pixmaps.append(pixmap)
        return pixmaps

    def show_document(self):
        self.view.show_pages(self.render_all_pages())
        self.view.scroll_to_page(self.current_page)
        self.update_toolbar()

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "PDF選択", "", "PDF (*.pdf)")
        if not path:
            return
        try:
            self.document.open(path)
            self.cache.clear()
            self.current_page = 0
            self.show_document()
            self.view.fit_to_width()
        except PDFOpenError as error:
            QMessageBox.critical(self, "PDFを開けません", str(error))

    def next_page(self):
        if not self.document.has_document() or self.current_page >= self.document.page_count - 1:
            return
        self.current_page += 1
        self.view.scroll_to_page(self.current_page)
        self.update_toolbar()

    def prev_page(self):
        if not self.document.has_document() or self.current_page <= 0:
            return
        self.current_page -= 1
        self.view.scroll_to_page(self.current_page)
        self.update_toolbar()

    def update_current_page(self, page):
        if page != self.current_page:
            self.current_page = page
            self.update_toolbar()

    def change_zoom(self, index):
        self.apply_zoom_text(self.zoom_combo.itemText(index))

    def apply_typed_zoom(self):
        self.apply_zoom_text(self.zoom_combo.currentText())

    def apply_zoom_text(self, text):
        value = text.strip().replace("%", "")
        try:
            percent = float(value)
        except ValueError:
            self.update_zoom_display(self.view.zoom_factor)
            return
        percent = max(10.0, min(percent, 800.0))
        self.view.set_zoom(percent / 100.0)

    def update_zoom_display(self, zoom_factor):
        percent = round(zoom_factor * 100)
        self.zoom_combo.blockSignals(True)
        self.zoom_combo.setCurrentText(f"{percent}%")
        self.zoom_combo.blockSignals(False)

    def fit_to_width(self):
        if not self.document.has_document():
            return

        if not self.view.fit_to_width():
            QMessageBox.information(
                self,
                "幅に合わせる",
                "表示できるPDFページがありません。",
            )

    def save_pdf(self):
        if not self.document.has_document():
            return
        try:
            self.document.save()
        except PDFSaveError as error:
            QMessageBox.critical(self, "PDFを保存できません", str(error))

    def save_as_pdf(self):
        if not self.document.has_document():
            return
        path, _ = QFileDialog.getSaveFileName(self, "名前を付けて保存", "", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            self.document.save_as(path)
        except PDFSaveError as error:
            QMessageBox.critical(self, "PDFを保存できません", str(error))

    def rotate_left(self):
        if not self.document.has_document():
            return
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.document.rotate_all_pages(-90)
        else:
            self.document.rotate_page(self.current_page, -90)
        self.cache.clear()
        self.show_document()
        self.view.fit_to_width()

    def rotate_right(self):
        if not self.document.has_document():
            return
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.document.rotate_all_pages(90)
        else:
            self.document.rotate_page(self.current_page, 90)
        self.cache.clear()
        self.show_document()
        self.view.fit_to_width()

    def change_view_mode(self, index):
        if index == 0:
            self.view.set_single_mode()
        else:
            self.view.set_continuous_mode()
        if self.document.has_document():
            self.view.scroll_to_page(self.current_page)

    def closeEvent(self, event):
        self.document.close()
        event.accept()
