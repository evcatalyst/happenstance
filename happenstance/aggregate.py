from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Mapping

from .config import load_config
from .hash import compute_meta
from .io import append_meta, docs_path, read_json, write_json
from .prompting import build_gap_bullets, month_spread_guidance
from .search import build_live_search_params
from .validate import filter_events_by_window


def _fixture_restaurants(region: str) -> List[Dict]:
    return [
        {
            "name": "Blue Harbor Grill",
            "cuisine": "Seafood",
            "address": f"{region} Waterfront",
            "url": "https://example.com/blue-harbor",
            "match_reason": "Great before a waterfront concert",
        },
        {
            "name": "Sunset Pasta",
            "cuisine": "Italian",
            "address": f"{region} Arts District",
            "url": "https://example.com/sunset-pasta",
            "match_reason": "Close to the gallery walk",
        },
        {
            "name": "Midnight Sushi",
            "cuisine": "Sushi",
            "address": f"{region} Downtown",
            "url": "https://example.com/midnight-sushi",
            "match_reason": "Open late after live music",
        },
        {
            "name": "Firepit BBQ",
            "cuisine": "BBQ",
            "address": f"{region} Market",
            "url": "https://example.com/firepit-bbq",
            "match_reason": "Perfect for families near the park",
        },
    ]


def _fixture_events(region: str) -> List[Dict]:
    now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    return [
        {
            "title": "Waterfront Jazz Night",
            "category": "live music",
            "date": (now + timedelta(days=2)).isoformat(),
            "location": f"{region} Waterfront Stage",
            "url": "https://example.com/jazz-night",
        },
        {
            "title": "Gallery Walk",
            "category": "art",
            "date": (now + timedelta(days=5)).isoformat(),
            "location": f"{region} Arts District",
            "url": "https://example.com/gallery-walk",
        },
        {
            "title": "Family Picnic at the Park",
            "category": "family",
            "date": (now + timedelta(days=7)).isoformat(),
            "location": f"{region} Central Park",
            "url": "https://example.com/family-picnic",
        },
        {
            "title": "City Fun Run",
            "category": "sports",
            "date": (now + timedelta(days=15)).isoformat(),
            "location": f"{region} River Trail",
            "url": "https://example.com/city-fun-run",
        },
    ]


def _build_pairings(events: List[Dict], restaurants: List[Dict]) -> List[Dict]:
    if not restaurants:
        return []
    pairings: List[Dict] = []
    for idx, event in enumerate(events):
        restaurant = restaurants[idx % len(restaurants)]
        pairings.append(
            {
                "event": event["title"],
                "restaurant": restaurant["name"],
                "match_reason": restaurant.get("match_reason", "Nearby and reliable"),
                "event_url": event.get("url"),
                "restaurant_url": restaurant.get("url"),
            }
        )
    return pairings


def aggregate(profile: str | None = None) -> Dict[str, Mapping]:
    cfg = load_config(profile)
    restaurants = _fixture_restaurants(cfg["region"])
    events = filter_events_by_window(_fixture_events(cfg["region"]), cfg["event_window_days"])

    gap_cuisines = [c for c in cfg.get("target_cuisines", []) if c not in {r["cuisine"] for r in restaurants}]
    gap_categories = [c for c in cfg.get("target_categories", []) if c not in {e["category"] for e in events}]
    gap_bullets = build_gap_bullets(gap_cuisines + gap_categories)

    previous_meta = read_json(docs_path("meta.json")) or {}

    restaurants_meta = compute_meta(restaurants, previous_meta.get("restaurants", {}))
    events_meta = compute_meta(events, previous_meta.get("events", {}))

    meta_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": cfg["profile"],
        "region": cfg["region"],
        "branding": cfg.get("branding", {}),
        "pairing_rules": cfg.get("pairing_rules", []),
        "search": build_live_search_params(cfg),
        "gap_bullets": gap_bullets,
        "events": events_meta,
        "restaurants": restaurants_meta,
        "pairings": _build_pairings(events, restaurants),
        "guidance": month_spread_guidance(),
    }

    persist_outputs(restaurants, restaurants_meta, events, events_meta, cfg, meta_payload)
    return {"events": events, "restaurants": restaurants, "meta": meta_payload}


def persist_outputs(
    restaurants: List[Mapping],
    restaurants_meta: Mapping,
    events: List[Mapping],
    events_meta: Mapping,
    cfg: Mapping,
    meta_payload: Mapping,
) -> None:
    append_meta_write("restaurants.json", restaurants, restaurants_meta)
    append_meta_write("events.json", events, events_meta)
    write_json_raw("config.json", {"branding": cfg.get("branding", {}), "pairing_rules": cfg.get("pairing_rules", [])})
    write_json_raw("meta.json", meta_payload)


def append_meta_write(name: str, items: List[Mapping], meta: Mapping) -> None:
    payload = append_meta(items, meta)
    write_json(docs_path(name), payload)


def write_json_raw(name: str, payload) -> None:
    write_json(docs_path(name), payload)
