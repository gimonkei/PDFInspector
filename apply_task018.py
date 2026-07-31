from pathlib import Path
import shutil

root = Path(__file__).resolve().parent
source_root = root / "files"
paths = [
    Path("app/viewer/pdf_view.py"),
    Path("app/ui/main_window.py"),
]

for relative in paths:
    source = source_root / relative
    target = root / relative
    if not source.exists():
        raise FileNotFoundError(source)
    if not target.exists():
        raise FileNotFoundError(target)

for relative in paths:
    source = source_root / relative
    target = root / relative
    backup = target.with_suffix(target.suffix + ".task018_backup")
    if not backup.exists():
        shutil.copy2(target, backup)
    shutil.copy2(source, target)

for relative in paths:
    target = root / relative
    compile(target.read_text(encoding="utf-8"), str(target), "exec")

print("Task018 applied successfully.")
print("Annotation Undo / Redo is now available with Ctrl+Z / Ctrl+Y.")
