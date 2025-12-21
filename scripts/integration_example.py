"""
Optional integration example for using the two-phase pairing system in aggregate.py.

This is a REFERENCE IMPLEMENTATION showing how to integrate the new pairing system
with the existing codebase. It is NOT required - the existing pairing logic continues
to work.

The new pairing system is designed to be used separately, particularly for:
1. Frontend applications that need availability-aware recommendations
2. Systems that can provide OpenTable/booking availability data
3. Advanced filtering (family-style requirements, time windows, etc.)
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from happenstance.pairing import (
    AvailabilityPayload,
    Event,
    PairingConfig,
    Restaurant,
    rank_restaurants_for_event,
)


def convert_legacy_event_to_pairing_event(legacy_event: Dict) -> Event:
    """
    Convert a legacy event dict to the new Event structure.
    
    Args:
        legacy_event: Event from aggregate.py (has title, category, date, location)
    
    Returns:
        Event object for pairing system
    """
    # Parse event datetime
    event_date = legacy_event.get("date", "")
    if event_date:
        start_at = datetime.fromisoformat(event_date.replace("Z", "+00:00"))
    else:
        start_at = datetime.now(timezone.utc)
    
    # Infer event type from category
    category = legacy_event.get("category", "").lower()
    if "family" in category or "kids" in legacy_event.get("title", "").lower():
        event_type = "FAMILY_STYLE_GATHERING"
        meal_intent = "MEAL_IS_EVENT"
        has_kids = True
    elif "music" in category or "concert" in category:
        event_type = "SHOW"
        meal_intent = "BEFORE_EVENT"
        has_kids = False
    elif "sports" in category:
        event_type = "SPORTS"
        meal_intent = "BEFORE_EVENT"
        has_kids = False
    else:
        event_type = "MEETING"
        meal_intent = "BEFORE_EVENT"
        has_kids = False
    
    # Extract location (may need geocoding)
    # For now, use placeholder coordinates (in production, use geocoding from location_str)
    # location_str = legacy_event.get("location", "")
    location = {"lat": 37.7749, "lng": -122.4194}
    
    return {
        "id": legacy_event.get("title", "event")[:50],
        "type": event_type,
        "location": location,
        "startAt": start_at.isoformat(),
        "mealIntent": meal_intent,
        "partySize": 4,  # Default, could be user preference
        "hasKids": has_kids,
    }


def convert_legacy_restaurant_to_pairing_restaurant(legacy_rest: Dict) -> Restaurant:
    """
    Convert a legacy restaurant dict to the new Restaurant structure.
    
    Args:
        legacy_rest: Restaurant from aggregate.py (has name, cuisine, address)
    
    Returns:
        Restaurant object for pairing system
    """
    # Extract cuisine tags
    cuisine = legacy_rest.get("cuisine", "Restaurant")
    cuisine_tags = [cuisine] if cuisine != "Restaurant" else []
    
    # Infer service style from cuisine/name
    name_lower = legacy_rest.get("name", "").lower()
    cuisine_lower = cuisine.lower()
    
    service_style_tags = []
    group_signals = []
    
    # Heuristics for service style
    if any(word in name_lower or word in cuisine_lower for word in ["family", "tavern", "grill"]):
        service_style_tags.append("family_style")
        group_signals.append("large_tables")
    elif any(word in name_lower or word in cuisine_lower for word in ["tapas", "mezze", "dim sum"]):
        service_style_tags.append("share_plates")
    else:
        service_style_tags.append("casual")
    
    # Infer group signals
    if any(word in name_lower for word in ["family", "kids"]):
        group_signals.append("kids_menu")
    if "bbq" in cuisine_lower or "pizza" in cuisine_lower:
        group_signals.append("noise_tolerant")
    
    # Use placeholder location (in production, use geocoding from address)
    location = {"lat": 37.7750, "lng": -122.4195}
    
    return {
        "id": legacy_rest.get("name", "restaurant"),
        "name": legacy_rest.get("name", "Unknown"),
        "location": location,
        "cuisineTags": cuisine_tags,
        "serviceStyleTags": service_style_tags,
        "groupSignals": group_signals,
    }


def enhanced_pairing_with_availability(
    events: List[Dict],
    restaurants: List[Dict],
    availability_data: Optional[List[AvailabilityPayload]] = None,
    config: Optional[PairingConfig] = None,
) -> List[Dict]:
    """
    Enhanced pairing that uses the new two-phase system.
    
    This is an EXAMPLE of how to integrate the new pairing system.
    It can coexist with the existing _build_pairings function.
    
    Args:
        events: Legacy event dicts
        restaurants: Legacy restaurant dicts
        availability_data: Optional availability from frontend
        config: Optional pairing configuration
    
    Returns:
        List of enhanced pairing dicts with time windows and scores
    """
    if config is None:
        config = PairingConfig()
    
    enhanced_pairings = []
    
    for event in events:
        # Convert to new format
        pairing_event = convert_legacy_event_to_pairing_event(event)
        pairing_restaurants = [
            convert_legacy_restaurant_to_pairing_restaurant(r) 
            for r in restaurants
        ]
        
        # Rank restaurants for this event
        recommendations = rank_restaurants_for_event(
            pairing_event,
            pairing_restaurants,
            config=config,
            availability_payloads=availability_data,
        )
        
        if not recommendations:
            continue
        
        # Take top recommendation
        top_rec = recommendations[0]
        top_restaurant = next(
            (r for r in restaurants if r["name"] == top_rec["restaurantId"]),
            None
        )
        
        if not top_restaurant:
            continue
        
        # Build enhanced pairing
        pairing = {
            "event": event["title"],
            "restaurant": top_restaurant["name"],
            "match_reason": "; ".join(top_rec["whyMatched"]),
            "event_url": event.get("url"),
            "restaurant_url": top_restaurant.get("url"),
            "event_date": event.get("date"),
            "event_location": event.get("location"),
            # Enhanced fields from new system
            "score": top_rec["score"],
            "score_breakdown": top_rec["scoreBreakdown"],
            "target_time": top_rec["targetTime"],
            "recommended_windows": top_rec["recommendedWindows"],
            "availability_pending": top_rec["availabilityPending"],
            "recommended_times": top_rec.get("recommendedAvailableTimes"),
        }
        
        enhanced_pairings.append(pairing)
    
    return enhanced_pairings


# Example usage (for documentation/testing purposes)
if __name__ == "__main__":
    # Mock data
    events = [
        {
            "title": "Family Picnic",
            "category": "family",
            "date": "2024-01-20T14:00:00Z",
            "location": "Central Park",
            "url": "https://example.com/picnic",
        }
    ]
    
    restaurants = [
        {
            "name": "Family Italian Restaurant",
            "cuisine": "Italian",
            "address": "123 Main St",
            "url": "https://example.com/italian",
        }
    ]
    
    # Phase A: Without availability
    print("Phase A - Without Availability:")
    pairings_a = enhanced_pairing_with_availability(events, restaurants)
    for p in pairings_a:
        print(f"  {p['event']} → {p['restaurant']}")
        print(f"  Score: {p['score']:.1f}, Target: {p['target_time']}")
        print(f"  Window: {p['recommended_windows']['preferred']}")
    
    # Phase B: With availability
    print("\nPhase B - With Availability:")
    availability = [
        {
            "restaurantId": "Family Italian Restaurant",
            "date": "2024-01-20",
            "partySize": 4,
            "availableTimes": ["13:00", "13:30", "14:00"],
        }
    ]
    pairings_b = enhanced_pairing_with_availability(events, restaurants, availability)
    for p in pairings_b:
        print(f"  {p['event']} → {p['restaurant']}")
        print(f"  Score: {p['score']:.1f}")
        print(f"  Recommended Times: {p['recommended_times']}")
