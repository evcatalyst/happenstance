#!/usr/bin/env python3
"""
Demo script showing the two-phase restaurant-event pairing system.

This demonstrates:
- Phase A: Ranking restaurants by fit before availability is known
- Phase B: Re-ranking with availability data
"""

from datetime import datetime, timedelta, timezone

from happenstance.pairing import (
    AvailabilityPayload,
    Event,
    Restaurant,
    rank_restaurants_for_event,
)


def demo_family_gathering():
    """Demo: Family gathering requiring family-style dining."""
    print("=" * 80)
    print("DEMO: Family Gathering (8 people with kids)")
    print("=" * 80)
    
    # Event: Family gathering at 6 PM
    event: Event = {
        "id": "family-dinner-1",
        "type": "FAMILY_STYLE_GATHERING",
        "startAt": (datetime.now(timezone.utc) + timedelta(days=3)).replace(hour=18, minute=0).isoformat(),
        "mealIntent": "MEAL_IS_EVENT",
        "partySize": 8,
        "hasKids": True,
        "location": {"lat": 37.7749, "lng": -122.4194},
    }
    
    # Restaurants (mix of family-style and non-family-style)
    restaurants: list[Restaurant] = [
        {
            "id": "italian-family-rest",
            "name": "Bella Famiglia",
            "location": {"lat": 37.7750, "lng": -122.4195},
            "cuisineTags": ["Italian"],
            "serviceStyleTags": ["family_style"],
            "groupSignals": ["large_tables", "kids_menu", "noise_tolerant"],
        },
        {
            "id": "tapas-share-rest",
            "name": "Barcelona Tapas",
            "location": {"lat": 37.7751, "lng": -122.4196},
            "cuisineTags": ["Spanish"],
            "serviceStyleTags": ["share_plates"],
            "groupSignals": ["large_tables", "noise_tolerant"],
        },
        {
            "id": "fancy-french",
            "name": "Le Petit Paris",
            "location": {"lat": 37.7752, "lng": -122.4197},
            "cuisineTags": ["French"],
            "serviceStyleTags": ["fine_dining"],
            "groupSignals": [],
        },
    ]
    
    # Travel times (in minutes)
    travel_times = {
        "italian-family-rest": 8,
        "tapas-share-rest": 12,
        "fancy-french": 10,
    }
    
    print("\n--- PHASE A: Ranking by Fit (No Availability) ---")
    phase_a_results = rank_restaurants_for_event(
        event,
        restaurants,
        travel_times_by_restaurant_id=travel_times,
    )
    
    print(f"\nFound {len(phase_a_results)} matching restaurants:")
    for i, rec in enumerate(phase_a_results, 1):
        print(f"\n{i}. {next(r['name'] for r in restaurants if r['id'] == rec['restaurantId'])}")
        print(f"   Score: {rec['score']:.1f}/100")
        print(f"   Target Time: {rec['targetTime']}")
        print(f"   Preferred Window: {rec['recommendedWindows']['preferred']['startTime']} - "
              f"{rec['recommendedWindows']['preferred']['endTime']}")
        print(f"   Why Matched: {', '.join(rec['whyMatched'])}")
        print(f"   Availability: {'Pending' if rec['availabilityPending'] else 'Confirmed'}")
    
    print("\n--- PHASE B: With Availability Data ---")
    
    # Simulate availability data (e.g., from OpenTable)
    availability_data: list[AvailabilityPayload] = [
        {
            "restaurantId": "italian-family-rest",
            "date": event["startAt"][:10],
            "partySize": 8,
            "availableTimes": ["17:30", "17:45", "18:00"],  # Good availability
        },
        {
            "restaurantId": "tapas-share-rest",
            "date": event["startAt"][:10],
            "partySize": 8,
            "availableTimes": ["19:30", "20:00"],  # Late availability
        },
    ]
    
    phase_b_results = rank_restaurants_for_event(
        event,
        restaurants,
        travel_times_by_restaurant_id=travel_times,
        availability_payloads=availability_data,
    )
    
    print(f"\nRe-ranked with availability ({len(phase_b_results)} restaurants):")
    for i, rec in enumerate(phase_b_results, 1):
        print(f"\n{i}. {next(r['name'] for r in restaurants if r['id'] == rec['restaurantId'])}")
        print(f"   Score: {rec['score']:.1f}/100 (Availability Fit: "
              f"{rec['scoreBreakdown']['availabilityFit']:.1f})")
        print(f"   Recommended Times: {rec['recommendedAvailableTimes'] or 'None available'}")
        print(f"   Availability: {'Pending' if rec['availabilityPending'] else 'Confirmed'}")


def demo_pre_show_dinner():
    """Demo: Dinner before a 7 PM show."""
    print("\n\n" + "=" * 80)
    print("DEMO: Pre-Show Dinner (7 PM show)")
    print("=" * 80)
    
    # Event: Show at 7 PM
    event: Event = {
        "id": "theater-show-1",
        "type": "SHOW",
        "startAt": (datetime.now(timezone.utc) + timedelta(days=5)).replace(hour=19, minute=0).isoformat(),
        "mealIntent": "BEFORE_EVENT",
        "partySize": 2,
        "hasKids": False,
        "location": {"lat": 37.7749, "lng": -122.4194},
    }
    
    restaurants: list[Restaurant] = [
        {
            "id": "italian-near",
            "name": "Teatro Italiano",
            "location": {"lat": 37.7750, "lng": -122.4195},
            "cuisineTags": ["Italian"],
            "serviceStyleTags": ["casual"],
            "groupSignals": [],
        },
        {
            "id": "sushi-far",
            "name": "Sushi Master",
            "location": {"lat": 37.7800, "lng": -122.4300},
            "cuisineTags": ["Sushi"],
            "serviceStyleTags": ["casual"],
            "groupSignals": [],
        },
    ]
    
    travel_times = {
        "italian-near": 5,  # Very close
        "sushi-far": 25,    # Far away
    }
    
    print("\n--- PHASE A: Ranking by Fit ---")
    phase_a_results = rank_restaurants_for_event(
        event,
        restaurants,
        travel_times_by_restaurant_id=travel_times,
    )
    
    for i, rec in enumerate(phase_a_results, 1):
        rest_name = next(r["name"] for r in restaurants if r["id"] == rec["restaurantId"])
        print(f"\n{i}. {rest_name}")
        print(f"   Score: {rec['score']:.1f} (Travel: {rec['scoreBreakdown']['travelTime']:.1f}, "
              f"Service: {rec['scoreBreakdown']['serviceStyle']:.1f})")
        print(f"   Must finish by: {rec['recommendedWindows']['preferred']['endTime']} "
              f"(for {event['startAt'][11:16]} show)")
        print(f"   Target seat time: {rec['targetTime']}")
    
    # Add availability
    availability_data: list[AvailabilityPayload] = [
        {
            "restaurantId": "italian-near",
            "date": event["startAt"][:10],
            "partySize": 2,
            "availableTimes": ["17:00", "17:15", "17:30"],
        },
        {
            "restaurantId": "sushi-far",
            "date": event["startAt"][:10],
            "partySize": 2,
            "availableTimes": ["16:00", "16:15", "16:30"],  # Very early
        },
    ]
    
    print("\n--- PHASE B: With Availability ---")
    phase_b_results = rank_restaurants_for_event(
        event,
        restaurants,
        travel_times_by_restaurant_id=travel_times,
        availability_payloads=availability_data,
    )
    
    for i, rec in enumerate(phase_b_results, 1):
        rest_name = next(r["name"] for r in restaurants if r["id"] == rec["restaurantId"])
        print(f"\n{i}. {rest_name}")
        print(f"   Final Score: {rec['score']:.1f}")
        print(f"   Best Times: {rec['recommendedAvailableTimes']}")
        print("   Why: Close to venue, good timing for show")


def main():
    """Run all demos."""
    print("\n" + "🍽️  TWO-PHASE RESTAURANT-EVENT PAIRING DEMO  🎭".center(80))
    
    demo_family_gathering()
    demo_pre_show_dinner()
    
    print("\n\n" + "=" * 80)
    print("Demo complete! The pairing system:")
    print("  ✓ Computes time windows (not single times)")
    print("  ✓ Scores restaurants by fit (Phase A)")
    print("  ✓ Re-ranks with availability data (Phase B)")
    print("  ✓ Enforces family-style for family events")
    print("  ✓ Considers travel time, cuisine, and group signals")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
