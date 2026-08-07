from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter
from PySide6.QtPrintSupport import QPrinter

from app.printing.print_renderer import PrintRenderer


class PrintEngine:
    def __init__(self, document, annotations):
        self.renderer = PrintRenderer(document, annotations)

    def print_pages(
        self,
        printer: QPrinter,
        page_indexes,
        options,
    ) -> None:
        painter = QPainter()
        if not painter.begin(printer):
            raise RuntimeError(
                "プリンターを開始できませんでした。"
            )

        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform,
            False,
        )

        try:
            printer_resolution = max(
                int(printer.resolution()),
                72,
            )

            for sequence, page_index in enumerate(page_indexes):
                if sequence > 0 and not printer.newPage():
                    raise RuntimeError(
                        "次の印刷ページを作成できませんでした。"
                    )

                image, render_dpi = self.renderer.render_page(
                    page_index,
                    options.quality_dpi,
                    options.print_annotations,
                )

                paint_rect = printer.pageRect(
                    QPrinter.Unit.DevicePixel
                )
                source_rect = QRectF(
                    0,
                    0,
                    image.width(),
                    image.height(),
                )

                if options.scale_mode == "fit":
                    scale = min(
                        paint_rect.width() / image.width(),
                        paint_rect.height() / image.height(),
                    )
                elif options.scale_mode == "actual":
                    scale = printer_resolution / render_dpi
                else:
                    scale = (
                        printer_resolution
                        / render_dpi
                        * (options.scale_percent / 100.0)
                    )

                target_width = image.width() * scale
                target_height = image.height() * scale

                if options.center:
                    target_x = (
                        paint_rect.left()
                        + (paint_rect.width() - target_width) / 2.0
                    )
                    target_y = (
                        paint_rect.top()
                        + (paint_rect.height() - target_height) / 2.0
                    )
                else:
                    target_x = paint_rect.left()
                    target_y = paint_rect.top()

                painter.drawImage(
                    QRectF(
                        target_x,
                        target_y,
                        target_width,
                        target_height,
                    ),
                    image,
                    source_rect,
                )
        finally:
            painter.end()
