from pathlib import Path
import shutil, compileall
root=Path(__file__).resolve().parent
files=[Path("app/pdf/document.py"),Path("app/annotations/annotation_renderer.py"),Path("tests/source_regression_phase5_2.py")]
for rel in files:
    src=root/"files"/rel; dst=root/rel
    if not src.exists(): raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists():
        bak=dst.with_suffix(dst.suffix+".task041_phase5_2_backup")
        if not bak.exists(): shutil.copy2(dst,bak)
    shutil.copy2(src,dst)
    compile(dst.read_text(encoding="utf-8"),str(dst),"exec")
    print("Installed:",dst)
if not compileall.compile_dir(str(root),quiet=1,force=True): raise RuntimeError("compileall failed")
exec((root/"tests/source_regression_phase5_2.py").read_text(encoding="utf-8"),{"__file__":str(root/"tests/source_regression_phase5_2.py")})
print("Task041 Phase5.2 applied successfully.")
