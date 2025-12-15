#!/usr/bin/env python
"""
CLI command to fetch AI-powered data using web search.

This script uses the agent's web_search tool to fetch restaurant and event data,
then passes it to the aggregate command.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from happenstance.ai_prompts import generate_events_prompt, generate_restaurant_prompt
from happenstance.config import load_config


def main():
    parser = argparse.ArgumentParser(description="Fetch AI data using web search")
    parser.add_argument("--profile", default=None, help="Profile to use from config")
    parser.add_argument(
        "--output-dir", 
        default="/tmp",
        help="Directory to store AI responses"
    )
    args = parser.parse_args()
    
    # Load config
    cfg = load_config(args.profile)
    api_config = cfg.get("api_config", {}).get("ai", {})
    city = api_config.get("city", cfg.get("region", "San Francisco"))
    
    # Generate prompts
    restaurant_prompt = generate_restaurant_prompt(
        city=city,
        cuisines=cfg.get("target_cuisines", []),
        count=api_config.get("restaurant_count", 20)
    )
    
    events_prompt = generate_events_prompt(
        city=city,
        categories=cfg.get("target_categories", []),
        days_ahead=cfg.get("event_window_days", 30),
        count=api_config.get("event_count", 20)
    )
    
    print("=" * 80)
    print("RESTAURANT PROMPT:")
    print("=" * 80)
    print(restaurant_prompt)
    print()
    
    print("=" * 80)
    print("EVENTS PROMPT:")
    print("=" * 80)
    print(events_prompt)
    print()
    
    print("=" * 80)
    print("INSTRUCTIONS:")
    print("=" * 80)
    print("Run these prompts through the web_search tool and save the responses:")
    print(f"1. Save restaurant response to: {args.output_dir}/ai_restaurants_response.json")
    print(f"2. Save events response to: {args.output_dir}/ai_events_response.json")
    print()
    print("Then set environment variables:")
    print(f"  export AI_RESTAURANTS_DATA=$(cat {args.output_dir}/ai_restaurants_response.json)")
    print(f"  export AI_EVENTS_DATA=$(cat {args.output_dir}/ai_events_response.json)")
    print()
    print("Finally run: python -m happenstance.cli aggregate")


if __name__ == "__main__":
    main()
