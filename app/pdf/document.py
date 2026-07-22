import fitz


class PDFDocument:

    def __init__(self):
        self.doc = None


    def open(self, path):

        self.doc = fitz.open(path)


    def get_page(self, index):

        return self.doc[index]


    def page_count(self):

        if self.doc:
            return len(self.doc)

        return 0