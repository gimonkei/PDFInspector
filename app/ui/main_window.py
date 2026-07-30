from PySide6.QtCore import Qt, QTimer
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
from app.pdf.render_pipeline import RenderPipeline
from app.pdf.render_manager import RenderManager
from app.pdf.renderer import PDFRenderer
from app.viewer.pdf_view import PDFView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDFInspector")
        self.resize(1200, 800)

        self.document = PDFDocument()
        self.renderer = PDFRenderer()
        self.render_manager = RenderManager(self.renderer)
        self.render_pipeline = RenderPipeline(self.render_manager)
        self.current_page = 0

        self.view = PDFView()
        self.view.page_changed.connect(self.update_current_page)
        self.view.zoom_changed.connect(self.on_zoom_changed)
        self.view.visible_region_changed.connect(
            self.schedule_visible_tile_render
        )
        self.setCentralWidget(self.view)

        # Wait until zooming settles before switching render resolution.
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.setInterval(180)
        self.render_timer.timeout.connect(self.rerender_for_current_zoom)

        # Scrolling receives a shorter debounce and renders only nearby tiles.
        self.visible_tile_timer = QTimer(self)
        self.visible_tile_timer.setSingleShot(True)
        self.visible_tile_timer.setInterval(55)
        self.visible_tile_timer.timeout.connect(self.render_visible_tiles)

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
        rotate_left_action.setToolTip(
            "クリック：現在ページを左90°回転\n"
            "Shift+クリック：全ページを左90°回転"
        )
        rotate_left_action.triggered.connect(self.rotate_left)
        toolbar.addAction(rotate_left_action)

        rotate_right_action = QAction("↻", self)
        rotate_right_action.setToolTip(
            "クリック：現在ページを右90°回転\n"
            "Shift+クリック：全ページを右90°回転"
        )
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
        self.zoom_combo.addItems(
            ["50%", "75%", "100%", "125%", "150%", "200%", "300%"]
        )
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setToolTip("ズーム倍率（10%～800%）")
        self.zoom_combo.activated.connect(self.change_zoom)
        self.zoom_combo.lineEdit().editingFinished.connect(
            self.apply_typed_zoom
        )
        toolbar.addWidget(self.zoom_combo)

        fit_width_action = QAction("幅に合わせる", self)
        fit_width_action.setToolTip(
            "PDFを表示領域の幅に合わせる (Ctrl+2)"
        )
        fit_width_action.setShortcut("Ctrl+2")
        fit_width_action.triggered.connect(self.fit_to_width)
        toolbar.addAction(fit_width_action)

        self.render_scale_label = QLabel(
            " 描画: 2.00x / PIPELINE / 細線ON "
        )
        self.render_scale_label.setToolTip(
            "描画要求をパイプライン経由で処理します"
        )
        toolbar.addWidget(self.render_scale_label)

        self.hairline_action = QAction("細線強調", self)
        self.hairline_action.setCheckable(True)
        self.hairline_action.setChecked(True)
        self.hairline_action.setToolTip(
            "低倍率時に細い線を画面表示だけ強調します。"
            "PDFデータは変更しません。"
        )
        self.hairline_action.toggled.connect(self.toggle_hairline)
        toolbar.addAction(self.hairline_action)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        toolbar.addWidget(spacer)

        save_action = QAction("💾 保存", self)
        save_action.setToolTip("保存 (Ctrl+S)")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_pdf)
        toolbar.addAction(save_action)

        save_as_action = QAction("💾 名前を付けて保存", self)
        save_as_action.setToolTip(
            "名前を付けて保存 (Ctrl+Shift+S)"
        )
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_as_pdf)
        toolbar.addAction(save_as_action)

        self.view_mode = QComboBox()
        self.view_mode.addItems(["1ページ表示", "連続表示"])
        self.view_mode.currentIndexChanged.connect(
            self.change_view_mode
        )
        toolbar.addWidget(self.view_mode)

        self.update_toolbar()

    def update_toolbar(self):
        has_pdf = self.document.has_document()
        self.prev_action.setEnabled(
            has_pdf and self.current_page > 0
        )
        self.next_action.setEnabled(
            has_pdf
            and self.current_page < self.document.page_count - 1
        )
        self.page_label.setText(
            f"{self.current_page + 1} / {self.document.page_count}"
            if has_pdf
            else "0 / 0"
        )

    def _device_pixel_ratio(self):
        return max(float(self.view.devicePixelRatioF()), 1.0)

    def update_render_label(self):
        scale = self.render_manager.target_scale(
            self.view.zoom_factor,
            self._device_pixel_ratio(),
        )
        state = (
            "ON"
            if self.render_manager.hairline_enabled
            else "OFF"
        )
        cache_count = self.render_manager.tile_cache_count()
        self.render_scale_label.setText(
            f" 描画: {scale:.2f}x / PIPELINE "
            f"/ 細線{state} / cache {cache_count} "
        )

    def show_document(self):
        layouts = self.render_manager.get_page_layouts(
            self.document
        )
        self.view.show_pages(layouts)
        self.view.scroll_to_page(self.current_page)
        self.update_toolbar()
        self.update_render_label()
        self.schedule_visible_tile_render()

    def schedule_visible_tile_render(self):
        if self.document.has_document():
            self.visible_tile_timer.start()

    def render_visible_tiles(self):
        if not self.document.has_document():
            return

        page_regions = self.view.visible_page_regions()
        if not page_regions:
            return

        request = self.render_pipeline.create_request(
            page_regions,
            self.view.zoom_factor,
            self._device_pixel_ratio(),
        )
        result = self.render_pipeline.execute(
            self.document,
            request,
        )

        if not self.render_pipeline.is_current(result.generation):
            return

        self.view.apply_rendered_pages(result.pages)
        self.update_render_label()

    def rerender_for_current_zoom(self):
        if not self.document.has_document():
            return
        self.render_pipeline.invalidate()
        self.view.clear_rendered_tiles()
        self.update_render_label()
        self.schedule_visible_tile_render()

    def on_zoom_changed(self, zoom_factor):
        self.update_zoom_display(zoom_factor)
        self.update_render_label()
        if self.document.has_document():
            self.render_timer.start()

    def toggle_hairline(self, enabled):
        self.render_pipeline.invalidate()
        self.render_manager.set_hairline_enabled(enabled)
        if self.document.has_document():
            self.view.clear_rendered_tiles()
            self.update_render_label()
            self.schedule_visible_tile_render()

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "PDF選択",
            "",
            "PDF (*.pdf)",
        )
        if not path:
            return
        try:
            self.document.open(path)
            self.render_pipeline.invalidate()
            self.render_manager.clear()
            self.render_manager.prepare_document(self.document)
            self.current_page = 0
            self.show_document()
            self.view.fit_to_width()
        except PDFOpenError as error:
            QMessageBox.critical(
                self,
                "PDFを開けません",
                str(error),
            )

    def next_page(self):
        if (
            not self.document.has_document()
            or self.current_page
            >= self.document.page_count - 1
        ):
            return
        self.current_page += 1
        self.view.scroll_to_page(self.current_page)
        self.update_toolbar()
        self.schedule_visible_tile_render()

    def prev_page(self):
        if (
            not self.document.has_document()
            or self.current_page <= 0
        ):
            return
        self.current_page -= 1
        self.view.scroll_to_page(self.current_page)
        self.update_toolbar()
        self.schedule_visible_tile_render()

    def update_current_page(self, page):
        if page != self.current_page:
            self.current_page = page
            self.update_toolbar()

    def change_zoom(self, index):
        self.apply_zoom_text(
            self.zoom_combo.itemText(index)
        )

    def apply_typed_zoom(self):
        self.apply_zoom_text(
            self.zoom_combo.currentText()
        )

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
            QMessageBox.critical(
                self,
                "PDFを保存できません",
                str(error),
            )

    def save_as_pdf(self):
        if not self.document.has_document():
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "名前を付けて保存",
            "",
            "PDF (*.pdf)",
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
                str(error),
            )

    def rotate_left(self):
        if not self.document.has_document():
            return
        if (
            QApplication.keyboardModifiers()
            & Qt.KeyboardModifier.ShiftModifier
        ):
            self.document.rotate_all_pages(-90)
        else:
            self.document.rotate_page(
                self.current_page,
                -90,
            )
        self.render_pipeline.invalidate()
        self.render_manager.clear()
        self.render_manager.prepare_document(self.document)
        self.show_document()
        self.view.fit_to_width()

    def rotate_right(self):
        if not self.document.has_document():
            return
        if (
            QApplication.keyboardModifiers()
            & Qt.KeyboardModifier.ShiftModifier
        ):
            self.document.rotate_all_pages(90)
        else:
            self.document.rotate_page(
                self.current_page,
                90,
            )
        self.render_pipeline.invalidate()
        self.render_manager.clear()
        self.render_manager.prepare_document(self.document)
        self.show_document()
        self.view.fit_to_width()

    def change_view_mode(self, index):
        if index == 0:
            self.view.set_single_mode()
        else:
            self.view.set_continuous_mode()
        if self.document.has_document():
            self.render_pipeline.invalidate()
            self.view.scroll_to_page(self.current_page)
            self.schedule_visible_tile_render()

    def closeEvent(self, event):
        self.render_timer.stop()
        self.visible_tile_timer.stop()
        self.render_pipeline.invalidate()
        self.document.close()
        event.accept()
