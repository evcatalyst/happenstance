## Happenstance

Static weekend planner for restaurants and events. Data lives in `docs/*.json` and a lightweight UI renders it for GitHub Pages.

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
Pages deploy uses `actions/upload-pages-artifact` + `actions/deploy-pages` from the generated `docs/` output. Generated JSON is published via artifact by default; set `COMMIT_DATA=1` to allow commits when hashes change.

### Troubleshooting
- **Empty output**: ensure `EVENT_WINDOW_DAYS` is large enough and run `python -m happenstance.cli aggregate`.
- **No citations/links**: check that source fixtures in `happenstance/aggregate.py` include URLs.
- **Serve mismatch**: `serve.py` and CLI both serve `docs/`; avoid legacy `static/` paths.
