import fitz


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
