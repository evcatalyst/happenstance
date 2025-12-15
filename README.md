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

The system supports both **fixture (demo) data** and **real AI-powered data sources**:

**Fixture Data** (default fallback):
- Uses hardcoded sample restaurants and events
- No setup required
- Perfect for testing and development

**AI-Powered Data** (Grok/OpenAI via web_search):
Configure in `config/config_logic.json`:
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

**Setting Up AI Data**:

The system uses **Grok and OpenAI** (available through GitHub Copilot) to fetch real restaurant and event data via intelligent web search. See `docs/AI_SETUP.md` for complete instructions.

**Quick Start**:
1. Generate prompts: `python scripts/fetch_ai_data.py`
2. Use Copilot agent's `web_search` tool with the prompts
3. Set environment variables with the JSON responses:
   ```bash
   export AI_RESTAURANTS_DATA=$(cat /tmp/ai_restaurants_response.json)
   export AI_EVENTS_DATA=$(cat /tmp/ai_events_response.json)
   ```
4. Run: `python -m happenstance.cli aggregate`

**For GitHub Actions**: Add AI-fetched data as repository secrets:
- Go to repository Settings → Secrets and variables → Actions
- Add secrets: `AI_RESTAURANTS_DATA` (JSON array), `AI_EVENTS_DATA` (JSON array)
- See `docs/AI_SETUP.md` for detailed instructions

**Advantages**:
- ✅ Uses existing Grok/OpenAI access (no additional API keys needed)
- ✅ Fetches real, current data from any city
- ✅ Intelligent search and parsing
- ✅ Automatic fallback to fixture data
- ✅ No per-request costs

The system automatically falls back to fixture data if AI responses are not provided, ensuring the site always has data to display.

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
