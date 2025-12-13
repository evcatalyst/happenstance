import json
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"


def _load(name: str):
    with open(DOCS / name, "r", encoding="utf-8") as f:
        return json.load(f)


def test_events_structure():
    data = _load("events.json")
    assert isinstance(data, list)
    *items, meta = data
    for event in items:
        for field in ["title", "category", "date", "location", "url"]:
            assert field in event
    assert "_meta" in meta
    assert {"items_hash", "items_changed", "item_count"} <= set(meta["_meta"].keys())


def test_restaurants_structure():
    data = _load("restaurants.json")
    assert isinstance(data, list)
    *items, meta = data
    for restaurant in items:
        for field in ["name", "cuisine", "address", "url"]:
            assert field in restaurant
    assert "_meta" in meta
    assert {"items_hash", "items_changed", "item_count"} <= set(meta["_meta"].keys())


def test_config_structure():
    config = _load("config.json")
    assert "branding" in config
    assert "pairing_rules" in config
