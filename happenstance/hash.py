import hashlib
import json
from typing import Iterable, List, Mapping, MutableMapping, Sequence

IGNORED_FIELDS = {"_meta", "timestamp", "meta", "match_reason"}


def _strip_ignored(obj: MutableMapping, ignore_fields: set[str]) -> MutableMapping:
    return {k: v for k, v in obj.items() if k not in ignore_fields}


def _normalize_items(items: Iterable[Mapping], ignore_fields: set[str]) -> List[Mapping]:
    normalized: List[Mapping] = []
    for item in items:
        clean = _strip_ignored(dict(item), ignore_fields)
        normalized.append(clean)
    return normalized


def canonical_hash(items: Sequence[Mapping], ignore_fields: set[str] | None = None) -> str:
    ignore_fields = ignore_fields or IGNORED_FIELDS
    normalized = _normalize_items(items, ignore_fields)
    normalized_sorted = sorted(normalized, key=lambda x: json.dumps(x, sort_keys=True))
    encoded = json.dumps(normalized_sorted, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_meta(
    items: Sequence[Mapping],
    previous_meta: Mapping | None = None,
    ignore_fields: set[str] | None = None,
) -> Mapping:
    items_hash = canonical_hash(items, ignore_fields)
    prev_hash = None
    if previous_meta:
        prev_hash = previous_meta.get("items_hash") or previous_meta.get("_meta", {}).get("items_hash")
    changed = prev_hash is None or prev_hash != items_hash
    return {
        "items_hash": items_hash,
        "items_changed": changed,
        "item_count": len(items),
    }
