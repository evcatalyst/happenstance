"""Helper script to fetch AI data using web_search tool.

This script is meant to be called by the agent code that has access to the web_search tool.
It generates prompts and can parse responses to store in environment variables.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def generate_restaurant_prompt(city: str, cuisines: list[str], count: int = 20) -> str:
    """Generate a prompt for fetching restaurant data."""
    cuisines_str = ", ".join(cuisines) if cuisines else "various cuisines"
    
    return f"""Find {count} popular, real restaurants currently operating in {city}. 
Include a variety of cuisines: {cuisines_str}.

Return ONLY a valid JSON array with this exact structure (no additional text, explanations, or markdown):
[
  {{
    "name": "Restaurant Name",
    "cuisine": "Cuisine Type",
    "address": "Street Address, {city}",
    "url": "https://www.google.com/maps/search/?api=1&query=Restaurant+Name+{city.replace(' ', '+')}",
    "match_reason": "Brief description (e.g., 'Great waterfront dining with fresh seafood')",
    "rating": 4.5,
    "price_level": 2
  }}
]

Requirements:
- Use REAL, currently operating restaurants in {city}
- Ensure variety in cuisine types (Italian, Sushi, BBQ, Mexican, etc.)
- Include mix of price levels (1-4 scale)
- Provide actual street addresses
- Return valid JSON only"""


def generate_events_prompt(city: str, categories: list[str], days_ahead: int = 30, count: int = 20) -> str:
    """Generate a prompt for fetching event data."""
    cats_str = ", ".join(categories) if categories else "live music, art, family events, sports"
    
    # Calculate date range
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=days_ahead)
    
    return f"""Find {count} real, upcoming events in {city} between {start_date.strftime('%B %d, %Y')} and {end_date.strftime('%B %d, %Y')}.
Include events in these categories: {cats_str}.

Return ONLY a valid JSON array with this exact structure (no additional text, explanations, or markdown):
[
  {{
    "title": "Event Name",
    "category": "live music",
    "date": "2025-12-20T19:00:00+00:00",
    "location": "Venue Name, {city}",
    "url": "https://www.google.com/maps/search/?api=1&query=Event+Name+Venue+{city.replace(' ', '+')}"
  }}
]

Requirements:
- Use REAL, upcoming events in {city}
- Dates must be between {start_date.strftime('%Y-%m-%d')} and {end_date.strftime('%Y-%m-%d')}
- Use ISO 8601 format for dates (YYYY-MM-DDTHH:MM:SS+00:00)
- Categories must be one of: live music, art, family, sports, entertainment
- Include actual venue names
- Return valid JSON only"""


if __name__ == "__main__":
    # Example usage
    print("Restaurant Prompt:")
    print("=" * 80)
    print(generate_restaurant_prompt("San Francisco", ["Italian", "Sushi", "BBQ", "Vegan"]))
    print("\n\nEvents Prompt:")
    print("=" * 80)
    print(generate_events_prompt("San Francisco", ["live music", "art", "family", "sports"]))
