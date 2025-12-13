from happenstance.hash import canonical_hash, compute_meta


def test_canonical_hash_ignores_order_and_meta():
    items_a = [
        {"name": "a", "value": 1, "_meta": {"note": "ignore"}},
        {"name": "b", "value": 2},
    ]
    items_b = [
        {"name": "b", "value": 2},
        {"name": "a", "value": 1, "timestamp": "ignored"},
    ]
    assert canonical_hash(items_a) == canonical_hash(items_b)


def test_items_changed_detection():
    items = [{"name": "a"}]
    first_meta = compute_meta(items, None)
    second_meta = compute_meta(items, {"items_hash": first_meta["items_hash"]})
    assert first_meta["items_changed"] is True
    assert second_meta["items_changed"] is False
