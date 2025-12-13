from datetime import datetime, timedelta

from happenstance.prompting import build_gap_bullets
from happenstance.validate import filter_events_by_window


def test_filter_events_by_window_excludes_outside():
    now = datetime(2024, 1, 1, 12, 0, 0)
    events = [
        {"title": "soon", "date": (now + timedelta(days=2)).isoformat()},
        {"title": "far", "date": (now + timedelta(days=20)).isoformat()},
    ]
    filtered = filter_events_by_window(events, days=10, now=now)
    assert len(filtered) == 1
    assert filtered[0]["title"] == "soon"


def test_gap_bullets_cap_three():
    missing = ["one", "two", "three", "four"]
    bullets = build_gap_bullets(missing)
    assert len(bullets) == 3
    assert bullets[0].startswith("Add more options for one")
