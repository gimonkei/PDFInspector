from pathlib import Path

root = Path(__file__).resolve().parents[1]
doc = (root / "app/pdf/document.py").read_text(encoding="utf-8")
renderer = (root / "app/annotations/annotation_renderer.py").read_text(encoding="utf-8")
assert "self._document[int(page_index)]" not in doc
assert "page = self.get_page(int(page_index))" in doc
assert "def _absolute_points(record):" in renderer
assert "_absolute_points(record)" in renderer
assert 'if kind == "text":' in renderer
print("Phase5.2 source regression checks passed.")
