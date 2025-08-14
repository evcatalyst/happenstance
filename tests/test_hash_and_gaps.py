import importlib.util, sys, types, json
from pathlib import Path

# Dynamically load aggregate.py without executing main logic (guarded by __main__)
MODULE_PATH = Path('scripts/aggregate.py')
spec = importlib.util.spec_from_file_location('aggregate', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules['aggregate'] = mod
spec.loader.exec_module(mod)  # type: ignore


def test_canonical_items_hash_stability():
    items1 = [
        {"name": "A", "address": "1 Main", "cuisine": "Thai", "_transient": 123},
        {"name": "B", "address": "2 Main", "cuisine": "Pizza"},
    ]
    items2 = [
        {"name": "B", "address": "2 Main", "cuisine": "Pizza", "ignored": True},
        {"name": "A", "address": "1 Main", "cuisine": "Thai"},
    ]
    h1 = mod.canonical_items_hash(items1)
    h2 = mod.canonical_items_hash(items2)
    assert h1 == h2, "Hash should be order & transient-key agnostic"


def test_gap_bullets_restaurants_missing():
    # Provide only two cuisines; expect bullet referencing missing others
    items = [
        {"name": "Spot A", "cuisine": "Thai"},
        {"name": "Spot B", "cuisine": "Pizza"},
    ]
    bullets = mod.__dict__['compute_gap_bullets']('restaurants', items) if 'compute_gap_bullets' in mod.__dict__ else []
    # compute_gap_bullets is nested; fallback: re-implement reference check via calling through a small shim if exposed
    if not bullets:
        # emulate logic (ensures test won't hard fail if symbol gets exported later)
        pass
    assert bullets and 'missing cuisines' in bullets[0].lower()


def test_gap_bullets_events_missing():
    items = [
        {"name": "Event A", "category": "live music"},
    ]
    bullets = mod.__dict__['compute_gap_bullets']('events', items) if 'compute_gap_bullets' in mod.__dict__ else []
    assert bullets and 'categories' in bullets[0].lower()
