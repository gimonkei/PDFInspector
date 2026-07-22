import fitz


class PDFDocument:

    def __init__(self):

        self.doc = None


    def open(self, path):

        self.doc = fitz.open(path)


    def get_page(self, index):

        if self.doc is None:
            return None

        return self.doc[index]


    @property
    def page_count(self):

        if self.doc is None:
            return 0

        return len(self.doc)


    def has_document(self):

        return self.doc is not None