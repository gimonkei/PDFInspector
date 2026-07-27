from dataclasses import dataclass

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem


@dataclass
class PageInfo:

    page: int

    pixmap: QPixmap

    item: QGraphicsPixmapItem

    top: float

    bottom: float


class PageManager:

    def __init__(self):

        self.pages = []


    def clear(self):

        self.pages.clear()


    def add_page(
        self,
        page,
        pixmap,
        item,
        top,
        bottom
    ):

        self.pages.append(

            PageInfo(

                page=page,

                pixmap=pixmap,

                item=item,

                top=top,

                bottom=bottom
            )
        )


    def count(self):

        return len(
            self.pages
        )


    def get(
        self,
        index
    ):

        if (
            index < 0
            or
            index >= len(self.pages)
        ):

            return None


        return self.pages[
            index
        ]


    def visible_page(
        self,
        y
    ):

        if not self.pages:
            return 0

    #
    # 一番近いページを探す
    #
        nearest = self.pages[0]

        distance = abs(
            y - nearest.top
        )

        for page in self.pages:

            d = abs(
                y - page.top
            )

            if d < distance:

                distance = d

                nearest = page

        return nearest.page