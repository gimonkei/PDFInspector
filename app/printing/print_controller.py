from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.printing.print_engine import PrintEngine
from app.printing.hybrid_print_exporter import (
    HybridPrintExporter,
)
from app.printing.vector_print_exporter import (
    VectorPrintExporter,
)
from app.printing.adobe_print_bridge import (
    AdobePrintBridge,
)
from app.printing.print_options import PrintOptionsDialog


class PrintController:
    def __init__(
        self,
        parent,
        document,
        annotations,
        current_page: int,
    ):
        self.parent = parent
        self.document = document
        self.annotations = annotations
        self.current_page = int(current_page)

    def run(self) -> None:
        options_dialog = PrintOptionsDialog(
            self.parent,
            self.document.page_count,
            self.current_page,
        )
        if (
            options_dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        options = options_dialog.values()

        try:
            page_indexes = self._resolve_pages(options)
        except (TypeError, ValueError) as error:
            QMessageBox.warning(
                self.parent,
                "ページ範囲",
                str(error),
            )
            return

        if not page_indexes:
            return

        if options.print_mode == "adobe_dialog":
            self._open_adobe_print_dialog(
                page_indexes,
                options,
            )
            return

        if options.print_mode == "adobe_direct":
            self._direct_vector_print(
                page_indexes,
                options,
            )
            return

        if options.print_mode == "vector_open":
            self._open_vector_print_pdf(
                page_indexes,
                options,
            )
            return

        # The legacy direct QPrinter path used a second annotation
        # renderer, which caused checks, clouds, date stamps and text to
        # differ from the saved / on-screen appearance. Generate one
        # finalized appearance PDF and print that instead.
        self._open_adobe_print_dialog(
            page_indexes,
            options,
        )
        return

    def _open_adobe_print_dialog(
        self,
        page_indexes,
        options,
    ):
        QApplication.setOverrideCursor(
            Qt.CursorShape.WaitCursor
        )
        try:
            output_path = HybridPrintExporter(
                self.document,
                self.annotations,
            ).create_print_pdf(
                page_indexes,
                include_annotations=(
                    options.print_annotations
                ),
            )

            result = AdobePrintBridge().open_print_dialog(
                output_path
            )
        except Exception as error:
            QMessageBox.critical(
                self.parent,
                "Adobe印刷画面エラー",
                "印刷専用PDFの作成またはAdobeの起動に失敗しました。\n"
                f"{error}",
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

        if result.started:
            return

        opened = VectorPrintExporter.open_in_default_viewer(
            output_path
        )

        if opened:
            QMessageBox.warning(
                self.parent,
                "Adobeが見つかりません",
                (
                    "Adobe Acrobat／Readerの印刷画面を"
                    "起動できなかったため、印刷用PDFを開きました。\n\n"
                    "開いたアプリでCtrl＋Pを押してください。"
                ),
            )
        else:
            QMessageBox.warning(
                self.parent,
                "Adobeを起動できません",
                (
                    "Adobe Acrobat／Readerを検出できませんでした。\n"
                    f"印刷用PDF:\n{output_path}"
                ),
            )

    def _direct_vector_print(
        self,
        page_indexes,
        options,
    ):
        printer = QPrinter(
            QPrinter.PrinterMode.HighResolution
        )
        printer.setDocName(
            Path(
                self.document.path
                or "PDFInspector"
            ).name
        )

        printer_dialog = QPrintDialog(
            printer,
            self.parent,
        )
        printer_dialog.setWindowTitle(
            "印刷先プリンターを選択"
        )

        if (
            printer_dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        printer_name = str(
            printer.printerName()
        ).strip()
        if not printer_name:
            QMessageBox.warning(
                self.parent,
                "プリンター",
                "プリンターが選択されていません。",
            )
            return

        QApplication.setOverrideCursor(
            Qt.CursorShape.WaitCursor
        )
        try:
            output_path = HybridPrintExporter(
                self.document,
                self.annotations,
            ).create_print_pdf(
                page_indexes,
                include_annotations=(
                    options.print_annotations
                ),
            )

            bridge = AdobePrintBridge()
            result = bridge.print_pdf(
                output_path,
                printer_name,
            )
        except Exception as error:
            QMessageBox.critical(
                self.parent,
                "直接印刷エラー",
                "印刷専用PDFの作成または送信に失敗しました。\n"
                f"{error}",
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

        if result.started:
            QMessageBox.information(
                self.parent,
                "印刷を送信しました",
                (
                    f"「{printer_name}」へ印刷データを送信しました。\n\n"
                    "Adobeの処理状況やプリンターのキューを"
                    "確認してください。"
                ),
            )
            return

        opened = VectorPrintExporter.open_in_default_viewer(
            output_path
        )

        if opened:
            QMessageBox.warning(
                self.parent,
                "Adobeが見つかりません",
                (
                    "Adobe Acrobat／Readerの直接印刷機能を"
                    "利用できなかったため、印刷用PDFを開きました。\n\n"
                    "開いたアプリでCtrl＋Pを押してください。"
                ),
            )
        else:
            QMessageBox.warning(
                self.parent,
                "直接印刷できません",
                (
                    "Adobe Acrobat／Readerが見つかりませんでした。\n"
                    f"印刷用PDF:\n{output_path}"
                ),
            )

    def _open_vector_print_pdf(
        self,
        page_indexes,
        options,
    ):
        QApplication.setOverrideCursor(
            Qt.CursorShape.WaitCursor
        )
        try:
            output_path = HybridPrintExporter(
                self.document,
                self.annotations,
            ).create_print_pdf(
                page_indexes,
                include_annotations=(
                    options.print_annotations
                ),
            )
        except Exception as error:
            QMessageBox.critical(
                self.parent,
                "印刷用PDF作成エラー",
                "印刷用PDFを作成できませんでした。\n"
                f"{error}",
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

        opened = VectorPrintExporter.open_in_default_viewer(
            output_path
        )
        if not opened:
            QMessageBox.information(
                self.parent,
                "印刷用PDF",
                "印刷用PDFを作成しました。\n"
                f"{output_path}\n\n"
                "このファイルをPDFビューアで開いて"
                "印刷してください。",
            )
            return

        QMessageBox.information(
            self.parent,
            "ベクター高品質印刷",
            "印刷専用PDFを既定のPDFアプリで開きました。\n\n"
            "開いたアプリでCtrl＋Pを押して印刷してください。"
            "文字や線は元PDFのベクター品質を維持します。",
        )

    def _resolve_pages(self, options):
        if options.range_mode == "all":
            return list(range(self.document.page_count))

        if options.range_mode == "current":
            return [self.current_page]

        return self._parse_page_range(
            options.range_text,
            self.document.page_count,
        )

    @staticmethod
    def _parse_page_range(text, page_count):
        pages = set()
        value = str(text or "").strip()
        if not value:
            raise ValueError(
                "ページ範囲を入力してください。"
            )

        for token in value.split(","):
            token = token.strip()
            if not token:
                continue

            if "-" in token:
                start_text, end_text = token.split("-", 1)
                start = int(start_text)
                end = int(end_text)
                if start > end:
                    start, end = end, start
                pages.update(
                    page_number - 1
                    for page_number in range(start, end + 1)
                )
            else:
                pages.add(int(token) - 1)

        invalid = [
            page_index
            for page_index in pages
            if page_index < 0 or page_index >= page_count
        ]
        if invalid:
            raise ValueError(
                "存在しないページが指定されています。"
            )

        return sorted(pages)
