## Happenstance

Static weekend planner for restaurants and events. Data lives in `docs/*.json` and a lightweight UI renders it for GitHub Pages.

### 🌐 Live Demo

**[View the live app →](https://evcatalyst.github.io/happenstance/)**

The app is automatically deployed to GitHub Pages daily and on every push to `main`. Browse restaurants, events, and paired recommendations with filtering and multiple layout options.

**How to use:**
- **Restaurants tab**: Browse dining options filtered by cuisine or keywords
- **Events tab**: Explore upcoming events by category (art, music, family, etc.)
- **Paired tab**: See recommended restaurant + event combinations for a complete evening
- **Filter**: Use the search box to filter by keywords or categories
- **Layout**: Toggle between card view (visual) and table view (compact)

The app loads data from JSON files and indicates readiness with `data-hs-ready="1"` on the `<body>` element.

### Quickstart
```bash
pip install -r requirements.txt
python -m happenstance.cli aggregate
python -m happenstance.cli serve  # or make dev
```

Open http://localhost:8000 to browse the UI. The readiness signal is `data-hs-ready="1"` on the `<body>` once data loads.

### Profiles & Environment
Configure profiles in `config/config_logic.json`. Environment overrides:
- `PROFILE` – profile name (default: `default`)
- `LIVE_SEARCH_MODE` – live search mode hint
- `EVENT_WINDOW_DAYS` – days ahead for events filter
- `BASE_URL` – override base URL
- `COMMIT_DATA` – set to `1` to allow committing generated JSON (artifact deploy is default)

### Data Sources

The system supports both **fixture (demo) data** and **real API-powered data sources**:

**Fixture Data** (default fallback):
- Uses hardcoded sample restaurants and events
- No setup required
- Perfect for testing and development

**API-Powered Data** (Google Places, Ticketmaster):
Configure in `config/config_logic.json`:
```json
{
  "data_sources": {
    "restaurants": "google_places",
    "events": "ticketmaster"
  },
  "api_config": {
    "google_places": {
      "city": "San Francisco",
      "radius": 5000,
      "count": 20
    },
    "ticketmaster": {
      "city": "San Francisco",
      "count": 20
    }
  }
}
```

**Setting Up API Data**:

The system uses **Google Places** and **Ticketmaster** APIs to fetch real restaurant and event data. See `docs/API_SETUP.md` for complete instructions.

**Quick Start**:
1. Get API keys from Google Places and Ticketmaster (see `docs/API_SETUP.md`)
2. Set environment variables:
   ```bash
   export GOOGLE_PLACES_API_KEY="your_google_key"
   export TICKETMASTER_API_KEY="your_ticketmaster_key"
   ```
3. Run: `python -m happenstance.cli aggregate`

**For GitHub Actions**: Add API keys as repository secrets:
- Go to repository Settings → Secrets and variables → Actions
- Add secrets: `GOOGLE_PLACES_API_KEY`, `TICKETMASTER_API_KEY`
- See `docs/API_SETUP.md` for detailed instructions

**AI-Powered Data** (Alternative):

As an alternative to traditional APIs, you can use AI-powered search (Grok/OpenAI). See `docs/AI_SETUP.md` for instructions.

**Advantages**:
- ✅ Real, current data from any city
- ✅ Automatic fallback to fixture data
- ✅ Multiple data source options (APIs or AI)
- ✅ No per-request costs with free API tiers
- ✅ Flexible configuration

The system automatically falls back to fixture data if API keys are not provided, ensuring the site always has data to display.

### CLI
```
python -m happenstance.cli aggregate   # writes docs/*.json
python -m happenstance.cli serve       # serves docs/ (PORT defaults to 8000)
```

### Testing
- Lint: `ruff check .`
- Unit/contract: `pytest`
- E2E (Playwright): `npm run test:e2e` (needs `npx playwright install --with-deps chromium`)
- Make targets: `make test`, `make e2e`

### GitHub Pages

**Live site**: [https://evcatalyst.github.io/happenstance/](https://evcatalyst.github.io/happenstance/)

The site is automatically deployed using GitHub Actions:
- **Automatic deployment**: Runs on every push to `main`, daily at 6 AM UTC via cron schedule, or manually via workflow dispatch
- **Workflow**: `.github/workflows/pages.yml` handles build and deployment
- **Process**: 
  1. Runs `python -m happenstance.cli aggregate` to generate fresh JSON data
  2. Uploads the `docs/` directory as a GitHub Pages artifact
  3. Deploys to GitHub Pages
- **Validation**: `.github/workflows/validate-pages.yml` checks that published endpoints are accessible and contain valid data

Pages deploy uses `actions/upload-pages-artifact` + `actions/deploy-pages` from the generated `docs/` output. Generated JSON is published via artifact by default; set `COMMIT_DATA=1` to allow commits when hashes change.

### Troubleshooting
- **Empty output**: ensure `EVENT_WINDOW_DAYS` is large enough and run `python -m happenstance.cli aggregate`.
- **No citations/links**: check that source fixtures in `happenstance/aggregate.py` include URLs.
- **Serve mismatch**: `serve.py` and CLI both serve `docs/`; avoid legacy `static/` paths.
