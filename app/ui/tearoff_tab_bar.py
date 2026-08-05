from __future__ import annotations

import json

from PySide6.QtCore import QByteArray, QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QApplication, QFrame, QTabBar


class TearOffTabBar(QTabBar):
    MIME_TYPE = "application/x-pdfinspector-document-tab"

    tearOffRequested = Signal(int, QPoint)
    tabTransferRequested = Signal(str, int, int)

    def __init__(self, owner_window_id, parent=None):
        super().__init__(parent)
        self.owner_window_id = str(owner_window_id)
        self._press_position = None
        self._press_index = -1
        self._drag_running = False
        self.setAcceptDrops(True)

        self._drop_indicator = QFrame(self)
        self._drop_indicator.setFixedWidth(3)
        self._drop_indicator.setStyleSheet(
            "background: palette(highlight);"
        )
        self._drop_indicator.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.position().toPoint()
            self._press_index = self.tabAt(self._press_position)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_running
            or self._press_position is None
            or self._press_index < 0
            or not (event.buttons() & Qt.MouseButton.LeftButton)
        ):
            super().mouseMoveEvent(event)
            return

        distance = (
            event.position().toPoint() - self._press_position
        ).manhattanLength()
        if distance < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        self._start_document_drag(self._press_index)

    def mouseReleaseEvent(self, event):
        self._press_position = None
        self._press_index = -1
        super().mouseReleaseEvent(event)

    def _start_document_drag(self, index):
        if index < 0 or index >= self.count():
            return

        self._drag_running = True
        try:
            mime = QMimeData()
            payload = {
                "window_id": self.owner_window_id,
                "tab_index": int(index),
            }
            mime.setData(
                self.MIME_TYPE,
                QByteArray(json.dumps(payload).encode("utf-8")),
            )

            drag = QDrag(self)
            drag.setMimeData(mime)
            rect = self.tabRect(index)
            pixmap = self.grab(rect)
            if not pixmap.isNull():
                drag.setPixmap(pixmap)
                drag.setHotSpot(
                    QPoint(
                        min(rect.width() // 2, pixmap.width() // 2),
                        min(rect.height() // 2, pixmap.height() // 2),
                    )
                )

            result = drag.exec(Qt.DropAction.MoveAction)
            if result == Qt.DropAction.IgnoreAction:
                self.tearOffRequested.emit(
                    index,
                    self.cursor().pos(),
                )
        finally:
            self._drag_running = False
            self._press_position = None
            self._press_index = -1
            self._hide_drop_indicator()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            self._show_drop_indicator(
                self._target_index(event.position().toPoint())
            )
            return
        event.ignore()

    def dragMoveEvent(self, event):
        if not event.mimeData().hasFormat(self.MIME_TYPE):
            event.ignore()
            return
        target_index = self._target_index(
            event.position().toPoint()
        )
        self._show_drop_indicator(target_index)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def dragLeaveEvent(self, event):
        self._hide_drop_indicator()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._hide_drop_indicator()
        if not event.mimeData().hasFormat(self.MIME_TYPE):
            event.ignore()
            return

        try:
            raw = bytes(
                event.mimeData().data(self.MIME_TYPE)
            )
            payload = json.loads(raw.decode("utf-8"))
            source_window_id = str(payload["window_id"])
            source_index = int(payload["tab_index"])
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            event.ignore()
            return

        target_index = self._target_index(
            event.position().toPoint()
        )
        self.tabTransferRequested.emit(
            source_window_id,
            source_index,
            target_index,
        )
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def _target_index(self, point):
        if self.count() <= 0:
            return 0
        for index in range(self.count()):
            if point.x() < self.tabRect(index).center().x():
                return index
        return self.count()

    def _show_drop_indicator(self, target_index):
        if self.count() <= 0:
            x = 2
        elif target_index >= self.count():
            x = self.tabRect(self.count() - 1).right() + 2
        else:
            x = self.tabRect(target_index).left() - 2

        self._drop_indicator.setGeometry(
            max(0, x),
            2,
            3,
            max(10, self.height() - 4),
        )
        self._drop_indicator.raise_()
        self._drop_indicator.show()

    def _hide_drop_indicator(self):
        self._drop_indicator.hide()
