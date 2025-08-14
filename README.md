# Happenstance

AI-powered restaurants & events aggregation pipeline with multi-pass LLM synthesis, live search enrichment, structured outputs, deterministic change detection, and GitHub Pages deployment (no noisy commits by default).

## Features
Core
- Multi-pass aggregation (feedback loops, gap analysis) via xAI Grok with optional OpenAI augmentation.
- Structured Outputs (Pydantic via `xai-sdk`) for type-safe JSON parsing; fallback JSON mode if SDK absent.
- Deterministic hashing + meta sentinel to detect real item changes vs timestamp churn.
- Outputs in `docs/` (`events.json`, `restaurants.json`, `config.json`, `meta.json`).

Enrichment
- Live Search (web / news / X / RSS) with rotating URL groups & citation capture.
- Link validation (optional HTTP HEAD/GET) and citation debug artifacts.
- Gap detection (cuisine / category coverage bullets) feeding subsequent passes.
- Month distribution scoring for event spread.

Front-End (static)
- Toggle views: restaurants / events / paired.
- Sorting, filtering, light/dark themes, badge + newness indicators.
- White labeling (profiles) and optional geo boundary.

DevOps
- Commit gating: `COMMIT_DATA` env flag suppresses noisy automated commits by default.
- GitHub Pages deployment using a Pages artifact (`publish-pages.yml`) – serves latest JSON without commits.
- Always-uploaded artifacts for generated JSON & debug traces for inspection.

## Setup (Local)
```bash
git clone https://github.com/<you>/happenstance.git
cd happenstance
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GROK_API_KEY=YOUR_XAI_KEY
python scripts/aggregate.py
python -m http.server -d docs 8000  # or any static server
open http://localhost:8000
```

Discard generated JSON before committing (they’re CI managed):
```bash
git restore docs/events.json docs/restaurants.json docs/meta.json 2>/dev/null || true
```

## GitHub Actions / Environments
1. Create Environment `beta` and add secrets:
	- `GROK_API_KEY` (required)
	- `OPENAI_API_KEY` + `AUGMENT_WITH_OPENAI=1` (optional augmentation)
	- `XAI_API_KEY` (optional alias – supported by script)
2. (Optional) Add profile overrides in `config/config_logic.json`.
3. `update-data.yml` runs daily (05:00 UTC) + manual dispatch; it generates JSON & uploads artifacts.
4. Commits happen only if `COMMIT_DATA=1` (Repository / Org variable or workflow override). Default = `0` to avoid divergence.
5. `publish-pages.yml` (05:30 UTC + manual) deploys `docs/` via a Pages artifact, serving JSON publicly without committing them.

### Publishing Flow
Two modes:
| Mode | How | Pros | Cons |
|------|-----|------|------|
| Artifact + Pages (default) | `publish-pages.yml` deploy | No commit noise, fast, immutable snapshot | History of JSON not in git |
| Commit (opt-in) | Set `COMMIT_DATA=1` and re-run update workflow | Versioned JSON in repo | Branch churn if frequent |

Force a Pages redeploy without content change: manually dispatch `Publish Docs to GitHub Pages` with `force_deploy=true`.

git restore static/events.json static/restaurants.json || true
## Local Development Tips
| Task | Command |
|------|---------|
| Run a single aggregation pass limit | `MAX_RUN_PASSES=1 python scripts/aggregate.py` |
| Enable live search heuristics | `LIVE_SEARCH_MODE=auto` |
| Include X posts & news | `LIVE_SEARCH_INCLUDE_X=1 LIVE_SEARCH_INCLUDE_NEWS=1 python scripts/aggregate.py` |
| Strict validation off (debug raw volume) | `VALIDATION_MODE=off` |
| Link validation drop invalid | `LINK_HTTP_VALIDATE=1 LINK_DROP_INVALID=1` |
| Dry run (skip external LLM/API calls) | `DRY_RUN=1 python scripts/aggregate.py` |

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
| LINK_HTTP_VALIDATE | 1 to perform HTTP HEAD/GET on links | 0 |
| LINK_DROP_INVALID | 1 to exclude items whose link fails validation | 0 |
| DRY_RUN | 1 skips external LLM/search calls (generates prompts + empty results) | 0 |
| COMMIT_DATA | 1 to allow workflow commits | 0 |
| COST_PER_1K_PROMPT | Override pricing prompt tokens | 0 |
| COST_PER_1K_COMPLETION | Override pricing completion tokens | 0 |

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

## GitHub Actions (Details)
Workflows:
- `update-data.yml` (main) & `update-data-beta.yml` (beta branch) – aggregation with commit gating + artifact uploads.
- `publish-pages.yml` – deploys `docs/` to GitHub Pages (Actions source) without commits.

Deterministic Change Detection:
- Items list hashed after stable sort & transient field stripping; `_meta.items_changed` set accordingly. Prevents daily timestamp-only commits.

Artifacts:
- `docs-json*` – generated JSON (download if commits suppressed)
- `debug-*` – prompts, citations, link validation, raw vs validated outputs

To enable commits permanently, define repository variable `COMMIT_DATA=1` then re-run workflow or wait for next schedule.

## Troubleshooting
- Empty output: check debug artifacts (raw vs validated) in workflow run.
- Invalid JSON: inspect `last_run_raw_*.json` and adjust instructions.
- API errors: confirm secret exists / quotas / network.
- Citations missing: set `LIVE_SEARCH_MODE=auto` (or on) & ensure xai-sdk installed.
- Structured outputs disabled: install deps (`pip install -r requirements.txt`). Fallback uses JSON parsing.

## Warnings
- Avoid manually editing generated JSON in `docs/` – CI overwrites it.
- If you temporarily commit changes for testing, revert before enabling automated commits to prevent noisy diffs.

## Pages Deployment
Ensure repository Settings > Pages: Source = GitHub Actions.
First run: Manually dispatch `Publish Docs to GitHub Pages` to seed. Files served at:
`https://<owner>.github.io/<repo>/events.json` etc.
Cache bust in clients with a query param (e.g. `events.json?v=2025-08-14`).

## License
MIT – see `LICENSE`.

## Live Search Quick Start
```
export LIVE_SEARCH_MODE=auto
export LIVE_SEARCH_INCLUDE_NEWS=1
export LIVE_SEARCH_ALLOWED_SITES="timesunion.com,albany.com"
python scripts/aggregate.py
```
Check `debug/citations_*.json` for source URLs powering entries.

## Structured Outputs
With `xai-sdk` present the script uses strongly typed Pydantic models for restaurants & events. Missing SDK? Script falls back to JSON parse path (less strict) – install `xai-sdk` for full guarantees.

## Maintenance & Versioning
Semantic-ish 0.x increments capturing cohesive feature batches (see `CHANGELOG.md`). After API + schema stabilize, move to 1.0. Use `MAINTENANCE.md` for operational runbook.

## Contributing
See `CONTRIBUTING.md` for guidelines (issues, PR style, commit hygiene, branching, release steps).
