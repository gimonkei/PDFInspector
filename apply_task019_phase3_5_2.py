from pathlib import Path
import shutil

root = Path(__file__).resolve().parent
paths = [
    Path("app/viewer/pdf_view.py"),
    Path("app/viewer/selection_overlay.py"),
]

for relative in paths:
    source = root / "files" / relative
    target = root / relative
    if not source.exists():
        raise FileNotFoundError(source)
    if not target.exists():
        raise FileNotFoundError(target)

for relative in paths:
    source = root / "files" / relative
    target = root / relative
    backup = target.with_suffix(
        target.suffix + ".task019_phase3_5_2_backup"
    )
    if not backup.exists():
        shutil.copy2(target, backup)
    shutil.copy2(source, target)
    compile(target.read_text(encoding="utf-8"), str(target), "exec")

print("Task019 Phase3.5.2 applied successfully.")
print("Selection handles now take priority over new shape creation.")
