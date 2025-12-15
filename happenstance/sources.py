"""Data source integrations for fetching real restaurant and event data using AI.

This module uses AI-powered search (Grok/OpenAI) to fetch restaurant and event data.
The data is fetched using web search capabilities and parsed from AI responses.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List


def _parse_json_from_text(text: str) -> Any:
    """
    Extract JSON from AI response text.
    
    Args:
        text: Text potentially containing JSON
        
    Returns:
        Parsed JSON object or None
    """
    # Try to find JSON in markdown code blocks first
    json_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\]|\{[\s\S]*?\})\s*```', text, re.MULTILINE)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to find raw JSON array
    json_match = re.search(r'(\[[\s\S]*?\])', text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to find raw JSON object
    json_match = re.search(r'(\{[\s\S]*?\})', text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    return None


def fetch_ai_restaurants(
    region: str,
    city: str | None = None,
    cuisine_types: List[str] | None = None,
    count: int = 20,
    ai_response: str | None = None,
) -> List[Dict]:
    """
    Fetch restaurants using AI-powered search results.
    
    Args:
        region: Region name for display purposes
        city: City name for search
        cuisine_types: List of preferred cuisine types
        count: Number of restaurants to fetch
        ai_response: Pre-fetched AI response (from web_search tool)
        
    Returns:
        List of restaurant dictionaries
    """
    city_name = city or region
    
    if not ai_response:
        # Check if response was provided via environment variable
        ai_response = os.getenv("AI_RESTAURANTS_DATA")
    
    if not ai_response:
        raise ValueError(
            "No AI response provided for restaurants. "
            "Either pass ai_response parameter or set AI_RESTAURANTS_DATA environment variable."
        )
    
    try:
        # Try to parse JSON from response
        data = _parse_json_from_text(ai_response)
        
        if data and isinstance(data, list):
            # Validate and clean the data
            restaurants = []
            for item in data[:count]:
                if isinstance(item, dict) and "name" in item:
                    restaurant = {
                        "name": item.get("name", "Unknown"),
                        "cuisine": item.get("cuisine", "Restaurant"),
                        "address": item.get("address", f"{city_name} area"),
                        "url": item.get("url", f"https://www.google.com/search?q={item.get('name', 'restaurant').replace(' ', '+')}+{city_name.replace(' ', '+')}"),
                        "match_reason": item.get("match_reason", f"Popular restaurant in {city_name}"),
                    }
                    # Optional fields
                    if "rating" in item:
                        restaurant["rating"] = item["rating"]
                    if "price_level" in item:
                        restaurant["price_level"] = item["price_level"]
                    restaurants.append(restaurant)
            
            if restaurants:
                return restaurants
        
        # If parsing failed, raise error to trigger fallback
        raise ValueError("Failed to parse restaurant data from AI response")
        
    except Exception as e:
        raise ValueError(f"Failed to fetch restaurants using AI: {e}") from e


def fetch_ai_events(
    region: str,
    city: str | None = None,
    categories: List[str] | None = None,
    days_ahead: int = 30,
    count: int = 20,
    ai_response: str | None = None,
) -> List[Dict]:
    """
    Fetch events using AI-powered search results.
    
    Args:
        region: Region name for display purposes
        city: City name for search  
        categories: List of preferred event categories
        days_ahead: Number of days ahead to search for events
        count: Number of events to fetch
        ai_response: Pre-fetched AI response (from web_search tool)
        
    Returns:
        List of event dictionaries
    """
    city_name = city or region
    
    if not ai_response:
        # Check if response was provided via environment variable
        ai_response = os.getenv("AI_EVENTS_DATA")
    
    if not ai_response:
        raise ValueError(
            "No AI response provided for events. "
            "Either pass ai_response parameter or set AI_EVENTS_DATA environment variable."
        )
    
    try:
        # Try to parse JSON from response
        data = _parse_json_from_text(ai_response)
        
        if data and isinstance(data, list):
            # Validate and clean the data
            events = []
            for item in data[:count]:
                if isinstance(item, dict) and "title" in item:
                    event = {
                        "title": item.get("title", "Unknown Event"),
                        "category": item.get("category", "entertainment"),
                        "date": item.get("date", datetime.now(timezone.utc).isoformat()),
                        "location": item.get("location", f"{city_name}"),
                        "url": item.get("url", f"https://www.google.com/search?q={item.get('title', 'event').replace(' ', '+')}+{city_name.replace(' ', '+')}"),
                    }
                    events.append(event)
            
            if events:
                return events
        
        # If parsing failed, raise error to trigger fallback
        raise ValueError("Failed to parse event data from AI response")
        
    except Exception as e:
        raise ValueError(f"Failed to fetch events using AI: {e}") from e
