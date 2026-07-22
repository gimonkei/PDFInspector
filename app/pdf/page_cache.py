from PySide6.QtGui import QPixmap


class PageCache:
    """
    PDFページの描画結果を保持するキャッシュ
    """

    def __init__(self):

        self.cache = {}


    def get(self, page_index):

        return self.cache.get(
            page_index
        )


    def set(
        self,
        page_index,
        pixmap: QPixmap
    ):

        self.cache[page_index] = pixmap


    def clear(self):

        self.cache.clear()


    def contains(
        self,
        page_index
    ):

        return page_index in self.cache