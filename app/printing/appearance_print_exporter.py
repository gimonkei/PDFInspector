from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import shutil
import tempfile

import fitz
from PySide6.QtCore import QByteArray, QBuffer, QIODevice

from app.printing.print_renderer import PrintRenderer


class AppearancePrintExporter:
    """Create a print PDF from one finalized page-rendering pipeline."""

    def __init__(self, document, annotations):
        self.document = document
        self.annotations = list(annotations or [])
        self.renderer = PrintRenderer(
            document,
            self.annotations,
        )

    def create_print_pdf(
        self,
        page_indexes,
        *,
        include_annotations=True,
        requested_dpi=600,
    ):
        if self.document.doc is None:
            raise RuntimeError(
                "PDFが開かれていません。"
            )

        indexes = [
            int(index)
            for index in page_indexes
        ]
        if not indexes:
            raise RuntimeError(
                "印刷対象ページがありません。"
            )

        self._cleanup_old_print_files()
        output_path = self._new_output_path()

        output = fitz.open()
        try:
            for page_index in indexes:
                if not (
                    0
                    <= page_index
                    < len(self.document.doc)
                ):
                    raise RuntimeError(
                        "存在しないページが含まれています。"
                    )

                source_page = self.document.doc[
                    page_index
                ]
                image, _dpi = self.renderer.render_page(
                    page_index,
                    int(requested_dpi),
                    bool(include_annotations),
                )

                data = QByteArray()
                buffer = QBuffer(data)
                buffer.open(
                    QIODevice.OpenModeFlag.WriteOnly
                )
                if not image.save(buffer, "PNG"):
                    raise RuntimeError(
                        "印刷ページ画像を作成できませんでした。"
                    )
                buffer.close()

                target_page = output.new_page(
                    width=float(source_page.rect.width),
                    height=float(source_page.rect.height),
                )
                target_page.insert_image(
                    target_page.rect,
                    stream=bytes(data),
                    keep_proportion=False,
                    overlay=True,
                )

            output.save(
                str(output_path),
                garbage=4,
                deflate=True,
                clean=True,
            )
        except Exception:
            output.close()
            try:
                output_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass
            raise
        else:
            output.close()

        return output_path

    @staticmethod
    def open_in_default_viewer(path):
        path = Path(path)
        try:
            if os.name == "nt":
                os.startfile(str(path))
                return True

            import subprocess

            command = (
                ["open", str(path)]
                if shutil.which("open")
                else ["xdg-open", str(path)]
            )
            subprocess.Popen(command)
            return True
        except (OSError, RuntimeError):
            return False

    def _new_output_path(self):
        directory = (
            Path(tempfile.gettempdir())
            / "PDFInspector"
            / "Print"
        )
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        source_name = Path(
            self.document.path
            or "document.pdf"
        ).stem
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )
        return directory / (
            f"{source_name}_appearance_print_"
            f"{timestamp}.pdf"
        )

    def _cleanup_old_print_files(self):
        directory = (
            Path(tempfile.gettempdir())
            / "PDFInspector"
            / "Print"
        )
        if not directory.exists():
            return

        cutoff = (
            datetime.now().timestamp()
            - 7 * 24 * 60 * 60
        )
        for path in directory.glob(
            "*_appearance_print_*.pdf"
        ):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                continue
