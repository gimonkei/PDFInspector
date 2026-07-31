import fitz

from app.annotations.date_stamp import render_date_stamp_png


class PDFDocumentError(Exception):
    """PDF操作に失敗したときの基底例外。"""


class PDFOpenError(PDFDocumentError):
    """PDFを開けなかったときの例外。"""


class PDFPasswordRequiredError(PDFOpenError):
    """パスワード保護されたPDFを開いたときの例外。"""


class PDFSaveError(PDFDocumentError):
    """PDFを保存できなかったときの例外。"""


class PDFDocument:

    def __init__(self):
        self.doc = None
        self.path = ""

    def open(self, path):
        try:
            document = fitz.open(path)
        except Exception as error:
            raise PDFOpenError(
                "PDFを開けませんでした。\n"
                "ファイルが破損しているか、PDF形式ではない可能性があります。"
            ) from error

        if document.needs_pass:
            document.close()
            raise PDFPasswordRequiredError(
                "このPDFはパスワードで保護されています。\n"
                "現在のバージョンではパスワード付きPDFを開けません。"
            )

        self.close()
        self.doc = document
        self.path = path

    def close(self):
        if self.doc:
            self.doc.close()

        self.doc = None
        self.path = ""

    def has_document(self):
        return self.doc is not None

    def save(self):
        if self.doc is None:
            raise PDFSaveError("保存するPDFが開かれていません。")

        if not self.path:
            raise PDFSaveError("保存先が設定されていません。")

        try:
            self.doc.save(
                self.path,
                incremental=True,
                encryption=fitz.PDF_ENCRYPT_KEEP
            )
        except Exception as error:
            raise PDFSaveError(
                "PDFを上書き保存できませんでした。\n"
                "ファイルが別のアプリで使用中か、書き込み権限がない可能性があります。"
            ) from error

    def save_as(self, path):
        if self.doc is None:
            raise PDFSaveError("保存するPDFが開かれていません。")

        try:
            self.doc.save(path)
        except Exception as error:
            raise PDFSaveError(
                "PDFを保存できませんでした。\n"
                "保存先の書き込み権限や空き容量を確認してください。"
            ) from error

        self.path = path

    @property
    def page_count(self):
        if self.doc is None:
            return 0

        return len(self.doc)

    def get_page(self, index):
        if self.doc is None:
            return None

        if index < 0 or index >= len(self.doc):
            return None

        return self.doc.load_page(index)

    def get_all_pages(self):
        if self.doc is None:
            return []

        return [
            self.doc.load_page(i)
            for i in range(len(self.doc))
        ]

    @staticmethod
    def _display_point_to_pdf(page, x, y):
        point = fitz.Point(float(x), float(y))
        if page.rotation:
            point = point * page.derotation_matrix
        return point

    def add_checkmark(self, page_index, x, y, size=15.0):
        page = self.get_page(page_index)
        if page is None:
            return None

        size = max(float(size), 6.0)
        display_points = [
            (x - size * 0.48, y),
            (x - size * 0.12, y + size * 0.38),
            (x + size * 0.55, y - size * 0.48),
        ]
        points = []
        for px, py in display_points:
            point = self._display_point_to_pdf(page, px, py)
            points.append((float(point.x), float(point.y)))

        annot = page.add_ink_annot([points])
        annot.set_colors(stroke=(1.0, 0.0, 0.0))
        annot.set_border(width=2.0)
        annot.set_info(
            title="PDFInspector",
            subject="チェック",
            content="チェック",
        )
        annot.update()
        return annot

    def add_freetext_comment(
        self,
        page_index,
        x,
        y,
        text,
        font_size=11.0,
    ):
        page = self.get_page(page_index)
        if page is None:
            return None

        content = str(text).strip()
        if not content:
            return None

        point = self._display_point_to_pdf(page, x, y)
        lines = content.splitlines() or [content]
        longest = max(len(line) for line in lines)
        width = max(90.0, longest * float(font_size) * 0.72 + 14.0)
        height = max(24.0, len(lines) * float(font_size) * 1.55 + 10.0)
        rect = fitz.Rect(
            point.x,
            point.y,
            point.x + width,
            point.y + height,
        )
        annot = page.add_freetext_annot(
            rect,
            content,
            fontsize=float(font_size),
            fontname="helv",
            text_color=(1.0, 0.0, 0.0),
            fill_color=None,
            border_color=None,
            align=0,
        )
        annot.set_info(
            title="PDFInspector",
            subject="コメント",
            content=content,
        )
        annot.update()
        return annot

    def add_date_stamp(
        self,
        page_index,
        x,
        y,
        top,
        date_text,
        bottom,
        color="black",
        size=72.0,
        line_width=1.5,
    ):
        page = self.get_page(page_index)
        if page is None:
            return None

        center = self._display_point_to_pdf(page, x, y)
        size = max(float(size), 42.0)
        half = size / 2.0
        rect = fitz.Rect(
            center.x - half,
            center.y - half,
            center.x + half,
            center.y + half,
        )
        record = {
            "top": str(top),
            "date": str(date_text),
            "bottom": str(bottom),
            "color": str(color),
            "size": size,
            "line_width": float(line_width),
        }
        png = render_date_stamp_png(record, scale=4.0)
        page.insert_image(rect, stream=png, overlay=True, keep_proportion=True)
        return rect

    def rotate_page(self, index, angle):
        if self.doc is None:
            return

        if index < 0 or index >= len(self.doc):
            return

        page = self.doc.load_page(index)
        current = page.rotation
        page.set_rotation((current + angle) % 360)

    def rotate_all_pages(self, angle):
        if self.doc is None:
            return

        for i in range(len(self.doc)):
            self.rotate_page(i, angle)
