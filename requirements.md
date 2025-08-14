# Requirements for Happenstance

## Overview
Happenstance is an AI-powered aggregator for events and restaurants using Python, GitHub Actions, and GitHub Pages. It aggregates data via the Grok API into `static/events.json` and `static/restaurants.json`, with a static front-end featuring toggles for restaurants/events/paired views (client-side matching on category/location based on config pairing_rules), filters, sorting, and light/dark themes. Supports white labeling via a 'profiles' array in `config/config_logic.json` (e.g., select via PROFILE env var). Optionally supports GeoJSON in `region.geo_boundary` for precise location prompts (serialize to string in API calls if present).

## Deployment Stack / Pipeline
- Leverage GitHub Actions for automation: Daily scheduled runs at 5 AM UTC and manual dispatch to aggregate data via Grok API.
- Publishing through GitHub Pages: Static site served from the `static/` directory.
- `GROK_API_KEY` set as a GitHub repository secret, injected as an environment variable in Actions for secure API calls.
- Workflow includes: Run Python script, validate/output JSON, commit changes to `static/*.json` only if data updated, upload debug artifacts on failure, soft-fail on empty results.

## Directory Structure
```
happenstance/ (project root)
├── .github/
│   └── workflows/
│       └── update-data.yml  # GitHub Actions workflow
├── config/
│   └── config_logic.json  # Master config for profiles, prompts, schemas
├── scripts/
│   └── aggregate.py  # Python script for data aggregation (Grok API calls)
├── static/  # Content published via GitHub Pages (HTML/CSS/JS + generated JSON)
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   ├── events.json  # Generated output
│   └── restaurants.json  # Generated output
├── debug/  # Debug logs and artifacts (.gitignore most, upload as artifacts)
│   ├── last_run_raw_events.json
│   ├── last_run_validated_events.json
│   ├── last_run_raw_restaurants.json
│   └── last_run_validated_restaurants.json
├── requirements.txt  # Python dependencies
├── README.md  # Documentation, setup, troubleshooting
└── .gitignore
```

## Configuration: config/config_logic.json
JSON file with a 'profiles' array. Each profile includes:
- `name`: e.g., 'capital_region'
- `region`: Object with `name` (string), `focus` (string for geographic scope), optional `geo_boundary` (GeoJSON Polygon object for precise boundaries, serialized to prompt string if present)
- `sources`: Object with `restaurants` and `events` arrays (e.g., ["Yelp Capital Region", ...])
- `instructions`: String for aggregation guidance
- `user_predilections`: Array of preferences (e.g., ["Prioritize tacos, music events"])
- `branding`: Object with `site_title`, `logo_url`, `badges` (e.g., {"new_restaurant": "Fresh Bite"})
- `pairing_rules`: Array of objects like `{"match_on": "category", "examples": ["food fest -> Mexican"]}`, `{"match_on": "location", "fuzzy_match": true}`
- `json_schema`: Objects defining schemas for events/restaurants arrays (fields: name, address/venue, cuisine/category, description, link, is_new, badge)

## Backend: scripts/aggregate.py
Python script using `requests` and `json`:
- Load `config_logic.json`, select profile from `os.environ.get('PROFILE', 'capital_region')`.
- For the profile, build separate prompts for restaurants/events (inject region.focus, sources, predilections, timeframe, branding; if geo_boundary present, serialize coordinates to string like "geofenced by Polygon with coords [[lon1,lat1],...]").
- Call Grok API (`https://api.x.ai/v1/chat/completions`, model='grok-3-mini', messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, auth Bearer GROK_API_KEY from env).
- Parse/validate JSON arrays against schema, detect is_new by comparing to existing `static/*.json` (use name+address for restaurants, name+venue+date for events), add badges/is_new from branding.
- Write updated JSON to `static/` only if changed.
- Save debug files: `debug/last_run_raw_events.json`, `debug/last_run_validated_events.json`, etc.
- Handle errors, print logs for local debug.
- Optionally generate `static/config.json` with branding/pairing_rules for front-end.

## Front-End: static/index.html
HTML structure:
- `<h1 id="site-title">` for dynamic title
- `<img id="logo" src="">` for logo
- `<select id="view-select">` with options: restaurants, events, paired
- `<select id="theme-select">` with options: light, dark
- `<input id="filter" placeholder="Filter by name/cuisine...">`
- `<div id="content">` for dynamic tables

## Front-End: static/styles.css
Tufte-inspired CSS:
- Sans-serif fonts
- Clean tables with light borders
- `.new-badge {background: #ffcc00; padding: 2px; border-radius: 3px;}`
- `body.light {background: white; color: black;}`
- `body.dark {background: #333; color: white;}` with border adjustments for dark mode

## Front-End: static/app.js
Vanilla JS:
- On load, fetch `static/events.json`, `restaurants.json`, and `static/config.json` (for branding/pairing_rules).
- Set `document.title` and h1 to branding.site_title, logo.src to logo_url.
- Render on view change: tables for restaurants (columns: name/address/cuisine/desc/link/badge with <span class="new-badge">New!</span> if is_new), events (name/date/venue/desc/link/badge), paired (event_name/date, rest_name/cuisine, match_reason—compute using pairing_rules, e.g., if match_on=category check includes, location fuzzy string match on venue/address).
- Add filter (input event filters rows by name/cuisine/category).
- Sorting (th click sorts column asc/desc).
- Theme switch (body.className = value).

## Dependencies: requirements.txt
```
requests
```

## Documentation: README.md
- Instructions: Fork/repo setup, add GROK_API_KEY secret, local debug (export GROK_API_KEY; python scripts/aggregate.py; test front-end with python -m http.server in static/; discard static/*.json changes with git restore before commit).
- Enable Pages on main branch.
- Troubleshooting: Check debug files, API quotas.
- White labeling: Edit/add profiles, set PROFILE in Actions env.
- GeoJSON option: Add to region.geo_boundary for precise prompts.
- Warnings: NEVER commit static/*.json manually—let Actions handle; discard local gens.

## Git Ignore: .gitignore
```
debug/*
__pycache__/
.env
*.pyc
```

## Post-Setup
After creating files, run `git init`, `git add .`, `git commit -m 'Initial setup for Happenstance'`.