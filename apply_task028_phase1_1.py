from pathlib import Path
import shutil

root = Path(__file__).resolve().parent
source = root / "files/app/ui/main_window.py"
target = root / "app/ui/main_window.py"

if not source.exists():
    raise FileNotFoundError(source)
if not target.exists():
    raise FileNotFoundError(target)

backup = target.with_suffix(
    target.suffix + ".task028_phase1_1_backup"
)
if not backup.exists():
    shutil.copy2(target, backup)

shutil.copy2(source, target)
compile(
    target.read_text(encoding="utf-8"),
    str(target),
    "exec",
)

print("Task028 Phase1.1 applied successfully.")
print("Paper-size labels now use a theme-aware badge.")
