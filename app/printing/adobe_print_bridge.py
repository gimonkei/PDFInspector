from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys


@dataclass(frozen=True)
class AdobePrintResult:
    started: bool
    executable: Path | None = None
    process_id: int | None = None
    message: str = ""


class AdobePrintBridge:
    """Send a PDF to a selected Windows printer through Adobe Acrobat."""

    def find_executable(self):
        if os.name != "nt":
            return None

        candidates = []

        for environment_name in (
            "ProgramFiles",
            "ProgramFiles(x86)",
            "ProgramW6432",
            "LOCALAPPDATA",
        ):
            root_value = os.environ.get(
                environment_name
            )
            if not root_value:
                continue

            root = Path(root_value)
            candidates.extend(
                [
                    root
                    / "Adobe/Acrobat DC/Acrobat/Acrobat.exe",
                    root
                    / "Adobe/Acrobat Reader DC/Reader/AcroRd32.exe",
                    root
                    / "Adobe/Reader 11.0/Reader/AcroRd32.exe",
                    root
                    / "Adobe/Acrobat 2020/Acrobat/Acrobat.exe",
                    root
                    / "Adobe/Acrobat 2017/Acrobat/Acrobat.exe",
                ]
            )

        registry_candidates = self._registry_candidates()
        candidates.extend(registry_candidates)

        seen = set()
        for candidate in candidates:
            try:
                resolved = candidate.expanduser().resolve()
            except OSError:
                resolved = candidate

            normalized = str(resolved).lower()
            if normalized in seen:
                continue
            seen.add(normalized)

            if resolved.is_file():
                return resolved

        return None

    def open_print_dialog(
        self,
        pdf_path,
    ):
        pdf_path = Path(pdf_path).resolve()
        if not pdf_path.is_file():
            return AdobePrintResult(
                False,
                message="印刷用PDFが存在しません。",
            )

        executable = self.find_executable()
        if executable is None:
            return AdobePrintResult(
                False,
                message=(
                    "Adobe Acrobat／Readerを"
                    "検出できませんでした。"
                ),
            )

        # /p opens the document and immediately invokes Adobe's print dialog.
        # Do not use /h here because it can also hide or minimize the dialog
        # on some Acrobat / Reader versions.
        command = [
            str(executable),
            "/n",
            "/p",
            str(pdf_path),
        ]

        try:
            process = subprocess.Popen(
                command,
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            return AdobePrintResult(
                False,
                executable=executable,
                message=str(error),
            )

        return AdobePrintResult(
            True,
            executable=executable,
            process_id=process.pid,
            message=(
                "Adobeの印刷画面を起動しました。"
            ),
        )

    def print_pdf(
        self,
        pdf_path,
        printer_name,
    ):
        pdf_path = Path(pdf_path).resolve()
        if not pdf_path.is_file():
            return AdobePrintResult(
                False,
                message="印刷用PDFが存在しません。",
            )

        executable = self.find_executable()
        if executable is None:
            return AdobePrintResult(
                False,
                message=(
                    "Adobe Acrobat／Readerを"
                    "検出できませんでした。"
                ),
            )

        printer_name = str(
            printer_name or ""
        ).strip()
        if not printer_name:
            return AdobePrintResult(
                False,
                executable=executable,
                message="プリンター名が空です。",
            )

        creation_flags = 0
        startup_info = None

        if os.name == "nt":
            creation_flags = getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            )
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= (
                subprocess.STARTF_USESHOWWINDOW
            )
            startup_info.wShowWindow = 0

        command = [
            str(executable),
            "/n",
            "/s",
            "/o",
            "/h",
            "/t",
            str(pdf_path),
            printer_name,
        ]

        try:
            process = subprocess.Popen(
                command,
                close_fds=True,
                creationflags=creation_flags,
                startupinfo=startup_info,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            return AdobePrintResult(
                False,
                executable=executable,
                message=str(error),
            )

        return AdobePrintResult(
            True,
            executable=executable,
            process_id=process.pid,
            message=(
                "Adobeへ印刷命令を送信しました。"
            ),
        )

    @staticmethod
    def _registry_candidates():
        if os.name != "nt":
            return []

        try:
            import winreg
        except ImportError:
            return []

        results = []
        keys = (
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Acrobat.exe",
            ),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\AcroRd32.exe",
            ),
            (
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Acrobat.exe",
            ),
            (
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\AcroRd32.exe",
            ),
        )

        access_modes = [
            winreg.KEY_READ,
        ]
        if hasattr(
            winreg,
            "KEY_WOW64_64KEY",
        ):
            access_modes.extend(
                [
                    winreg.KEY_READ
                    | winreg.KEY_WOW64_64KEY,
                    winreg.KEY_READ
                    | winreg.KEY_WOW64_32KEY,
                ]
            )

        for root, key_path in keys:
            for access in access_modes:
                try:
                    with winreg.OpenKey(
                        root,
                        key_path,
                        0,
                        access,
                    ) as key:
                        value, _ = winreg.QueryValueEx(
                            key,
                            None,
                        )
                except OSError:
                    continue

                if value:
                    results.append(
                        Path(str(value).strip('"'))
                    )

        return results
