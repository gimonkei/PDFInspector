from pathlib import Path
import shutil

root = Path(__file__).resolve().parent
source = root / "files/app/viewer/pdf_view.py"
target = root / "app/viewer/pdf_view.py"

if not source.exists():
    raise FileNotFoundError(source)
if not target.exists():
    raise FileNotFoundError(target)

backup = target.with_suffix(
    target.suffix + ".task019_phase8_7_1_backup"
)
if not backup.exists():
    shutil.copy2(target, backup)

shutil.copy2(source, target)
compile(
    target.read_text(encoding="utf-8"),
    str(target),
    "exec",
)

print("Task019 Phase8.7.1 applied successfully.")
print("The date-stamp preview flag error was fixed.")
