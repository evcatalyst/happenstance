from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping, Sequence


def filter_events_by_window(
    events: Sequence[Mapping],
    days: int,
    now: datetime | None = None,
) -> list[Mapping]:
    now = now or datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days)
    filtered: list[Mapping] = []
    for event in events:
        date_str = event.get("date")
        if not date_str:
            continue
        try:
            event_dt = datetime.fromisoformat(date_str)
            if event_dt.tzinfo is None or event_dt.tzinfo.utcoffset(event_dt) is None:
                event_dt = event_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if event_dt.tzinfo is None or event_dt.tzinfo.utcoffset(event_dt) is None:
            event_dt = event_dt.replace(tzinfo=timezone.utc)
        if now <= event_dt <= cutoff:
            filtered.append(event)
    return filtered


def require_fields(items: Iterable[Mapping], required: Sequence[str]) -> None:
    for idx, item in enumerate(items):
        missing = [field for field in required if field not in item]
        if missing:
            label = item.get("name") or item.get("title") or "unknown"
            raise ValueError(f"Item {idx} ({label}) missing required fields: {', '.join(missing)}")
