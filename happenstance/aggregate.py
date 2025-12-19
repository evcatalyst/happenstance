from __future__ import annotations

import math
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping

from .config import load_config
from .hash import compute_meta
from .io import append_meta, docs_path, read_json, write_json
from .prompting import build_gap_bullets, month_spread_guidance
from .search import build_live_search_params
from .sources import (
    _infer_cuisine,
    _make_request,
    fetch_ai_events,
    fetch_ai_restaurants,
    fetch_eventbrite_events,
    fetch_google_places_restaurants,
    fetch_ticketmaster_events,
)
from .validate import filter_events_by_window

# Constants for nearby restaurant search
NEARBY_RESTAURANT_RADIUS_METERS = 800.0  # ~0.5 miles
MAX_NEARBY_RESTAURANTS_PER_EVENT = 3

# Google Places price level mapping
PRICE_LEVEL_MAP = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


def _build_google_maps_url(place_id: str | None, name: str, location: str) -> str:
    """
    Build a Google Maps URL for a place.
    
    Args:
        place_id: Google Places ID if available
        name: Name of the place
        location: Location/city string
        
    Returns:
        Google Maps URL
    """
    if place_id:
        return f"https://www.google.com/maps/place/?q=place_id:{place_id}"
    return f"https://www.google.com/search?q={urllib.parse.quote(name)}+{urllib.parse.quote(location)}"


def _geocode_address(address: str) -> tuple[float, float] | None:
    """
    Geocode an address using Google Maps Geocoding API.
    
    Args:
        address: Address string to geocode
        
    Returns:
        Tuple of (latitude, longitude) or None if geocoding fails
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        return None
    
    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
        data = _make_request(url)
        
        if data.get("status") == "OK" and data.get("results"):
            location = data["results"][0]["geometry"]["location"]
            return (location["lat"], location["lng"])
    except Exception:
        pass
    
    return None


def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two coordinates using Haversine formula.
    
    Args:
        lat1, lon1: First coordinate (latitude, longitude)
        lat2, lon2: Second coordinate (latitude, longitude)
        
    Returns:
        Distance in miles
    """
    # Radius of Earth in miles
    R = 3959.0
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def _fetch_nearby_restaurants(event_location: str, count: int = 5) -> List[Dict]:
    """
    Fetch restaurants near a specific event location.
    
    Args:
        event_location: Event location string
        count: Number of nearby restaurants to fetch
        
    Returns:
        List of restaurant dictionaries
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        return []
    
    # First geocode the event location
    coords = _geocode_address(event_location)
    if not coords:
        return []
    
    lat, lng = coords
    
    # Use Places API Nearby Search
    url = "https://places.googleapis.com/v1/places:searchNearby"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.types,places.rating,places.priceLevel,places.id",
    }
    
    body = {
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": lat,
                    "longitude": lng
                },
                "radius": NEARBY_RESTAURANT_RADIUS_METERS
            }
        },
        "includedTypes": ["restaurant"],
        "maxResultCount": min(count, 20),
    }
    
    try:
        data = _make_request(url, headers=headers, method="POST", data=body)
    except Exception:
        return []
    
    restaurants = []
    places = data.get("places", [])
    
    for place in places[:count]:
        name = place.get("displayName", {}).get("text", "Unknown")
        address = place.get("formattedAddress", event_location)
        place_id = place.get("id", "")
        
        # Build Google Maps URL
        url = _build_google_maps_url(place_id, name, event_location)
        
        restaurant = {
            "name": name,
            "cuisine": _infer_cuisine(place),
            "address": address,
            "url": url,
            "match_reason": "Near event location",
        }
        
        # Add rating if available
        if "rating" in place:
            restaurant["rating"] = place["rating"]
        
        # Add price level if available
        if "priceLevel" in place:
            restaurant["price_level"] = PRICE_LEVEL_MAP.get(place["priceLevel"], 2)
        
        restaurants.append(restaurant)
    
    return restaurants


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


def _compute_match_score(event: Dict, restaurant: Dict, distance_miles: float | None = None) -> tuple[int, str]:
    score = 0
    reasons: List[str] = []
    category = event.get("category", "").lower()
    cuisine = restaurant.get("cuisine", "").lower()
    title = event.get("title", "").lower()
    match_reason = restaurant.get("match_reason", "")
    location = event.get("location", "").lower()
    address = restaurant.get("address", "").lower()

    # Distance-based scoring (if available)
    if distance_miles is not None:
        if distance_miles < 0.5:
            score += 5
            reasons.append("Very close to event")
        elif distance_miles < 1.0:
            score += 3
            reasons.append("Walking distance")
        elif distance_miles < 3.0:
            score += 1
            reasons.append("Short drive")

    # Match category with cuisine
    if category and cuisine:
        if category in cuisine or cuisine in category:
            score += 3
            reasons.append("Cuisine matches event type")
        # Special category matches
        if "music" in category and any(k in cuisine for k in ["jazz", "american", "mediterranean"]):
            score += 2
            reasons.append("Great dining for music events")
        if "art" in category and any(k in cuisine for k in ["italian", "french", "contemporary"]):
            score += 2
            reasons.append("Sophisticated dining for art events")
        if "sports" in category and any(k in cuisine for k in ["american", "bbq", "pizza", "mexican"]):
            score += 2
            reasons.append("Casual dining for sports events")

    # Family-friendly matching
    if "family" in title or "kids" in title or "family" in category:
        if "family" in match_reason.lower() or any(k in cuisine for k in ["pizza", "american", "italian"]):
            score += 2
            reasons.append("Family-friendly pairing")

    # Late night events
    if "night" in title or "late" in title or "evening" in title:
        if "late" in match_reason.lower() or "sushi" in cuisine or "contemporary" in cuisine:
            score += 1
            reasons.append("Good for evening events")

    # Location proximity (simple string matching)
    if location and address:
        # Extract neighborhood/district names
        for neighborhood in ["downtown", "waterfront", "financial", "mission", "castro", "fillmore", "pacific"]:
            if neighborhood in location and neighborhood in address:
                score += 3
                reasons.append("Same neighborhood")
                break

    # High-quality restaurants get a bonus
    rating = restaurant.get("rating", 0)
    if rating >= 4.7:
        score += 2
        reasons.append("Highly rated")
    elif rating >= 4.5:
        score += 1
        reasons.append("Well rated")

    # Add variety - use a hash of cuisine to spread choices
    cuisine_variety_score = hash(cuisine) % 3
    score += cuisine_variety_score

    if not reasons:
        reasons.append(match_reason or "Nearby and reliable")

    return score, "; ".join(reasons)


def _build_pairings(events: List[Dict], restaurants: List[Dict]) -> List[Dict]:
    if not restaurants:
        return []
    pairings: List[Dict] = []
    
    # Cache geocoded locations to avoid redundant API calls
    location_cache: Dict[str, tuple[float, float] | None] = {}
    
    for event in events:
        event_location = event.get("location", "")
        
        # Get event coordinates
        event_coords = None
        if event_location and event_location not in location_cache:
            location_cache[event_location] = _geocode_address(event_location)
        event_coords = location_cache.get(event_location)
        
        # Fetch nearby restaurants for this event
        nearby_restaurants = _fetch_nearby_restaurants(event_location, count=MAX_NEARBY_RESTAURANTS_PER_EVENT)
        
        # Combine nearby restaurants with the main restaurant list
        # Prefer nearby restaurants but allow fallback to main list
        all_restaurants = nearby_restaurants + restaurants
        
        best_score = float("-inf")
        best_restaurant: Dict | None = None
        best_reason = ""
        best_distance: float | None = None
        
        for restaurant in all_restaurants:
            restaurant_address = restaurant.get("address", "")
            
            # Calculate distance if both coordinates are available
            distance_miles = None
            if event_coords and restaurant_address:
                if restaurant_address not in location_cache:
                    location_cache[restaurant_address] = _geocode_address(restaurant_address)
                restaurant_coords = location_cache.get(restaurant_address)
                
                if restaurant_coords:
                    distance_miles = _calculate_distance(
                        event_coords[0], event_coords[1],
                        restaurant_coords[0], restaurant_coords[1]
                    )
            
            score, reason = _compute_match_score(event, restaurant, distance_miles)
            if score > best_score:
                best_score = score
                best_restaurant = restaurant
                best_reason = reason
                best_distance = distance_miles
        
        pairing = {
            "event": event["title"],
            "restaurant": best_restaurant["name"] if best_restaurant else "",
            "match_reason": best_reason,
            "event_url": event.get("url"),
            "restaurant_url": best_restaurant.get("url") if best_restaurant else None,
        }
        
        # Add distance if available
        if best_distance is not None:
            pairing["distance_miles"] = round(best_distance, 1)
        
        # Add nearby restaurant options
        if nearby_restaurants:
            pairing["nearby_restaurants"] = [
                {
                    "name": r["name"],
                    "cuisine": r["cuisine"],
                    "url": r["url"],
                    "rating": r.get("rating"),
                }
                for r in nearby_restaurants[:MAX_NEARBY_RESTAURANTS_PER_EVENT]
            ]
        
        pairings.append(pairing)
    
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
        city = api_config.get("city", region)
        try:
            return fetch_google_places_restaurants(
                city=city,
                region=region,
                cuisine_types=cfg.get("target_cuisines"),
                count=api_config.get("count", 20),
            )
        except ValueError as e:
            print(f"Warning: Failed to fetch from Google Places API: {e}")
            print("Falling back to fixture data")
            return _fixture_restaurants(region)
    elif restaurant_source == "ai":
        print(f"Fetching restaurants using AI-powered search for {region}")
        api_config = cfg.get("api_config", {}).get("ai", {})
        try:
            return fetch_ai_restaurants(
                region=region,
                city=api_config.get("city"),
                cuisine_types=cfg.get("target_cuisines"),
                count=api_config.get("restaurant_count", 20),
            )
        except ValueError as e:
            print(f"Warning: Failed to fetch from AI: {e}")
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
        city = api_config.get("city", region)
        try:
            return fetch_ticketmaster_events(
                city=city,
                region=region,
                categories=cfg.get("target_categories"),
                days_ahead=days_ahead,
                count=api_config.get("count", 20),
            )
        except ValueError as e:
            print(f"Warning: Failed to fetch from Ticketmaster API: {e}")
            print("Falling back to fixture data")
            return _fixture_events(region)
    elif event_source == "eventbrite":
        print(f"Fetching events from Eventbrite API for {region}")
        api_config = cfg.get("api_config", {}).get("eventbrite", {})
        city = api_config.get("city", region)
        try:
            return fetch_eventbrite_events(
                city=city,
                region=region,
                categories=cfg.get("target_categories"),
                days_ahead=days_ahead,
                count=api_config.get("count", 20),
            )
        except ValueError as e:
            print(f"Warning: Failed to fetch from Eventbrite API: {e}")
            print("Falling back to fixture data")
            return _fixture_events(region)
    elif event_source == "ai":
        print(f"Fetching events using AI-powered search for {region}")
        api_config = cfg.get("api_config", {}).get("ai", {})
        try:
            return fetch_ai_events(
                region=region,
                city=api_config.get("city"),
                categories=cfg.get("target_categories"),
                days_ahead=days_ahead,
                count=api_config.get("event_count", 20),
            )
        except ValueError as e:
            print(f"Warning: Failed to fetch from AI: {e}")
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
