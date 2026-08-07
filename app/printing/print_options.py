from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)


@dataclass(frozen=True)
class PrintOptions:
    print_mode: str
    range_mode: str
    range_text: str
    scale_mode: str
    scale_percent: int
    print_annotations: bool
    center: bool
    quality_dpi: int


class PrintOptionsDialog(QDialog):
    def __init__(
        self,
        parent,
        page_count: int,
        current_page: int,
    ):
        super().__init__(parent)
        self.setWindowTitle("印刷設定")
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.print_mode_combo = QComboBox(self)
        self.print_mode_combo.addItem(
            "Adobeの印刷画面を表示（推奨）",
            "adobe_dialog",
        )
        self.print_mode_combo.addItem(
            "Adobe経由で直接印刷",
            "adobe_direct",
        )
        self.print_mode_combo.addItem(
            "印刷用PDFを既定アプリで開く",
            "vector_open",
        )
        self.print_mode_combo.addItem(
            "見た目優先PDFから印刷",
            "raster",
        )
        self.print_mode_combo.setToolTip(
            "Adobeの印刷画面を表示すると、ベクター品質を維持したまま"
            "プリンター、用紙、倍率、両面などをAdobe側で確認できます。"
        )
        form.addRow(
            "印刷方式:",
            self.print_mode_combo,
        )

        self.range_combo = QComboBox(self)
        self.range_combo.addItem("すべてのページ", "all")
        self.range_combo.addItem("現在のページ", "current")
        self.range_combo.addItem("ページ指定", "custom")
        form.addRow("印刷範囲:", self.range_combo)

        self.range_edit = QLineEdit(self)
        self.range_edit.setPlaceholderText("例: 1,3,5-8")
        self.range_edit.setEnabled(False)
        form.addRow("ページ:", self.range_edit)
        self.range_combo.currentIndexChanged.connect(
            self._update_range_state
        )

        self.scale_combo = QComboBox(self)
        self.scale_combo.addItem("用紙に合わせる", "fit")
        self.scale_combo.addItem("実際のサイズ（100%）", "actual")
        self.scale_combo.addItem("指定倍率", "custom")
        form.addRow("拡大縮小:", self.scale_combo)

        self.scale_spin = QSpinBox(self)
        self.scale_spin.setRange(10, 400)
        self.scale_spin.setValue(100)
        self.scale_spin.setSuffix("%")
        self.scale_spin.setEnabled(False)
        form.addRow("倍率:", self.scale_spin)
        self.scale_combo.currentIndexChanged.connect(
            self._update_scale_state
        )
        self.print_mode_combo.currentIndexChanged.connect(
            self._update_print_mode_state
        )

        self.quality_combo = QComboBox(self)
        self.quality_combo.addItem("標準（300 dpi）", 300)
        self.quality_combo.addItem("高品質（600 dpi）", 600)
        self.quality_combo.addItem("最高品質（1200 dpi）", 1200)
        self.quality_combo.setCurrentIndex(1)
        self.quality_combo.setEnabled(False)
        self.quality_combo.setToolTip(
            "大判ページではメモリ保護のため自動的に上限を下げます。"
        )
        form.addRow("印刷品質:", self.quality_combo)

        self.print_annotations_check = QCheckBox(
            "PDFInspectorの注釈も印刷する",
            self,
        )
        self.print_annotations_check.setChecked(True)
        form.addRow("", self.print_annotations_check)

        self.center_check = QCheckBox(
            "用紙の中央に配置",
            self,
        )
        self.center_check.setChecked(True)
        form.addRow("", self.center_check)

        layout.addLayout(form)

        note = QLabel(
            f"全{page_count}ページ／現在は{current_page + 1}ページ目",
            self,
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        quality_note = QLabel(
            "Adobeの印刷画面を表示する方式では、文字・寸法線・円弧を"
            "画像化せずに印刷専用PDFへ保持し、"
            "Adobeの印刷設定画面を直接開きます。"
            "\nAdobe上で改めてCtrl＋Pを押す必要はありません。"
            "\nAdobeが見つからない場合は印刷用PDFを開きます。",
            self,
        )
        quality_note.setWordWrap(True)
        layout.addWidget(quality_note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_print_mode_state(self):
        appearance_mode = (
            self.print_mode_combo.currentData()
            == "raster"
        )

        self.quality_combo.setEnabled(
            appearance_mode
        )
        self.scale_combo.setEnabled(False)
        self.scale_spin.setEnabled(False)
        self.center_check.setEnabled(False)

    def _update_range_state(self):
        self.range_edit.setEnabled(
            self.range_combo.currentData() == "custom"
        )

    def _update_scale_state(self):
        self.scale_spin.setEnabled(
            self.scale_combo.currentData() == "custom"
        )

    def values(self) -> PrintOptions:
        return PrintOptions(
            print_mode=str(
                self.print_mode_combo.currentData()
            ),
            range_mode=str(self.range_combo.currentData()),
            range_text=self.range_edit.text().strip(),
            scale_mode=str(self.scale_combo.currentData()),
            scale_percent=int(self.scale_spin.value()),
            print_annotations=(
                self.print_annotations_check.isChecked()
            ),
            center=self.center_check.isChecked(),
            quality_dpi=int(self.quality_combo.currentData()),
        )
