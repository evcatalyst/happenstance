import json
from pathlib import Path
from typing import Any, Mapping, Sequence

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def docs_path(filename: str) -> Path:
    return DOCS_DIR / filename


def append_meta(items: Sequence[Mapping], meta: Mapping) -> list:
    data = list(items)
    data.append({"_meta": meta})
    return data
