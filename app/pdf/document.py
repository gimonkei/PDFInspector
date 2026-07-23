import fitz


class PDFDocument:

    def __init__(self):

        self.doc = None


    def open(self, path):

        self.doc = fitz.open(path)


    def close(self):

        if self.doc:

            self.doc.close()

        self.doc = None


    def has_document(self):

        return self.doc is not None


    @property
    def page_count(self):

        if not self.doc:

            return 0

        return len(self.doc)


    def get_page(self, index):

        if not self.doc:

            return None


        if index < 0 or index >= len(self.doc):

            return None


        return self.doc[index]


    def get_all_pages(self):

        """
        全ページ取得
        """

        if not self.doc:

            return []


        return [
            self.doc[i]
            for i in range(len(self.doc))
        ]