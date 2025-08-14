# Happenstance

AI-powered aggregator for restaurants and events with static front-end.

## Features
- Aggregates via Grok / xAI API into `static/events.json` and `static/restaurants.json`
- Front-end toggles: restaurants / events / paired views
- Filtering, sorting, light/dark themes
- White labeling via profiles in `config/config_logic.json`
- Optional GeoJSON polygon for precise prompts
 - Structured Outputs (Pydantic via xai-sdk) for type-safe JSON
 - Optional Live Search (web/news/X/RSS) with citation capture

## Setup
1. Fork / clone repo.
2. Create a GitHub Environment named `beta` (Settings > Environments) and add secrets there:
	- `GROK_API_KEY` (xAI / Grok key)
	- (Optional) `OPENAI_API_KEY` (for augmentation) and set a secret `AUGMENT_WITH_OPENAI` = `1` if you want it always on.
	- (Optional) `XAI_API_KEY` if you prefer that variable name – workflow exports both.
	The scheduled workflow targets the `beta` environment so only these environment‑scoped secrets are used.
3. (Optional) Add more profiles in `config/config_logic.json`.
4. Enable GitHub Pages (Settings > Pages) to serve from `main` branch `static/` directory (or root then link).

## Local Development
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GROK_API_KEY=YOUR_KEY
python scripts/aggregate.py
# Serve static site
(cd static && python -m http.server 8000)
# Visit http://localhost:8000
```
Discard generated JSON before committing if you ran locally:
```bash
git restore static/events.json static/restaurants.json || true
```

## Environment Variables (Aggregation)
| Var | Purpose | Default |
|-----|---------|---------|
| GROK_API_KEY / XAI_API_KEY | API key auth | (required) |
| GROK_MODEL | Model name | grok-3 |
| PROFILE | Profile selection | capital_region |
| EVENT_WINDOW_DAYS | Future days to allow events | 120 |
| STRICT_VALIDATION | 1 enables ground-truth plausibility filter | 0 |
| MIN_RESTAURANTS | Fallback min target | 10 |
| MIN_EVENTS | Fallback min target | 10 |
| LIVE_SEARCH_MODE | off|auto|on to enable live search | off |
| LIVE_SEARCH_MAX_RESULTS | Max sources to fetch | 15 |
| LIVE_SEARCH_ALLOWED_SITES | Comma sites allow-list (web) | (blank) |
| LIVE_SEARCH_COUNTRY | ISO alpha-2 for web/news | (blank) |
| LIVE_SEARCH_FROM_DATE | Search from date (YYYY-MM-DD) | (blank) |
| LIVE_SEARCH_TO_DATE | Search to date (YYYY-MM-DD) | (blank) |
| LIVE_SEARCH_INCLUDE_X | 1 to include X posts (events focus) | 0 |
| LIVE_SEARCH_INCLUDE_NEWS | 1 to include news sources | 0 |
| LIVE_SEARCH_RSS | Single RSS feed URL | (blank) |

## Profiles / White Labeling
- Edit / add profiles in `config/config_logic.json`.
- Each profile: name, region, sources, instructions, user_predilections, branding, pairing_rules, json_schema.
- Set `PROFILE` env in workflow or locally: `PROFILE=capital_region python scripts/aggregate.py`.

## Geo Boundary
Add `region.geo_boundary` as a GeoJSON Polygon to narrow prompts. Example:
```json
"geo_boundary": {"type":"Polygon","coordinates":[[[-73.8,42.6],[-73.7,42.6],[-73.7,42.7],[-73.8,42.7],[-73.8,42.6]]]} 
```
Will be serialized into the prompt as a geofence hint.

## GitHub Actions
- Scheduled daily run at 05:00 UTC plus manual dispatch.
- Uses Environment `beta` (scoped secrets) with exported vars: `GROK_API_KEY`, optional `XAI_API_KEY`, `OPENAI_API_KEY`, `AUGMENT_WITH_OPENAI`, and `MAX_RUN_PASSES=5`.
- Commits only if JSON changed.
- Uploads debug artifacts from `debug/` (review in run summary under artifacts).

## Troubleshooting
- Empty output: check debug artifacts (raw vs validated) in workflow run.
- Invalid JSON: inspect `last_run_raw_*.json` and adjust instructions.
- API errors: confirm secret exists / quotas / network.
- Citations missing: set `LIVE_SEARCH_MODE=auto` (or on) & ensure xai-sdk installed.
- Structured outputs disabled: install deps (`pip install -r requirements.txt`). Fallback uses JSON parsing.

## Warnings
- NEVER manually edit or commit `static/events.json` or `static/restaurants.json` (let CI handle).
- Always restore or discard local generated JSON changes before commit.

## License
MIT (add a LICENSE file as needed).

## Live Search Quick Start
```
export LIVE_SEARCH_MODE=auto
export LIVE_SEARCH_INCLUDE_NEWS=1
export LIVE_SEARCH_ALLOWED_SITES="timesunion.com,albany.com"
python scripts/aggregate.py
```
Check `debug/citations_*.json` for source URLs powering entries.

## Structured Outputs
With `xai-sdk` present the script uses strongly typed Pydantic models for restaurants & events, guaranteeing schema adherence. Without it, it falls back to classic JSON response formatting.
