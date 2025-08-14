# Requirements for Happenstance

## Overview
Happenstance aggregates restaurant & event intelligence using multi-pass LLM calls (xAI Grok) enriched by live search, structured outputs, and feedback loops. Results are published as JSON in `docs/` and optionally deployed to GitHub Pages via an artifact workflow (no commits required). White labeling (profiles), geo boundary, link validation, gap analysis, and deterministic change detection round out the pipeline.

## Deployment Stack / Pipeline
- Aggregation workflows (`update-data*.yml`) run daily (05:00 UTC) and on demand.
- Commit gating: `COMMIT_DATA=1` required to persist JSON to git; otherwise artifacts only.
- Pages publish workflow (`publish-pages.yml`) deploys `docs/` via `actions/upload-pages-artifact` + `actions/deploy-pages` (05:30 UTC).
- Secrets provided through Environment `beta` (`GROK_API_KEY`, optional `OPENAI_API_KEY`, `AUGMENT_WITH_OPENAI`).

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
├── docs/  # Publicly served JSON + static site (deployed via Pages artifact)
│   ├── index.html / app.js / styles.css (if colocated) *or static front-end assets*
│   ├── events.json
│   ├── restaurants.json
│   ├── meta.json
│   └── config.json
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

## Backend: scripts/aggregate.py (Key Capabilities)
- Multi-pass loops with pass indexing, dynamic URL group rotation (live search domain subsets).
- Structured parsing via Pydantic models (xai-sdk) with fallback JSON parse if SDK absent.
- Gap analysis injection (coverage bullets) & month spread scoring for events balance.
- Deterministic canonical hashing (stable sort of items + transient field stripping) sets `_meta.items_changed`.
- Link validation (HEAD/GET) & drop invalid (flags) with debug artifacts.
- Cost estimation scaffolding using pricing maps or env overrides.

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
openai>=1.0.0
xai-sdk>=0.2.0
pydantic>=2.7.0
```
Optional (future / local only) could include: `tqdm`, `rich` for progress / logging (not required currently).

## Documentation Assets
- `README.md` – setup, workflows, commit gating, Pages publish model.
- `CHANGELOG.md` – versioned feature history.
- `CONTRIBUTING.md` – contribution & PR guidelines (added).
- `MAINTENANCE.md` – operational runbook (added).
- `LICENSE` – MIT.

## Git Ignore: .gitignore
```
debug/*
__pycache__/
.env
*.pyc
```

## Maintenance
See `MAINTENANCE.md` for:
- Rotating secrets
- Pricing override adjustments
- Manual publish & force deploy instructions
- Adding new live search URL groups
- Bumping dependency versions & verifying structured parsing

## Contribution Workflow Summary
1. Branch from `beta`: `feat/<short-desc>`
2. Add/update tests / docs (if added later) & run aggregation locally with `MAX_RUN_PASSES=1` for speed.
3. Open PR -> ensure Actions pass.
4. Merge to `beta` (squash or rebase preferred). Promote to `main` after stabilization.