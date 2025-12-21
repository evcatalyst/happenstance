"""
Two-phase restaurant-event pairing logic.

Phase A: Ranks restaurants by "fit" before availability is known.
Phase B: Re-ranks with availability data from the client/browser (e.g., OpenTable times).

The system computes recommended dining time windows (not single times) and provides
deterministic, testable scoring.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, TypedDict

# Type definitions for structured data


class Location(TypedDict):
    """Geographic location with latitude and longitude."""
    lat: float
    lng: float


class TimeWindow(TypedDict):
    """A time window with start and end times in HH:MM format."""
    startTime: str
    endTime: str


class FallbackWindow(TimeWindow):
    """A fallback time window with a label."""
    label: str


class RecommendedWindows(TypedDict):
    """Recommended dining time windows (preferred + fallbacks)."""
    preferred: TimeWindow
    fallbacks: List[FallbackWindow]


class ScoreBreakdown(TypedDict):
    """Breakdown of scoring components."""
    serviceStyle: float
    travelTime: float
    cuisineDiet: float
    availabilityFit: float


class Event(TypedDict, total=False):
    """Event data structure."""
    id: str
    type: str  # FAMILY_STYLE_GATHERING, SHOW, MEETING, DRINKS, etc.
    location: Location  # or could be address string
    address: Optional[str]  # if location is not geocoded yet
    startAt: str  # ISO datetime
    endAt: Optional[str]  # ISO datetime
    durationMinutes: Optional[int]
    mealIntent: Literal["BEFORE_EVENT", "AFTER_EVENT", "MEAL_IS_EVENT"]
    partySize: int
    hasKids: bool
    travelMode: Optional[str]


class Restaurant(TypedDict, total=False):
    """Restaurant data structure."""
    id: str
    name: str
    location: Location
    address: Optional[str]
    cuisineTags: List[str]
    serviceStyleTags: List[str]  # e.g., "family_style", "share_plates"
    groupSignals: List[str]  # e.g., "large_tables", "kids_menu", "private_room"
    priceTier: Optional[int]
    hours: Optional[Dict[str, Any]]


class AvailabilityPayload(TypedDict):
    """Availability data from the client (e.g., OpenTable scrape)."""
    restaurantId: str
    date: str  # YYYY-MM-DD
    partySize: int
    availableTimes: List[str]  # ["17:15", "17:45", "18:30"]


class PairingRecommendation(TypedDict):
    """Output recommendation for a restaurant-event pairing."""
    restaurantId: str
    score: float  # 0-100
    scoreBreakdown: ScoreBreakdown
    recommendedWindows: RecommendedWindows
    targetTime: str  # "HH:MM" ideal seat time
    availabilityPending: bool
    recommendedAvailableTimes: Optional[List[str]]  # populated in Phase B
    whyMatched: List[str]  # UI-friendly reasons


@dataclass
class PairingConfig:
    """Configuration for pairing algorithm with sensible defaults."""
    
    # Travel time caps (minutes) by event type / context
    travel_time_caps: Dict[str, int] = field(default_factory=lambda: {
        "FAMILY_STYLE_GATHERING": 15,
        "BEFORE_EVENT_TIMED": 20,
        "AFTER_EVENT": 25,
        "MEAL_IS_EVENT": 35,
        "DEFAULT": 25,
    })
    
    # Time buffers (minutes)
    pre_buffer_minutes: int = 10
    pre_buffer_with_kids: int = 15
    exit_buffer_minutes: int = 15
    exit_buffer_big_venue: int = 20
    
    # Meal durations (minutes)
    meal_duration_casual: int = 90
    meal_duration_nice: int = 105
    
    # Scoring weights (should sum to 1.0 or 100%)
    weight_service_style: float = 0.35
    weight_travel_time: float = 0.25
    weight_cuisine_diet: float = 0.20
    weight_availability: float = 0.20
    
    # Family-style handling
    require_family_style_for_family_events: bool = True
    
    # Default travel speed for distance approximation (mph)
    default_travel_speed_mph: float = 25.0


def _ceil_to_5_minutes(dt: datetime) -> datetime:
    """Round a datetime up to the nearest 5 minutes."""
    minutes = dt.minute
    remainder = minutes % 5
    if remainder == 0:
        return dt
    delta = 5 - remainder
    return dt + timedelta(minutes=delta)


def _format_time(dt: datetime) -> str:
    """Format datetime as HH:MM (24-hour format)."""
    return dt.strftime("%H:%M")


def _parse_time_to_minutes(time_str: str) -> int:
    """Parse HH:MM to minutes since midnight."""
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _minutes_to_time_str(minutes: int) -> str:
    """Convert minutes since midnight to HH:MM."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def compute_dining_windows(
    event: Event,
    travel_time_minutes: int,
    config: Optional[PairingConfig] = None,
) -> Dict[str, Any]:
    """
    Compute recommended dining time windows for an event.
    
    Args:
        event: Event details
        travel_time_minutes: Travel time from restaurant to event (or vice versa)
        config: Configuration (uses defaults if None)
    
    Returns:
        Dictionary with:
            - targetTime: str (HH:MM)
            - preferred: TimeWindow
            - fallbacks: List[FallbackWindow]
    """
    if config is None:
        config = PairingConfig()
    
    meal_intent = event.get("mealIntent", "BEFORE_EVENT")
    has_kids = event.get("hasKids", False)
    
    # Determine pre-buffer and meal duration
    pre_buffer = config.pre_buffer_with_kids if has_kids else config.pre_buffer_minutes
    
    # Estimate meal duration (could be refined with restaurant data)
    meal_duration = config.meal_duration_casual
    
    # Parse event start time
    start_at = datetime.fromisoformat(event["startAt"].replace("Z", "+00:00"))
    
    if meal_intent == "BEFORE_EVENT":
        # Latest finish = event start - travel time - pre-buffer
        latest_finish = start_at - timedelta(minutes=travel_time_minutes + pre_buffer)
        
        # Target seat time = latest finish - meal duration
        target_seat = latest_finish - timedelta(minutes=meal_duration)
        target_seat = _ceil_to_5_minutes(target_seat)
        
        # Preferred window: target ± 30 minutes
        preferred_start = target_seat - timedelta(minutes=30)
        preferred_end = target_seat + timedelta(minutes=30)
        
        # Fallback 1: 60 minutes earlier (only if still ends before event)
        fallback1_start = preferred_start - timedelta(minutes=60)
        fallback1_end = preferred_end - timedelta(minutes=60)
        
        # Fallback 2: 45 minutes later (only if ends before event start)
        fallback2_start = preferred_start + timedelta(minutes=45)
        fallback2_end = preferred_end + timedelta(minutes=45)
        # Ensure fallback2 still finishes before event
        if fallback2_end + timedelta(minutes=meal_duration) > latest_finish:
            fallback2_end = latest_finish - timedelta(minutes=meal_duration + 15)
            fallback2_start = fallback2_end - timedelta(minutes=60)
        
        return {
            "targetTime": _format_time(target_seat),
            "preferred": {
                "startTime": _format_time(preferred_start),
                "endTime": _format_time(preferred_end),
            },
            "fallbacks": [
                {
                    "label": "Earlier seating",
                    "startTime": _format_time(fallback1_start),
                    "endTime": _format_time(fallback1_end),
                },
                {
                    "label": "Later seating",
                    "startTime": _format_time(fallback2_start),
                    "endTime": _format_time(fallback2_end),
                },
            ],
        }
    
    elif meal_intent == "AFTER_EVENT":
        # Determine end time
        if "endAt" in event and event["endAt"]:
            end_at = datetime.fromisoformat(event["endAt"].replace("Z", "+00:00"))
        elif "durationMinutes" in event and event["durationMinutes"]:
            end_at = start_at + timedelta(minutes=event["durationMinutes"])
        else:
            # Default: assume 2-hour event
            end_at = start_at + timedelta(hours=2)
        
        # Earliest seat = event end + exit buffer + travel time + pre-buffer
        earliest_seat = end_at + timedelta(
            minutes=config.exit_buffer_minutes + travel_time_minutes + pre_buffer
        )
        earliest_seat = _ceil_to_5_minutes(earliest_seat)
        
        # Preferred window: earliest seat to +60 minutes
        preferred_start = earliest_seat
        preferred_end = earliest_seat + timedelta(minutes=60)
        
        # Fallback 1: +60 to +120 minutes
        fallback1_start = earliest_seat + timedelta(minutes=60)
        fallback1_end = earliest_seat + timedelta(minutes=120)
        
        # Fallback 2: -30 minutes (only if not before event end)
        fallback2_start = max(earliest_seat - timedelta(minutes=30), end_at + timedelta(minutes=pre_buffer))
        fallback2_end = fallback2_start + timedelta(minutes=60)
        
        return {
            "targetTime": _format_time(earliest_seat),
            "preferred": {
                "startTime": _format_time(preferred_start),
                "endTime": _format_time(preferred_end),
            },
            "fallbacks": [
                {
                    "label": "Later seating",
                    "startTime": _format_time(fallback1_start),
                    "endTime": _format_time(fallback1_end),
                },
                {
                    "label": "Earlier seating",
                    "startTime": _format_time(fallback2_start),
                    "endTime": _format_time(fallback2_end),
                },
            ],
        }
    
    else:  # MEAL_IS_EVENT
        # Default dinner windows
        # If kids, bias earlier
        if has_kids:
            preferred_start_time = "17:00"
            preferred_end_time = "18:30"
            fallback1_start_time = "18:30"
            fallback1_end_time = "20:00"
            fallback2_start_time = "16:00"
            fallback2_end_time = "17:00"
            target_time = "17:30"
        else:
            preferred_start_time = "18:00"
            preferred_end_time = "19:30"
            fallback1_start_time = "19:30"
            fallback1_end_time = "20:30"
            fallback2_start_time = "17:00"
            fallback2_end_time = "18:00"
            target_time = "18:30"
        
        return {
            "targetTime": target_time,
            "preferred": {
                "startTime": preferred_start_time,
                "endTime": preferred_end_time,
            },
            "fallbacks": [
                {
                    "label": "Later seating",
                    "startTime": fallback1_start_time,
                    "endTime": fallback1_end_time,
                },
                {
                    "label": "Earlier seating",
                    "startTime": fallback2_start_time,
                    "endTime": fallback2_end_time,
                },
            ],
        }


def _is_family_style_event(event: Event) -> bool:
    """Determine if an event requires family-style dining."""
    event_type = event.get("type", "").upper()
    if "FAMILY" in event_type:
        return True
    if event.get("hasKids", False) and event.get("partySize", 1) >= 4:
        return True
    if event.get("partySize", 1) >= 6:
        return True
    return False


def score_restaurant_fit(
    event: Event,
    restaurant: Restaurant,
    travel_time_minutes: int,
    config: Optional[PairingConfig] = None,
) -> Dict[str, Any]:
    """
    Score how well a restaurant fits an event (Phase A, no availability).
    
    Args:
        event: Event details
        restaurant: Restaurant details
        travel_time_minutes: Travel time in minutes
        config: Configuration (uses defaults if None)
    
    Returns:
        Dictionary with:
            - totalScore: float (0-100)
            - breakdown: ScoreBreakdown
            - reasons: List[str] (UI-friendly)
            - excluded: bool (True if hard-filtered)
    """
    if config is None:
        config = PairingConfig()
    
    breakdown: ScoreBreakdown = {
        "serviceStyle": 0.0,
        "travelTime": 0.0,
        "cuisineDiet": 0.0,
        "availabilityFit": 0.0,
    }
    reasons: List[str] = []
    
    # Check family-style requirement
    requires_family_style = _is_family_style_event(event)
    has_family_style = any(
        tag in restaurant.get("serviceStyleTags", [])
        for tag in ["family_style", "share_plates"]
    )
    
    if requires_family_style and not has_family_style:
        if config.require_family_style_for_family_events:
            # Hard filter: exclude this restaurant
            return {
                "totalScore": 0.0,
                "breakdown": breakdown,
                "reasons": ["Not family-style or share-plates"],
                "excluded": True,
            }
        else:
            # Soft penalty
            breakdown["serviceStyle"] = 10.0
            reasons.append("Not family-style dining")
    else:
        # Base service style score
        if has_family_style and requires_family_style:
            breakdown["serviceStyle"] = 90.0
            reasons.append("Family-style dining")
        elif has_family_style:
            breakdown["serviceStyle"] = 70.0
            reasons.append("Share plates available")
        else:
            breakdown["serviceStyle"] = 50.0
        
        # Bonuses for group signals
        group_signals = restaurant.get("groupSignals", [])
        bonus = 0.0
        if "large_tables" in group_signals:
            bonus += 5.0
            reasons.append("Large tables available")
        if "kids_menu" in group_signals and event.get("hasKids", False):
            bonus += 5.0
            reasons.append("Kids menu available")
        if "noise_tolerant" in group_signals:
            bonus += 3.0
        if "private_room" in group_signals and event.get("partySize", 1) >= 8:
            bonus += 7.0
            reasons.append("Private room available")
        
        breakdown["serviceStyle"] = min(100.0, breakdown["serviceStyle"] + bonus)
    
    # Travel time score
    if travel_time_minutes <= 10:
        breakdown["travelTime"] = 100.0
        reasons.append(f"{travel_time_minutes} min away - very close")
    elif travel_time_minutes <= 15:
        breakdown["travelTime"] = 85.0
        reasons.append(f"{travel_time_minutes} min away")
    elif travel_time_minutes <= 20:
        breakdown["travelTime"] = 70.0
        reasons.append(f"{travel_time_minutes} min drive")
    elif travel_time_minutes <= 25:
        breakdown["travelTime"] = 50.0
        reasons.append(f"{travel_time_minutes} min away")
    else:
        breakdown["travelTime"] = max(0.0, 100.0 - (travel_time_minutes - 25) * 3)
        if breakdown["travelTime"] > 0:
            reasons.append(f"{travel_time_minutes} min drive - far")
    
    # Cuisine fit (simple overlap for now)
    event_type = event.get("type", "").lower()
    cuisines = [c.lower() for c in restaurant.get("cuisineTags", [])]
    cuisine_score = 50.0  # baseline
    
    # Match event type with cuisine preferences
    if "music" in event_type or "show" in event_type:
        if any(c in cuisines for c in ["italian", "mediterranean", "american", "sushi"]):
            cuisine_score = 80.0
            reasons.append("Great for pre-show dining")
    elif "family" in event_type:
        if any(c in cuisines for c in ["italian", "american", "mexican", "pizza"]):
            cuisine_score = 85.0
            reasons.append("Family-friendly cuisine")
    elif "sports" in event_type:
        if any(c in cuisines for c in ["american", "bbq", "pizza", "mexican"]):
            cuisine_score = 80.0
            reasons.append("Perfect sports dining")
    
    breakdown["cuisineDiet"] = cuisine_score
    
    # Availability fit = 0 in Phase A
    breakdown["availabilityFit"] = 0.0
    
    # Compute total score
    total_score = (
        breakdown["serviceStyle"] * config.weight_service_style +
        breakdown["travelTime"] * config.weight_travel_time +
        breakdown["cuisineDiet"] * config.weight_cuisine_diet +
        breakdown["availabilityFit"] * config.weight_availability
    )
    
    return {
        "totalScore": total_score,
        "breakdown": breakdown,
        "reasons": reasons,
        "excluded": False,
    }


def _time_in_window(time_str: str, window_start: str, window_end: str) -> bool:
    """Check if a time falls within a window."""
    time_mins = _parse_time_to_minutes(time_str)
    start_mins = _parse_time_to_minutes(window_start)
    end_mins = _parse_time_to_minutes(window_end)
    return start_mins <= time_mins <= end_mins


def _closest_to_target(times: List[str], target: str) -> List[str]:
    """Find up to 3 times closest to target."""
    target_mins = _parse_time_to_minutes(target)
    times_with_dist = [(t, abs(_parse_time_to_minutes(t) - target_mins)) for t in times]
    times_with_dist.sort(key=lambda x: x[1])
    return [t for t, _ in times_with_dist[:3]]


def apply_availability(
    recommendations: List[PairingRecommendation],
    availability_payloads: List[AvailabilityPayload],
    event: Event,
    config: Optional[PairingConfig] = None,
) -> List[PairingRecommendation]:
    """
    Apply availability data to recommendations and re-rank (Phase B).
    
    Args:
        recommendations: Phase A recommendations
        availability_payloads: List of availability data from client
        event: Event details
        config: Configuration
    
    Returns:
        Updated and re-ranked recommendations
    """
    if config is None:
        config = PairingConfig()
    
    # Build availability lookup
    availability_map: Dict[str, AvailabilityPayload] = {
        av["restaurantId"]: av for av in availability_payloads
    }
    
    updated_recommendations: List[PairingRecommendation] = []
    
    for rec in recommendations:
        restaurant_id = rec["restaurantId"]
        
        if restaurant_id not in availability_map:
            # No availability data for this restaurant
            updated_recommendations.append(rec)
            continue
        
        availability = availability_map[restaurant_id]
        available_times = availability["availableTimes"]
        
        if not available_times:
            # No available times
            rec["availabilityPending"] = False
            rec["recommendedAvailableTimes"] = []
            rec["scoreBreakdown"]["availabilityFit"] = 0.0
            # Recompute total score
            breakdown = rec["scoreBreakdown"]
            rec["score"] = (
                breakdown["serviceStyle"] * config.weight_service_style +
                breakdown["travelTime"] * config.weight_travel_time +
                breakdown["cuisineDiet"] * config.weight_cuisine_diet +
                breakdown["availabilityFit"] * config.weight_availability
            )
            updated_recommendations.append(rec)
            continue
        
        # Score availability fit
        windows = rec["recommendedWindows"]
        preferred = windows["preferred"]
        fallbacks = windows["fallbacks"]
        target_time = rec["targetTime"]
        
        # Check which available times fall in which windows
        times_in_preferred = [
            t for t in available_times
            if _time_in_window(t, preferred["startTime"], preferred["endTime"])
        ]
        times_in_fallback1 = []
        times_in_fallback2 = []
        
        if len(fallbacks) >= 1:
            times_in_fallback1 = [
                t for t in available_times
                if _time_in_window(t, fallbacks[0]["startTime"], fallbacks[0]["endTime"])
            ]
        if len(fallbacks) >= 2:
            times_in_fallback2 = [
                t for t in available_times
                if _time_in_window(t, fallbacks[1]["startTime"], fallbacks[1]["endTime"])
            ]
        
        # Compute availability fit score
        if times_in_preferred:
            availability_fit_raw = 100.0
            recommended_times = _closest_to_target(times_in_preferred, target_time)
        elif times_in_fallback1:
            availability_fit_raw = 66.0
            recommended_times = _closest_to_target(times_in_fallback1, target_time)
        elif times_in_fallback2:
            availability_fit_raw = 33.0
            recommended_times = _closest_to_target(times_in_fallback2, target_time)
        else:
            availability_fit_raw = 0.0
            recommended_times = _closest_to_target(available_times, target_time)
        
        # Update recommendation
        rec["availabilityPending"] = False
        rec["recommendedAvailableTimes"] = recommended_times
        rec["scoreBreakdown"]["availabilityFit"] = availability_fit_raw
        
        # Recompute total score
        breakdown = rec["scoreBreakdown"]
        rec["score"] = (
            breakdown["serviceStyle"] * config.weight_service_style +
            breakdown["travelTime"] * config.weight_travel_time +
            breakdown["cuisineDiet"] * config.weight_cuisine_diet +
            breakdown["availabilityFit"] * config.weight_availability
        )
        
        updated_recommendations.append(rec)
    
    # Re-sort by score (descending), then by travel time (descending = closer), then by name (ascending)
    updated_recommendations.sort(
        key=lambda r: (
            -r["score"],
            -r["scoreBreakdown"]["travelTime"],  # Higher travel score = closer
            r["restaurantId"]
        )
    )
    
    return updated_recommendations


def rank_restaurants_for_event(
    event: Event,
    restaurants: List[Restaurant],
    travel_times_by_restaurant_id: Optional[Dict[str, int]] = None,
    config: Optional[PairingConfig] = None,
    availability_payloads: Optional[List[AvailabilityPayload]] = None,
) -> List[PairingRecommendation]:
    """
    Rank restaurants for an event.
    
    Phase A (no availability): Ranks by fit scores.
    Phase B (with availability): Applies availability and re-ranks.
    
    Args:
        event: Event details
        restaurants: List of candidate restaurants
        travel_times_by_restaurant_id: Optional mapping of restaurant ID to travel time (minutes)
        config: Configuration (uses defaults if None)
        availability_payloads: Optional list of availability data (triggers Phase B)
    
    Returns:
        Sorted list of PairingRecommendation objects
    """
    if config is None:
        config = PairingConfig()
    
    if travel_times_by_restaurant_id is None:
        travel_times_by_restaurant_id = {}
    
    recommendations: List[PairingRecommendation] = []
    
    for restaurant in restaurants:
        restaurant_id = restaurant["id"]
        
        # Get travel time (or approximate from distance)
        travel_time = travel_times_by_restaurant_id.get(restaurant_id)
        
        if travel_time is None:
            # Approximate using haversine if both have location
            if "location" in event and "location" in restaurant:
                event_loc = event["location"]
                rest_loc = restaurant["location"]
                distance_miles = _haversine_distance(
                    event_loc["lat"], event_loc["lng"],
                    rest_loc["lat"], rest_loc["lng"]
                )
                # Approximate travel time
                travel_time = int((distance_miles / config.default_travel_speed_mph) * 60)
            else:
                # Default fallback
                travel_time = 20
        
        # Compute dining windows
        windows = compute_dining_windows(event, travel_time, config)
        
        # Score the restaurant fit
        fit_result = score_restaurant_fit(event, restaurant, travel_time, config)
        
        if fit_result["excluded"]:
            # Skip excluded restaurants
            continue
        
        # Build recommendation
        recommendation: PairingRecommendation = {
            "restaurantId": restaurant_id,
            "score": fit_result["totalScore"],
            "scoreBreakdown": fit_result["breakdown"],
            "recommendedWindows": {
                "preferred": windows["preferred"],
                "fallbacks": windows["fallbacks"],
            },
            "targetTime": windows["targetTime"],
            "availabilityPending": True,
            "recommendedAvailableTimes": None,
            "whyMatched": fit_result["reasons"],
        }
        
        recommendations.append(recommendation)
    
    # Sort by score (descending), then travel time score (descending), then restaurant ID
    recommendations.sort(
        key=lambda r: (
            -r["score"],
            -r["scoreBreakdown"]["travelTime"],
            r["restaurantId"]
        )
    )
    
    # Phase B: Apply availability if provided
    if availability_payloads:
        recommendations = apply_availability(recommendations, availability_payloads, event, config)
    
    return recommendations


def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate distance between two coordinates using Haversine formula.
    
    Returns:
        Distance in miles
    """
    R = 3959.0  # Earth radius in miles
    
    lat1_rad = math.radians(lat1)
    lng1_rad = math.radians(lng1)
    lat2_rad = math.radians(lat2)
    lng2_rad = math.radians(lng2)
    
    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad
    
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c
