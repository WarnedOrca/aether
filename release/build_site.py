"""Build the static GitHub Pages demo into dist/site.

Usage: uv run python -m release.build_site
Contents: index.html, web_app.py, the checker and interpreter sources (py/), a file
manifest, and the example programs that include their own policy.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "site"


def build() -> list[str]:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "py").mkdir(parents=True)
    manifest = ["web_app.py"]
    shutil.copy(ROOT / "pages/web_app.py", OUT / "py/web_app.py")
    for pkg in ("checker", "interpreter"):
        for f in sorted((ROOT / pkg).iterdir()):
            if f.suffix in (".py", ".lark") and f.name != "__main__.py":
                (OUT / "py" / pkg).mkdir(exist_ok=True)
                shutil.copy(f, OUT / "py" / pkg / f.name)
                manifest.append(f"{pkg}/{f.name}")
    examples = {}
    first = "AppointmentReminders.ae"
    for f in sorted((ROOT / "data/examples").glob("*.ae"), key=lambda p: (p.name != first, p.name)):
        text = f.read_text(encoding="utf-8")
        if text.lstrip().startswith("policy "):  # self-contained examples only
            examples[f.stem] = text
    (OUT / "files.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (OUT / "examples.json").write_text(json.dumps(examples, indent=1), encoding="utf-8")
    shutil.copy(ROOT / "pages/index.html", OUT / "index.html")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    shutil.copy(ROOT / "LICENSE", OUT / "LICENSE")
    return manifest


if __name__ == "__main__":
    files = build()
    print(f"built dist/site: {len(files)} python files, examples: "
          f"{len(json.loads((OUT / 'examples.json').read_text(encoding='utf-8')))}")
