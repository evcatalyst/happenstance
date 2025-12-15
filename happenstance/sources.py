"""Data source integrations for fetching real restaurant and event data."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests


def fetch_google_places_restaurants(
    region: str,
    location: str | None = None,
    radius_meters: int = 5000,
    api_key: str | None = None,
) -> List[Dict]:
    """
    Fetch restaurants from Google Places API.
    
    Args:
        region: Region name for display purposes
        location: Lat,long coordinates (e.g., "37.7749,-122.4194")
        radius_meters: Search radius in meters
        api_key: Google Places API key
        
    Returns:
        List of restaurant dictionaries
    """
    api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise ValueError("Google Places API key not provided. Set GOOGLE_PLACES_API_KEY environment variable.")
    
    if not location:
        raise ValueError("Location coordinates required for Google Places API (format: 'lat,long')")
    
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": location,
        "radius": radius_meters,
        "type": "restaurant",
        "key": api_key,
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") != "OK":
            error_msg = data.get("error_message", data.get("status", "Unknown error"))
            raise ValueError(f"Google Places API error: {error_msg}")
        
        restaurants = []
        for place in data.get("results", [])[:20]:  # Limit to 20 restaurants
            # Determine cuisine from types or default
            types = place.get("types", [])
            cuisine = _infer_cuisine_from_types(types)
            
            restaurants.append({
                "name": place.get("name", "Unknown"),
                "cuisine": cuisine,
                "address": place.get("vicinity", f"{region} area"),
                "url": f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id', '')}",
                "match_reason": f"Popular {cuisine.lower()} restaurant in {region}",
                "rating": place.get("rating"),
                "price_level": place.get("price_level"),
            })
        
        return restaurants
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch from Google Places API: {e}") from e


def _infer_cuisine_from_types(types: List[str]) -> str:
    """Infer cuisine type from Google Places types."""
    cuisine_map = {
        "italian": "Italian",
        "japanese": "Japanese",
        "chinese": "Chinese",
        "mexican": "Mexican",
        "indian": "Indian",
        "thai": "Thai",
        "french": "French",
        "american": "American",
        "seafood": "Seafood",
        "pizza": "Pizza",
        "cafe": "Cafe",
        "bakery": "Bakery",
        "bar": "Bar & Grill",
    }
    
    for place_type in types:
        type_lower = place_type.lower()
        if type_lower in cuisine_map:
            return cuisine_map[type_lower]
    
    return "Restaurant"


def fetch_ticketmaster_events(
    region: str,
    city: str | None = None,
    state_code: str | None = None,
    country_code: str = "US",
    radius_miles: int = 25,
    api_key: str | None = None,
    days_ahead: int = 30,
) -> List[Dict]:
    """
    Fetch events from Ticketmaster Discovery API.
    
    Args:
        region: Region name for display purposes
        city: City name
        state_code: State code (e.g., "CA")
        country_code: Country code (default: "US")
        radius_miles: Search radius in miles
        api_key: Ticketmaster API key
        days_ahead: Number of days ahead to search for events
        
    Returns:
        List of event dictionaries
    """
    api_key = api_key or os.getenv("TICKETMASTER_API_KEY")
    if not api_key:
        raise ValueError("Ticketmaster API key not provided. Set TICKETMASTER_API_KEY environment variable.")
    
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    
    # Calculate date range
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=days_ahead)
    
    params: Dict[str, Any] = {
        "apikey": api_key,
        "countryCode": country_code,
        "radius": radius_miles,
        "unit": "miles",
        "size": 30,  # Number of events to fetch
        "sort": "date,asc",
        "startDateTime": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endDateTime": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    
    if city:
        params["city"] = city
    if state_code:
        params["stateCode"] = state_code
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        events = []
        embedded = data.get("_embedded", {})
        for event in embedded.get("events", []):
            # Extract event details
            name = event.get("name", "Unknown Event")
            event_date = event.get("dates", {}).get("start", {}).get("dateTime")
            
            if not event_date:
                continue  # Skip events without a date
            
            # Get venue information
            venues = event.get("_embedded", {}).get("venues", [])
            location = f"{region}"
            if venues:
                venue = venues[0]
                venue_name = venue.get("name", "")
                if venue_name:
                    location = f"{venue_name}, {region}"
            
            # Determine category
            classifications = event.get("classifications", [{}])
            category = "entertainment"
            if classifications:
                segment = classifications[0].get("segment", {}).get("name", "").lower()
                genre = classifications[0].get("genre", {}).get("name", "").lower()
                
                if "music" in segment or "music" in genre:
                    category = "live music"
                elif "sports" in segment:
                    category = "sports"
                elif "arts" in segment or "theatre" in segment:
                    category = "art"
                elif "family" in genre:
                    category = "family"
            
            # Get event URL
            event_url = event.get("url", "")
            
            events.append({
                "title": name,
                "category": category,
                "date": event_date,
                "location": location,
                "url": event_url,
            })
        
        return events
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch from Ticketmaster API: {e}") from e


def fetch_eventbrite_events(
    region: str,
    location_address: str | None = None,
    location_within: str = "25mi",
    api_key: str | None = None,
    days_ahead: int = 30,
) -> List[Dict]:
    """
    Fetch events from Eventbrite API.
    
    Args:
        region: Region name for display purposes
        location_address: Location address or coordinates
        location_within: Search radius (e.g., "25mi", "10km")
        api_key: Eventbrite API token
        days_ahead: Number of days ahead to search for events
        
    Returns:
        List of event dictionaries
    """
    api_key = api_key or os.getenv("EVENTBRITE_API_KEY")
    if not api_key:
        raise ValueError("Eventbrite API key not provided. Set EVENTBRITE_API_KEY environment variable.")
    
    if not location_address:
        raise ValueError("Location address required for Eventbrite API")
    
    url = "https://www.eventbriteapi.com/v3/events/search/"
    
    # Calculate date range
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=days_ahead)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    
    params = {
        "location.address": location_address,
        "location.within": location_within,
        "start_date.range_start": start_date.isoformat(),
        "start_date.range_end": end_date.isoformat(),
        "expand": "venue",
        "sort_by": "date",
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        events = []
        for event in data.get("events", []):
            name = event.get("name", {}).get("text", "Unknown Event")
            event_date = event.get("start", {}).get("utc")
            
            if not event_date:
                continue
            
            # Get venue
            venue = event.get("venue")
            location = region
            if venue:
                venue_name = venue.get("name", "")
                if venue_name:
                    location = f"{venue_name}, {region}"
            
            # Infer category from event name and description
            description = (event.get("description", {}).get("text", "") or "").lower()
            name_lower = name.lower()
            
            category = "entertainment"
            if any(word in name_lower or word in description for word in ["music", "concert", "band", "jazz"]):
                category = "live music"
            elif any(word in name_lower or word in description for word in ["art", "gallery", "exhibit", "museum"]):
                category = "art"
            elif any(word in name_lower or word in description for word in ["family", "kids", "children"]):
                category = "family"
            elif any(word in name_lower or word in description for word in ["sports", "game", "race", "run"]):
                category = "sports"
            
            events.append({
                "title": name,
                "category": category,
                "date": event_date,
                "location": location,
                "url": event.get("url", ""),
            })
        
        return events
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch from Eventbrite API: {e}") from e
