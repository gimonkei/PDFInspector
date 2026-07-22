import sys

from PySide6.QtWidgets import QApplication, QLabel


def main():
    app = QApplication(sys.argv)

    window = QLabel(
        "PDFInspector 起動確認"
    )

    window.resize(400, 200)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()