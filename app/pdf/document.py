import fitz


class PDFDocument:

    def __init__(self):

        self.doc = None

        self.path = ""


    def open(self, path):

        self.close()

        self.doc = fitz.open(path)

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

            return


        self.doc.save(
            self.path,
            incremental=True,
            encryption=fitz.PDF_ENCRYPT_KEEP
        )


    def save_as(
        self,
        path
    ):

        if self.doc is None:

            return


        self.doc.save(
            path
        )


        self.path = path


    @property
    def page_count(self):

        if self.doc is None:

            return 0


        return len(
            self.doc
        )


    def get_page(
        self,
        index
    ):

        if self.doc is None:

            return None


        if index < 0:

            return None


        if index >= len(
            self.doc
        ):

            return None


        return self.doc.load_page(
            index
        )


    def get_all_pages(self):

        if self.doc is None:

            return []


        return [
            self.doc.load_page(i)
            for i in range(
                len(self.doc)
            )
        ]

    def rotate_page(
        self,
        index,
        angle
    ):

        if self.doc is None:
            return

        if index < 0 or index >= len(self.doc):
            return

        page = self.doc.load_page(
            index
        )

        current = page.rotation

        page.set_rotation(
            (current + angle) % 360
        )

    def rotate_all_pages(
        self,
        angle
    ):

        if self.doc is None:
            return

        for i in range(
            len(self.doc)
        ):

            self.rotate_page(
                i,
                angle
            )