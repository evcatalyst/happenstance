# AI-Powered Data Setup Guide (Grok/OpenAI)

This guide explains how to set up AI-powered data fetching using Grok and OpenAI via the web_search tool.

## Overview

The Happenstance app now fetches real restaurant and event data using AI-powered web search:
- **Grok/OpenAI** via `web_search` tool for intelligent data retrieval
- Real, current restaurants and events from the target city
- Automatic JSON parsing and validation
- Fallback to fixture data if AI unavailable

## How It Works

1. **Prompt Generation**: The system creates detailed prompts requesting restaurant/event data
2. **AI Search**: Uses Grok/OpenAI through web_search to find real data
3. **JSON Parsing**: Extracts structured JSON from AI responses
4. **Data Integration**: Feeds parsed data into the aggregation pipeline

## Using AI Data Locally

### Step 1: Generate Prompts

```bash
python scripts/fetch_ai_data.py
```

This outputs prompts for restaurants and events.

### Step 2: Get AI Responses

Use the Copilot agent to fetch data:

1. Copy the restaurant prompt
2. Call `web_search` tool with the prompt
3. Save response to `/tmp/ai_restaurants_response.json`

Repeat for events prompt.

### Step 3: Run Aggregate

```bash
export AI_RESTAURANTS_DATA=$(cat /tmp/ai_restaurants_response.json)
export AI_EVENTS_DATA=$(cat /tmp/ai_events_response.json)
python -m happenstance.cli aggregate
```

## GitHub Actions Setup

### Option 1: API Keys (Recommended)

Add these repository secrets (Settings → Secrets → Actions):

1. **GROK_API_KEY**: API key from https://x.ai/api
2. **OPENAI_API_KEY**: API key from https://platform.openai.com/api-keys

With API keys configured, the system will automatically fetch fresh data on each run.

### Option 2: Pre-fetched Data

Alternatively, add these repository secrets:

1. **AI_RESTAURANTS_DATA**: JSON array of restaurants fetched via web_search
2. **AI_EVENTS_DATA**: JSON array of events fetched via web_search

### Fetching Data for Secrets

Use the Copilot agent with web_search tool:

**For Restaurants:**
```
Find 20 popular, real restaurants currently operating in San Francisco.
Include a variety of cuisines: Italian, Sushi, BBQ, Vegan.

Return ONLY a valid JSON array with this structure:
[
  {
    "name": "Restaurant Name",
    "cuisine": "Cuisine Type",
    "address": "Street Address, San Francisco",
    "url": "https://www.google.com/maps/search/?api=1&query=Restaurant+Name+San+Francisco",
    "match_reason": "Brief description",
    "rating": 4.5,
    "price_level": 2
  }
]
```

**For Events:**
```
Find 20 real, upcoming events in San Francisco for the next 30 days.
Include categories: live music, art, family, sports.

Return ONLY a valid JSON array with this structure:
[
  {
    "title": "Event Name",
    "category": "live music",
    "date": "2025-12-20T19:00:00+00:00",
    "location": "Venue Name, San Francisco",
    "url": "https://www.google.com/maps/search/?api=1&query=Event+Name+Venue+San+Francisco"
  }
]
```

Copy the JSON responses and add them as repository secrets.

## Configuration

Edit `config/config_logic.json`:

```json
{
  "data_sources": {
    "restaurants": "ai",
    "events": "ai"
  },
  "api_config": {
    "ai": {
      "city": "San Francisco",
      "restaurant_count": 20,
      "event_count": 20
    }
  }
}
```

## Advantages of AI-Powered Search

1. **No API Keys Needed**: Uses Grok/OpenAI already available to Copilot
2. **Real Data**: Fetches current, real restaurants and events
3. **Flexible**: Can search any city without additional API setup
4. **Intelligent**: AI understands context and provides relevant results
5. **Free**: No additional API costs beyond Copilot usage

## Example Output

**Restaurants** (Real San Francisco data):
- Acquerello (Italian) - Michelin-starred
- State Bird Provisions (New American)
- San Ho Won (Korean BBQ)
- Aíso (Vegan)

**Events** (Real San Francisco events):
- San Francisco Symphony: Disney's Frozen In Concert
- San Francisco 49ers vs. Indianapolis Colts
- Mads Tolling: A Cool Yule (Jazz)
- Family Day at SFMOMA

## Troubleshooting

### "No AI response provided" error
- Set environment variables OR pass ai_response parameter
- Check that JSON is valid

### JSON parsing fails
- Ensure AI response contains valid JSON
- Check for markdown code blocks (```json```)
- Verify array structure

### Falls back to fixture data
- Normal behavior when AI data unavailable
- Check environment variables are set correctly
- Validate JSON structure

## Updating Data

To refresh data:
1. Run web_search with updated prompts
2. Update repository secrets with new JSON
3. Trigger workflow (push to main or manual dispatch)
4. Data updates automatically

## Best Practices

1. **Regular Updates**: Fetch new data weekly/monthly
2. **Validate JSON**: Always check JSON is valid before storing
3. **Review Results**: Ensure AI-provided data is accurate
4. **Monitor Quality**: Check that venues/addresses are real
5. **Fallback Ready**: Keep fixtures updated as fallback

## Cost Considerations

- **Grok/OpenAI via Copilot**: Included in Copilot usage
- **No Additional Costs**: No per-request fees
- **Efficient**: One fetch can be used multiple times via secrets
