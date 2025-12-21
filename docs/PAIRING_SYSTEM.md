# Two-Phase Restaurant-Event Pairing System

This module implements a sophisticated two-phase matching system for pairing restaurants with events, designed to handle the reality that availability data (like OpenTable reservations) is unknown until the user checks in the browser.

## Overview

### Phase A: Fit Scoring (No Availability)
Ranks restaurants by how well they match the event based on:
- **Service Style**: Family-style/share-plates for family events (hard filter)
- **Travel Time**: Proximity to event location
- **Cuisine**: Match cuisine to event type (music, sports, family, etc.)
- **Group Signals**: Large tables, kids menu, private rooms, noise tolerance

Outputs time **windows** (not single times) with:
- Preferred window
- Fallback windows (earlier/later options)
- Target seat time

### Phase B: Availability Integration
Re-ranks restaurants when availability data arrives from the client:
- Intersects available times with recommended windows
- Scores based on window match (preferred > fallback1 > fallback2)
- Selects 1-3 recommended times closest to target
- Re-ranks by combined fit + availability score

## Quick Start

```python
from happenstance.pairing import (
    Event,
    Restaurant,
    AvailabilityPayload,
    rank_restaurants_for_event,
)

# Define event
event: Event = {
    "id": "show1",
    "type": "SHOW",
    "startAt": "2024-01-15T19:00:00+00:00",
    "mealIntent": "BEFORE_EVENT",
    "partySize": 2,
    "hasKids": False,
    "location": {"lat": 37.7749, "lng": -122.4194},
}

# Define restaurants
restaurants: list[Restaurant] = [
    {
        "id": "rest1",
        "name": "Italian Place",
        "location": {"lat": 37.7750, "lng": -122.4195},
        "cuisineTags": ["Italian"],
        "serviceStyleTags": ["casual"],
        "groupSignals": [],
    }
]

# Phase A: Rank by fit
travel_times = {"rest1": 10}  # minutes
phase_a = rank_restaurants_for_event(
    event, 
    restaurants, 
    travel_times_by_restaurant_id=travel_times
)

# Phase B: Add availability and re-rank
availability = [
    {
        "restaurantId": "rest1",
        "date": "2024-01-15",
        "partySize": 2,
        "availableTimes": ["17:00", "17:30", "18:00"],
    }
]
phase_b = rank_restaurants_for_event(
    event,
    restaurants,
    travel_times_by_restaurant_id=travel_times,
    availability_payloads=availability,
)
```

## Data Structures

### Event
```python
Event = {
    "id": str,
    "type": str,  # FAMILY_STYLE_GATHERING, SHOW, MEETING, DRINKS, etc.
    "location": {"lat": float, "lng": float},
    "startAt": str,  # ISO datetime
    "endAt": str | None,  # ISO datetime
    "durationMinutes": int | None,
    "mealIntent": "BEFORE_EVENT" | "AFTER_EVENT" | "MEAL_IS_EVENT",
    "partySize": int,
    "hasKids": bool,
    "travelMode": str | None,  # default "DRIVE"
}
```

### Restaurant
```python
Restaurant = {
    "id": str,
    "name": str,
    "location": {"lat": float, "lng": float},
    "cuisineTags": list[str],
    "serviceStyleTags": list[str],  # "family_style", "share_plates", etc.
    "groupSignals": list[str],  # "large_tables", "kids_menu", "private_room"
    "priceTier": int | None,
    "hours": dict | None,
}
```

### AvailabilityPayload
```python
AvailabilityPayload = {
    "restaurantId": str,
    "date": str,  # YYYY-MM-DD
    "partySize": int,
    "availableTimes": list[str],  # ["17:15", "17:45", "18:30"]
}
```

### PairingRecommendation (Output)
```python
PairingRecommendation = {
    "restaurantId": str,
    "score": float,  # 0-100
    "scoreBreakdown": {
        "serviceStyle": float,
        "travelTime": float,
        "cuisineDiet": float,
        "availabilityFit": float,
    },
    "recommendedWindows": {
        "preferred": {"startTime": str, "endTime": str},
        "fallbacks": [
            {"label": str, "startTime": str, "endTime": str}
        ],
    },
    "targetTime": str,  # HH:MM ideal seat time
    "availabilityPending": bool,
    "recommendedAvailableTimes": list[str] | None,
    "whyMatched": list[str],  # UI-friendly reasons
}
```

## Configuration

The `PairingConfig` class provides configurable defaults:

```python
from happenstance.pairing import PairingConfig

config = PairingConfig(
    # Travel time caps (minutes)
    travel_time_caps={
        "FAMILY_STYLE_GATHERING": 15,
        "BEFORE_EVENT_TIMED": 20,
        "AFTER_EVENT": 25,
        "MEAL_IS_EVENT": 35,
    },
    
    # Time buffers
    pre_buffer_minutes=10,
    pre_buffer_with_kids=15,
    exit_buffer_minutes=15,
    
    # Meal durations
    meal_duration_casual=90,
    meal_duration_nice=105,
    
    # Scoring weights (sum to 1.0)
    weight_service_style=0.35,
    weight_travel_time=0.25,
    weight_cuisine_diet=0.20,
    weight_availability=0.20,
    
    # Family-style enforcement
    require_family_style_for_family_events=True,
)
```

## Time Window Computation

### BEFORE_EVENT
For dinner before a 7 PM show:
1. Calculate latest finish: `event_start - travel_time - pre_buffer`
2. Calculate target seat: `latest_finish - meal_duration`
3. Create preferred window: `target ± 30 min`
4. Create fallbacks: earlier and later options (if time allows)

### AFTER_EVENT
For dinner after a 9 PM show:
1. Calculate earliest seat: `event_end + exit_buffer + travel_time + pre_buffer`
2. Create preferred window: `earliest_seat to +60 min`
3. Create fallbacks: later (+60-120 min) and earlier (-30 min)

### MEAL_IS_EVENT
For standalone dining:
- Standard windows: 6-7:30 PM (preferred), 7:30-8:30 PM, 5-6 PM
- With kids: 5-6:30 PM (preferred), 6:30-8 PM, 4-5 PM

## Scoring Details

### Service Style (35% weight)
- Family-style events **require** family_style or share_plates tags
- Bonuses for: large_tables (+5), kids_menu (+5 if hasKids), noise_tolerant (+3), private_room (+7 if party ≥ 8)

### Travel Time (25% weight)
- 0-10 min: 100 points
- 10-15 min: 85 points
- 15-20 min: 70 points
- 20-25 min: 50 points
- >25 min: decreasing

### Cuisine Fit (20% weight)
Simple tag matching with event type preferences:
- Music/shows: Italian, Mediterranean, American, Sushi
- Family: Italian, American, Mexican, Pizza
- Sports: American, BBQ, Pizza, Mexican

### Availability Fit (20% weight, Phase B only)
- 100 points: times in preferred window
- 66 points: times in fallback1
- 33 points: times in fallback2
- 0 points: no matching times

## Running Tests

```bash
# Run all pairing tests
pytest tests/test_pairing.py -v

# Run specific test class
pytest tests/test_pairing.py::TestComputeDiningWindows -v

# Run with coverage
pytest tests/test_pairing.py --cov=happenstance.pairing
```

## Demo

See the working demo:
```bash
python -m scripts.demo_pairing
```

This shows:
1. Family gathering with kids (8 people) - demonstrates family-style requirement
2. Pre-show dinner - demonstrates time window computation for BEFORE_EVENT
3. Both Phase A (no availability) and Phase B (with availability)

## Design Principles

1. **Deterministic**: Same inputs always produce same outputs
2. **Testable**: Pure functions with clear inputs/outputs
3. **Configurable**: All thresholds and weights in config
4. **Time Windows**: Never single times; always ranges with fallbacks
5. **No Backend Scraping**: Availability comes from client only
6. **Hard Filters**: Family events exclude non-family restaurants by default
7. **Stable Sorting**: Ties broken by travel time, then restaurant ID

## Future Enhancements

Potential additions (not in current scope):
- Dietary restriction filtering
- Price tier matching
- Operating hours validation
- Distance decay functions
- Multi-event itineraries
- Real-time availability updates
