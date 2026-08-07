from __future__ import annotations

from datetime import datetime
import math
import os
from pathlib import Path
import shutil
import tempfile

import fitz

from app.annotations.annotation_renderer import (
    recommended_render_scale,
    render_annotation_image,
)
from app.annotations.render_contract import image_to_png_bytes, qrectf_to_fitz_rect
from app.annotations.image_annotation import draw_image_annotation
from app.annotations.stamp_callout import draw_pdf_annotation
from app.annotations.balloon_annotation import draw_balloon_annotation
from app.annotations.pdf_annotation_painter import draw_raster_annotation


class VectorPrintExporter:
    """Create a selected-page PDF while preserving original vector content."""

    def __init__(self, document, annotations):
        self.document = document
        self.annotations = list(annotations or [])

    def create_print_pdf(
        self,
        page_indexes,
        include_annotations=True,
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
            for source_index in indexes:
                if not (
                    0
                    <= source_index
                    < len(self.document.doc)
                ):
                    raise RuntimeError(
                        "存在しないページが含まれています。"
                    )

                output.insert_pdf(
                    self.document.doc,
                    from_page=source_index,
                    to_page=source_index,
                    links=True,
                    annots=True,
                )

                if include_annotations:
                    target_page = output[
                        len(output) - 1
                    ]
                    self._draw_page_annotations(
                        target_page,
                        source_index,
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
                output_path.unlink(missing_ok=True)
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
        directory = Path(
            tempfile.gettempdir()
        ) / "PDFInspector" / "Print"
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
            f"{source_name}_print_{timestamp}.pdf"
        )

    def _cleanup_old_print_files(self):
        directory = Path(
            tempfile.gettempdir()
        ) / "PDFInspector" / "Print"
        if not directory.exists():
            return

        cutoff = (
            datetime.now().timestamp()
            - 7 * 24 * 60 * 60
        )
        for path in directory.glob(
            "*_print_*.pdf"
        ):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                continue

    def _draw_page_annotations(
        self,
        page,
        source_page_index,
    ):
        for record in self.annotations:
            if (
                int(
                    record.get(
                        "page_index",
                        -1,
                    )
                )
                != source_page_index
            ):
                continue

            self._draw_record(
                page,
                record,
            )

    def _draw_record(self, page, record):
        record_type = str(record.get("type", ""))
        if record_type == "image":
            draw_image_annotation(page, record)
            return
        scale = recommended_render_scale(record, requested_scale=6.0)
        image, bounds = render_annotation_image(record, scale=scale)
        if image is None or bounds is None:
            return
        page.insert_image(
            qrectf_to_fitz_rect(bounds),
            stream=image_to_png_bytes(image),
            keep_proportion=False,
            overlay=True,
        )


    @staticmethod
    def _draw_cloud_shape(
        shape,
        rect,
        radius,
    ):
        radius = max(
            3.0,
            min(
                float(radius),
                min(
                    rect.width,
                    rect.height,
                )
                / 3.0,
            ),
        )
        shape.draw_rect(rect)

    @staticmethod
    def _fitz_color(value):
        text = str(
            value or "#000000"
        ).strip()

        named = {
            "black": "#000000",
            "red": "#ff0000",
            "blue": "#0000ff",
            "green": "#008000",
            "white": "#ffffff",
            "yellow": "#ffff00",
        }
        text = named.get(
            text.lower(),
            text,
        )

        if (
            len(text) == 7
            and text.startswith("#")
        ):
            try:
                return tuple(
                    int(
                        text[index:index + 2],
                        16,
                    )
                    / 255.0
                    for index in (
                        1,
                        3,
                        5,
                    )
                )
            except ValueError:
                pass

        return (0.0, 0.0, 0.0)
