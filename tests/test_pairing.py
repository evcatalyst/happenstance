"""Tests for two-phase restaurant-event pairing logic."""

from typing import List

from happenstance.pairing import (
    AvailabilityPayload,
    Event,
    Restaurant,
    apply_availability,
    compute_dining_windows,
    rank_restaurants_for_event,
    score_restaurant_fit,
)


class TestComputeDiningWindows:
    """Tests for dining window computation."""
    
    def test_before_event_window_calculation(self):
        """Test that BEFORE_EVENT computes correct time windows."""
        # Event at 7 PM
        event: Event = {
            "id": "event1",
            "type": "SHOW",
            "startAt": "2024-01-15T19:00:00+00:00",
            "mealIntent": "BEFORE_EVENT",
            "partySize": 2,
            "hasKids": False,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        # 15 minutes travel time
        windows = compute_dining_windows(event, travel_time_minutes=15)
        
        # Should have targetTime, preferred, and fallbacks
        assert "targetTime" in windows
        assert "preferred" in windows
        assert "fallbacks" in windows
        assert len(windows["fallbacks"]) == 2
        
        # Verify windows are before event start
        # With 15 min travel + 10 min buffer + 90 min meal, we need to finish by ~5:35 PM
        # So target seat should be around 4:05 PM or earlier
        target_hour = int(windows["targetTime"].split(":")[0])
        assert target_hour < 19  # Before 7 PM event
    
    def test_before_event_with_kids_adds_buffer(self):
        """Test that hasKids=True adds extra buffer time."""
        event_no_kids: Event = {
            "id": "event1",
            "type": "SHOW",
            "startAt": "2024-01-15T19:00:00+00:00",
            "mealIntent": "BEFORE_EVENT",
            "partySize": 4,
            "hasKids": False,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        event_with_kids: Event = {
            **event_no_kids,
            "hasKids": True,
        }
        
        windows_no_kids = compute_dining_windows(event_no_kids, travel_time_minutes=10)
        windows_with_kids = compute_dining_windows(event_with_kids, travel_time_minutes=10)
        
        # With kids should have earlier target time (more buffer)
        target_no_kids_mins = int(windows_no_kids["targetTime"].split(":")[0]) * 60 + \
                              int(windows_no_kids["targetTime"].split(":")[1])
        target_with_kids_mins = int(windows_with_kids["targetTime"].split(":")[0]) * 60 + \
                               int(windows_with_kids["targetTime"].split(":")[1])
        
        assert target_with_kids_mins < target_no_kids_mins
    
    def test_after_event_window_calculation(self):
        """Test that AFTER_EVENT computes correct time windows."""
        # Event from 7-9 PM
        event: Event = {
            "id": "event1",
            "type": "SHOW",
            "startAt": "2024-01-15T19:00:00+00:00",
            "endAt": "2024-01-15T21:00:00+00:00",
            "mealIntent": "AFTER_EVENT",
            "partySize": 2,
            "hasKids": False,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        windows = compute_dining_windows(event, travel_time_minutes=15)
        
        assert "targetTime" in windows
        
        # Target should be after 9 PM (event end) + 15 min exit + 15 min travel + 10 min buffer
        # So around 9:40 PM or later
        target_hour = int(windows["targetTime"].split(":")[0])
        assert target_hour >= 21  # After 9 PM
    
    def test_after_event_uses_duration_if_no_end(self):
        """Test that AFTER_EVENT uses durationMinutes if endAt not provided."""
        # Event starts at 7 PM, 120 minute duration
        event: Event = {
            "id": "event1",
            "type": "SHOW",
            "startAt": "2024-01-15T19:00:00+00:00",
            "durationMinutes": 120,
            "mealIntent": "AFTER_EVENT",
            "partySize": 2,
            "hasKids": False,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        windows = compute_dining_windows(event, travel_time_minutes=10)
        
        # Should compute end as 9 PM (7 PM + 2 hours)
        # Then add buffers
        target_hour = int(windows["targetTime"].split(":")[0])
        assert target_hour >= 21
    
    def test_meal_is_event_default_windows(self):
        """Test that MEAL_IS_EVENT provides default dinner windows."""
        event: Event = {
            "id": "event1",
            "type": "DINNER",
            "startAt": "2024-01-15T18:00:00+00:00",
            "mealIntent": "MEAL_IS_EVENT",
            "partySize": 4,
            "hasKids": False,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        windows = compute_dining_windows(event, travel_time_minutes=10)
        
        # Should have standard dinner windows (6-7:30 PM preferred)
        assert windows["preferred"]["startTime"] == "18:00"
        assert windows["preferred"]["endTime"] == "19:30"
        assert windows["targetTime"] == "18:30"
    
    def test_meal_is_event_with_kids_earlier(self):
        """Test that MEAL_IS_EVENT with kids biases earlier."""
        event: Event = {
            "id": "event1",
            "type": "DINNER",
            "startAt": "2024-01-15T18:00:00+00:00",
            "mealIntent": "MEAL_IS_EVENT",
            "partySize": 4,
            "hasKids": True,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        windows = compute_dining_windows(event, travel_time_minutes=10)
        
        # Should have earlier windows for kids (5-6:30 PM preferred)
        assert windows["preferred"]["startTime"] == "17:00"
        assert windows["targetTime"] == "17:30"


class TestScoreRestaurantFit:
    """Tests for restaurant fit scoring."""
    
    def test_family_style_hard_filter_excludes_non_family_restaurants(self):
        """Test that family events exclude non-family-style restaurants."""
        event: Event = {
            "id": "event1",
            "type": "FAMILY_STYLE_GATHERING",
            "startAt": "2024-01-15T18:00:00+00:00",
            "mealIntent": "MEAL_IS_EVENT",
            "partySize": 8,
            "hasKids": True,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        restaurant_no_family_style: Restaurant = {
            "id": "rest1",
            "name": "Fine Dining",
            "location": {"lat": 37.7750, "lng": -122.4195},
            "cuisineTags": ["French"],
            "serviceStyleTags": ["fine_dining"],
            "groupSignals": [],
        }
        
        result = score_restaurant_fit(event, restaurant_no_family_style, travel_time_minutes=10)
        
        # Should be excluded
        assert result["excluded"] is True
        assert result["totalScore"] == 0.0
    
    def test_family_style_restaurant_scores_high_for_family_event(self):
        """Test that family-style restaurants score high for family events."""
        event: Event = {
            "id": "event1",
            "type": "FAMILY_STYLE_GATHERING",
            "startAt": "2024-01-15T18:00:00+00:00",
            "mealIntent": "MEAL_IS_EVENT",
            "partySize": 8,
            "hasKids": True,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        restaurant_family_style: Restaurant = {
            "id": "rest1",
            "name": "Family Restaurant",
            "location": {"lat": 37.7750, "lng": -122.4195},
            "cuisineTags": ["Italian"],
            "serviceStyleTags": ["family_style"],
            "groupSignals": ["large_tables", "kids_menu"],
        }
        
        result = score_restaurant_fit(event, restaurant_family_style, travel_time_minutes=10)
        
        # Should not be excluded and have high service style score
        assert result["excluded"] is False
        assert result["breakdown"]["serviceStyle"] >= 90.0
        assert "Family-style dining" in result["reasons"]
    
    def test_travel_time_scoring(self):
        """Test that travel time affects score correctly."""
        event: Event = {
            "id": "event1",
            "type": "SHOW",
            "startAt": "2024-01-15T19:00:00+00:00",
            "mealIntent": "BEFORE_EVENT",
            "partySize": 2,
            "hasKids": False,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        restaurant: Restaurant = {
            "id": "rest1",
            "name": "Restaurant",
            "location": {"lat": 37.7750, "lng": -122.4195},
            "cuisineTags": ["Italian"],
            "serviceStyleTags": ["casual"],
            "groupSignals": [],
        }
        
        # Close restaurant (5 min)
        result_close = score_restaurant_fit(event, restaurant, travel_time_minutes=5)
        
        # Far restaurant (30 min)
        result_far = score_restaurant_fit(event, restaurant, travel_time_minutes=30)
        
        # Close should score higher on travel time
        assert result_close["breakdown"]["travelTime"] > result_far["breakdown"]["travelTime"]
        assert result_close["totalScore"] > result_far["totalScore"]
    
    def test_group_signals_add_bonuses(self):
        """Test that group signals add score bonuses."""
        event: Event = {
            "id": "event1",
            "type": "FAMILY_STYLE_GATHERING",
            "startAt": "2024-01-15T18:00:00+00:00",
            "mealIntent": "MEAL_IS_EVENT",
            "partySize": 10,
            "hasKids": True,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        restaurant_basic: Restaurant = {
            "id": "rest1",
            "name": "Basic Restaurant",
            "location": {"lat": 37.7750, "lng": -122.4195},
            "cuisineTags": ["Italian"],
            "serviceStyleTags": ["family_style"],
            "groupSignals": [],
        }
        
        restaurant_with_signals: Restaurant = {
            "id": "rest2",
            "name": "Full Service Restaurant",
            "location": {"lat": 37.7750, "lng": -122.4195},
            "cuisineTags": ["Italian"],
            "serviceStyleTags": ["family_style"],
            "groupSignals": ["large_tables", "kids_menu", "private_room"],
        }
        
        result_basic = score_restaurant_fit(event, restaurant_basic, travel_time_minutes=10)
        result_with_signals = score_restaurant_fit(event, restaurant_with_signals, travel_time_minutes=10)
        
        # Restaurant with signals should score higher
        assert result_with_signals["breakdown"]["serviceStyle"] > result_basic["breakdown"]["serviceStyle"]


class TestApplyAvailability:
    """Tests for Phase B availability application."""
    
    def test_availability_intersection_with_preferred_window(self):
        """Test that available times in preferred window get highest score."""
        event: Event = {
            "id": "event1",
            "type": "SHOW",
            "startAt": "2024-01-15T19:00:00+00:00",
            "mealIntent": "BEFORE_EVENT",
            "partySize": 2,
            "hasKids": False,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        # Create a Phase A recommendation
        recommendation = {
            "restaurantId": "rest1",
            "score": 70.0,
            "scoreBreakdown": {
                "serviceStyle": 80.0,
                "travelTime": 90.0,
                "cuisineDiet": 70.0,
                "availabilityFit": 0.0,
            },
            "recommendedWindows": {
                "preferred": {"startTime": "17:00", "endTime": "18:00"},
                "fallbacks": [
                    {"label": "Earlier", "startTime": "16:00", "endTime": "17:00"},
                    {"label": "Later", "startTime": "18:00", "endTime": "19:00"},
                ],
            },
            "targetTime": "17:30",
            "availabilityPending": True,
            "recommendedAvailableTimes": None,
            "whyMatched": ["Close to venue"],
        }
        
        # Availability with times in preferred window
        availability = {
            "restaurantId": "rest1",
            "date": "2024-01-15",
            "partySize": 2,
            "availableTimes": ["17:15", "17:30", "17:45"],
        }
        
        updated = apply_availability([recommendation], [availability], event)
        
        assert len(updated) == 1
        assert updated[0]["availabilityPending"] is False
        assert updated[0]["scoreBreakdown"]["availabilityFit"] == 100.0
        assert updated[0]["recommendedAvailableTimes"] is not None
        assert len(updated[0]["recommendedAvailableTimes"]) > 0
        # Should recommend 17:30 (closest to target)
        assert "17:30" in updated[0]["recommendedAvailableTimes"]
    
    def test_availability_in_fallback_window_scores_lower(self):
        """Test that available times in fallback windows score lower."""
        event: Event = {
            "id": "event1",
            "type": "SHOW",
            "startAt": "2024-01-15T19:00:00+00:00",
            "mealIntent": "BEFORE_EVENT",
            "partySize": 2,
            "hasKids": False,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        recommendation = {
            "restaurantId": "rest1",
            "score": 70.0,
            "scoreBreakdown": {
                "serviceStyle": 80.0,
                "travelTime": 90.0,
                "cuisineDiet": 70.0,
                "availabilityFit": 0.0,
            },
            "recommendedWindows": {
                "preferred": {"startTime": "17:00", "endTime": "18:00"},
                "fallbacks": [
                    {"label": "Earlier", "startTime": "16:00", "endTime": "17:00"},
                    {"label": "Later", "startTime": "18:00", "endTime": "19:00"},
                ],
            },
            "targetTime": "17:30",
            "availabilityPending": True,
            "recommendedAvailableTimes": None,
            "whyMatched": ["Close to venue"],
        }
        
        # Availability only in fallback window
        availability = {
            "restaurantId": "rest1",
            "date": "2024-01-15",
            "partySize": 2,
            "availableTimes": ["16:15", "16:30"],  # In first fallback
        }
        
        updated = apply_availability([recommendation], [availability], event)
        
        assert updated[0]["scoreBreakdown"]["availabilityFit"] == 66.0
        assert "16:30" in updated[0]["recommendedAvailableTimes"]
    
    def test_no_availability_keeps_pending(self):
        """Test that restaurants without availability data stay pending."""
        event: Event = {
            "id": "event1",
            "type": "SHOW",
            "startAt": "2024-01-15T19:00:00+00:00",
            "mealIntent": "BEFORE_EVENT",
            "partySize": 2,
            "hasKids": False,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        recommendation = {
            "restaurantId": "rest1",
            "score": 70.0,
            "scoreBreakdown": {
                "serviceStyle": 80.0,
                "travelTime": 90.0,
                "cuisineDiet": 70.0,
                "availabilityFit": 0.0,
            },
            "recommendedWindows": {
                "preferred": {"startTime": "17:00", "endTime": "18:00"},
                "fallbacks": [],
            },
            "targetTime": "17:30",
            "availabilityPending": True,
            "recommendedAvailableTimes": None,
            "whyMatched": ["Close to venue"],
        }
        
        # No availability payload for this restaurant
        updated = apply_availability([recommendation], [], event)
        
        assert updated[0]["availabilityPending"] is True
        assert updated[0]["scoreBreakdown"]["availabilityFit"] == 0.0
    
    def test_reranking_by_availability(self):
        """Test that restaurants are re-ranked based on availability."""
        event: Event = {
            "id": "event1",
            "type": "SHOW",
            "startAt": "2024-01-15T19:00:00+00:00",
            "mealIntent": "BEFORE_EVENT",
            "partySize": 2,
            "hasKids": False,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        # Restaurant 1: higher initial score, but no good availability
        rec1 = {
            "restaurantId": "rest1",
            "score": 80.0,
            "scoreBreakdown": {
                "serviceStyle": 90.0,
                "travelTime": 85.0,
                "cuisineDiet": 80.0,
                "availabilityFit": 0.0,
            },
            "recommendedWindows": {
                "preferred": {"startTime": "17:00", "endTime": "18:00"},
                "fallbacks": [],
            },
            "targetTime": "17:30",
            "availabilityPending": True,
            "recommendedAvailableTimes": None,
            "whyMatched": ["Great food"],
        }
        
        # Restaurant 2: lower initial score, but perfect availability
        rec2 = {
            "restaurantId": "rest2",
            "score": 70.0,
            "scoreBreakdown": {
                "serviceStyle": 75.0,
                "travelTime": 80.0,
                "cuisineDiet": 70.0,
                "availabilityFit": 0.0,
            },
            "recommendedWindows": {
                "preferred": {"startTime": "17:00", "endTime": "18:00"},
                "fallbacks": [],
            },
            "targetTime": "17:30",
            "availabilityPending": True,
            "recommendedAvailableTimes": None,
            "whyMatched": ["Close by"],
        }
        
        # Only rest2 has good availability
        availability = {
            "restaurantId": "rest2",
            "date": "2024-01-15",
            "partySize": 2,
            "availableTimes": ["17:30"],  # Perfect time
        }
        
        updated = apply_availability([rec1, rec2], [availability], event)
        
        # rest2 should now rank higher due to availability
        assert updated[0]["restaurantId"] == "rest2"
        assert updated[0]["score"] > updated[1]["score"]


class TestRankRestaurantsForEvent:
    """Tests for complete ranking pipeline."""
    
    def test_phase_a_ranking_without_availability(self):
        """Test Phase A: ranking without availability data."""
        event: Event = {
            "id": "event1",
            "type": "FAMILY_STYLE_GATHERING",
            "startAt": "2024-01-15T18:00:00+00:00",
            "mealIntent": "MEAL_IS_EVENT",
            "partySize": 8,
            "hasKids": True,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        restaurants: List[Restaurant] = [
            {
                "id": "rest1",
                "name": "Family Italian",
                "location": {"lat": 37.7750, "lng": -122.4195},
                "cuisineTags": ["Italian"],
                "serviceStyleTags": ["family_style"],
                "groupSignals": ["large_tables", "kids_menu"],
            },
            {
                "id": "rest2",
                "name": "Fancy French",
                "location": {"lat": 37.7751, "lng": -122.4196},
                "cuisineTags": ["French"],
                "serviceStyleTags": ["fine_dining"],
                "groupSignals": [],
            },
            {
                "id": "rest3",
                "name": "Share Plates Tapas",
                "location": {"lat": 37.7752, "lng": -122.4197},
                "cuisineTags": ["Spanish"],
                "serviceStyleTags": ["share_plates"],
                "groupSignals": ["noise_tolerant"],
            },
        ]
        
        rankings = rank_restaurants_for_event(event, restaurants)
        
        # Should only include family-style and share-plates restaurants
        assert len(rankings) == 2
        assert all(r["availabilityPending"] is True for r in rankings)
        
        # rest1 (family_style) should rank first due to kids_menu bonus
        assert rankings[0]["restaurantId"] in ["rest1", "rest3"]
    
    def test_phase_b_ranking_with_availability(self):
        """Test Phase B: ranking with availability data."""
        event: Event = {
            "id": "event1",
            "type": "SHOW",
            "startAt": "2024-01-15T19:00:00+00:00",
            "mealIntent": "BEFORE_EVENT",
            "partySize": 2,
            "hasKids": False,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        restaurants: List[Restaurant] = [
            {
                "id": "rest1",
                "name": "Restaurant 1",
                "location": {"lat": 37.7750, "lng": -122.4195},
                "cuisineTags": ["Italian"],
                "serviceStyleTags": ["casual"],
                "groupSignals": [],
            },
            {
                "id": "rest2",
                "name": "Restaurant 2",
                "location": {"lat": 37.7751, "lng": -122.4196},
                "cuisineTags": ["American"],
                "serviceStyleTags": ["casual"],
                "groupSignals": [],
            },
        ]
        
        travel_times = {
            "rest1": 10,
            "rest2": 15,
        }
        
        availability: List[AvailabilityPayload] = [
            {
                "restaurantId": "rest1",
                "date": "2024-01-15",
                "partySize": 2,
                "availableTimes": ["17:00", "17:30"],
            },
        ]
        
        rankings = rank_restaurants_for_event(
            event,
            restaurants,
            travel_times_by_restaurant_id=travel_times,
            availability_payloads=availability,
        )
        
        assert len(rankings) == 2
        
        # rest1 should have availabilityPending=False
        rest1_rec = next(r for r in rankings if r["restaurantId"] == "rest1")
        assert rest1_rec["availabilityPending"] is False
        assert rest1_rec["recommendedAvailableTimes"] is not None
        
        # rest2 should still be pending
        rest2_rec = next(r for r in rankings if r["restaurantId"] == "rest2")
        assert rest2_rec["availabilityPending"] is True
    
    def test_stable_sorting_by_travel_time_then_name(self):
        """Test that ties are broken by travel time, then restaurant ID."""
        event: Event = {
            "id": "event1",
            "type": "SHOW",
            "startAt": "2024-01-15T19:00:00+00:00",
            "mealIntent": "BEFORE_EVENT",
            "partySize": 2,
            "hasKids": False,
            "location": {"lat": 37.7749, "lng": -122.4194},
        }
        
        # Create restaurants with identical attributes except ID
        restaurants: List[Restaurant] = [
            {
                "id": "rest_c",
                "name": "Restaurant C",
                "location": {"lat": 37.7750, "lng": -122.4195},
                "cuisineTags": ["Italian"],
                "serviceStyleTags": ["casual"],
                "groupSignals": [],
            },
            {
                "id": "rest_a",
                "name": "Restaurant A",
                "location": {"lat": 37.7750, "lng": -122.4195},
                "cuisineTags": ["Italian"],
                "serviceStyleTags": ["casual"],
                "groupSignals": [],
            },
            {
                "id": "rest_b",
                "name": "Restaurant B",
                "location": {"lat": 37.7750, "lng": -122.4195},
                "cuisineTags": ["Italian"],
                "serviceStyleTags": ["casual"],
                "groupSignals": [],
            },
        ]
        
        # All have same travel time
        travel_times = {
            "rest_a": 10,
            "rest_b": 10,
            "rest_c": 10,
        }
        
        rankings = rank_restaurants_for_event(
            event,
            restaurants,
            travel_times_by_restaurant_id=travel_times,
        )
        
        # Should be sorted alphabetically by ID when scores are equal
        ids = [r["restaurantId"] for r in rankings]
        assert ids == ["rest_a", "rest_b", "rest_c"]
