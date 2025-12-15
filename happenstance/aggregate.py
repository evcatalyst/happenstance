from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping

import requests

from .config import load_config
from .hash import compute_meta
from .io import append_meta, docs_path, read_json, write_json
from .prompting import build_gap_bullets, month_spread_guidance
from .search import build_live_search_params
from .sources import (
    fetch_eventbrite_events,
    fetch_google_places_restaurants,
    fetch_ticketmaster_events,
)
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


def _compute_match_score(event: Dict, restaurant: Dict) -> tuple[int, str]:
    score = 0
    reasons: List[str] = []
    category = event.get("category", "").lower()
    cuisine = restaurant.get("cuisine", "").lower()
    title = event.get("title", "").lower()
    match_reason = restaurant.get("match_reason", "")

    if category and cuisine and category in cuisine:
        score += 2
        reasons.append(f"Matches category '{event.get('category')}' with cuisine '{restaurant.get('cuisine')}'")

    if "family" in title or "kids" in title:
        if "family" in match_reason.lower() or "family" in cuisine:
            score += 2
            reasons.append("Family-friendly pairing")

    if "night" in title or "late" in title:
        if "late" in match_reason.lower() or "open" in match_reason.lower():
            score += 1
            reasons.append("Open late for night event")

    if not reasons:
        reasons.append(match_reason or "Nearby and reliable")

    return score, "; ".join(reasons)


def _build_pairings(events: List[Dict], restaurants: List[Dict]) -> List[Dict]:
    if not restaurants:
        return []
    pairings: List[Dict] = []
    for event in events:
        best_score = float("-inf")
        best_restaurant: Dict | None = None
        best_reason = ""
        for restaurant in restaurants:
            score, reason = _compute_match_score(event, restaurant)
            if score > best_score:
                best_score = score
                best_restaurant = restaurant
                best_reason = reason
        pairings.append(
            {
                "event": event["title"],
                "restaurant": best_restaurant["name"] if best_restaurant else "",
                "match_reason": best_reason,
                "event_url": event.get("url"),
                "restaurant_url": best_restaurant.get("url") if best_restaurant else None,
            }
        )
    return pairings


def _fetch_restaurants(cfg: Mapping) -> List[Dict]:
    """Fetch restaurants based on configured data source."""
    data_sources = cfg.get("data_sources", {})
    restaurant_source = data_sources.get("restaurants", "fixtures")
    region = cfg["region"]
    
    if restaurant_source == "fixtures":
        print(f"Using fixture data for restaurants in {region}")
        return _fixture_restaurants(region)
    elif restaurant_source == "google_places":
        print(f"Fetching restaurants from Google Places API for {region}")
        api_config = cfg.get("api_config", {}).get("google_places", {})
        try:
            return fetch_google_places_restaurants(
                region=region,
                location=api_config.get("location"),
                radius_meters=api_config.get("radius_meters", 5000),
            )
        except (ValueError, requests.RequestException) as e:
            print(f"Warning: Failed to fetch from Google Places API: {e}")
            print("Falling back to fixture data")
            return _fixture_restaurants(region)
    else:
        print(f"Warning: Unknown restaurant source '{restaurant_source}', using fixtures")
        return _fixture_restaurants(region)


def _fetch_events(cfg: Mapping) -> List[Dict]:
    """Fetch events based on configured data source."""
    data_sources = cfg.get("data_sources", {})
    event_source = data_sources.get("events", "fixtures")
    region = cfg["region"]
    days_ahead = cfg.get("event_window_days", 30)
    
    if event_source == "fixtures":
        print(f"Using fixture data for events in {region}")
        return _fixture_events(region)
    elif event_source == "ticketmaster":
        print(f"Fetching events from Ticketmaster API for {region}")
        api_config = cfg.get("api_config", {}).get("ticketmaster", {})
        try:
            return fetch_ticketmaster_events(
                region=region,
                city=api_config.get("city"),
                state_code=api_config.get("state_code"),
                country_code=api_config.get("country_code", "US"),
                radius_miles=api_config.get("radius_miles", 25),
                days_ahead=days_ahead,
            )
        except (ValueError, requests.RequestException) as e:
            print(f"Warning: Failed to fetch from Ticketmaster API: {e}")
            print("Falling back to fixture data")
            return _fixture_events(region)
    elif event_source == "eventbrite":
        print(f"Fetching events from Eventbrite API for {region}")
        api_config = cfg.get("api_config", {}).get("eventbrite", {})
        try:
            return fetch_eventbrite_events(
                region=region,
                location_address=api_config.get("location_address"),
                location_within=api_config.get("location_within", "25mi"),
                days_ahead=days_ahead,
            )
        except (ValueError, requests.RequestException) as e:
            print(f"Warning: Failed to fetch from Eventbrite API: {e}")
            print("Falling back to fixture data")
            return _fixture_events(region)
    else:
        print(f"Warning: Unknown event source '{event_source}', using fixtures")
        return _fixture_events(region)


def aggregate(profile: str | None = None) -> Dict[str, Mapping]:
    cfg = load_config(profile)
    
    # Fetch data from configured sources
    restaurants = _fetch_restaurants(cfg)
    events = filter_events_by_window(_fetch_events(cfg), cfg["event_window_days"])

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


def write_json_raw(name: str, payload: Any) -> None:
    write_json(docs_path(name), payload)
