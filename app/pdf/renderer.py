import fitz
from PySide6.QtGui import QImage, QPixmap


class PDFRenderer:


    def render_page(self, page):

        matrix = fitz.Matrix(
            2,
            2
        )

        pix = page.get_pixmap(
            matrix=matrix
        )


        image = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format_RGB888
        )


        return QPixmap.fromImage(
            image
        )