# Changelog

All notable changes to this project will be documented in this file.
## [0.8.0] - 2025-08-14
### Added
- Commit gating via `COMMIT_DATA` env (suppresses automated commits unless explicitly enabled).
- GitHub Pages deploy workflow (`publish-pages.yml`) using Pages artifact (serves `docs/*.json` without commits).
- Deterministic item hashing (stable sort + transient field stripping) to reduce false-positive change detection.
- Gap analysis prompts (cuisine / category coverage bullets) feeding multi-pass improvement.
- Month distribution scoring & guidance for event spread.
- Link validation (optional) with `LINK_HTTP_VALIDATE` and `LINK_DROP_INVALID`.
- Cost estimation hooks (env overrides `COST_PER_1K_PROMPT`, `COST_PER_1K_COMPLETION`).

### Changed
- Outputs moved / standardized in `docs/` directory (replacing older `static/` references in workflows). 
- Aggregation workflows now always upload artifacts (debug + JSON) regardless of commit outcome.

### Fixed
- Eliminated daily branch divergence caused by timestamp-only JSON churn.
- Resolved earlier indentation / duplication regressions by reverting and applying minimal stable hashing patch.

### Deprecated
- Implicit always-commit behavior replaced by explicit opt-in via environment variable.


Format: YYYY-MM-DD. Reverse chronological. Follows a loose "Keep a Changelog" style. Version numbers are provisional (0.x while iterating quickly) and group coherent feature sets captured during this build-out.

## [0.7.0] - 2025-08-13
### Added
- Live search URL grouping (`url_groups`) in `config/config_logic.json` with categorized high‑quality event sources (general, albany_specific, saratoga, schenectady, troy, venues_arts).
- Dynamic rotation of `url_groups` per aggregation pass (events vs restaurants) honoring API limit (max 5 allowed websites / pass).
- Feedback loop scaffolding: cuisine / category gap detection appended to subsequent pass instructions.
- Citations capture now consistently produced (`citations_*.json`).
- Optional HTTP link validation (HEAD/GET) with debug outputs `link_validation_*.json` and env toggles `LINK_HTTP_VALIDATE`, `LINK_DROP_INVALID`.

### Changed
- `build_search_parameters` now pass-aware (`pass_index`) and profile-aware; enforces API website limit.
- Prompts augmented with live search usage hints when mode is `on`/`auto`.

### Fixed
- Structured parse indentation error resolved in `call_grok` after refactor.

## [0.6.0] - 2025-08-13
### Added
- Modern front-end redesign: card & table layouts, theming tokens, layout + sort controls, counts footer, Inter font.
- Layout toggle (Cards/Table) & sorting selector with dynamic options per view.
- Development server script `scripts/serve.py` (resolves `file://` CORS issues).

### Changed
- Rewrote `styles.css` with design system (CSS variables, dark mode improvements, responsive grid).
- Enhanced `app.js` for cards rendering, sorting, counts, and layout persistence state.

## [0.5.0] - 2025-08-13
### Added
- Profile-driven live search defaults (reads `profile.live_search` and sets env if unset).
- Search prompt augmentation encouraging citation-backed, verifiable items.
- Defensive serialization for citations & usage artifacts.

### Changed
- Multi-pass aggregation now uses environment / profile to enable search (though initial passes produced no citations until later improvements).

### Fixed
- Main function indentation regression (earlier malformed try block) fully rewritten for consistent control flow.

## [0.4.0] - 2025-08-12
### Added
- Structured outputs via `xai-sdk` + Pydantic models (`RestaurantItem`, `EventItem`, wrapper classes) enabling schema-validated parsing.
- Multi-pass seeded aggregation (restaurants & events) with environment-configurable targets (`TARGET_RESTAURANTS`, `TARGET_EVENTS`, `MAX_PROMPT_PASSES`, `PASS_SEEDS_*`).
- Validation modes: `VALIDATION_MODE` = off | soft | strict plus legacy `STRICT_VALIDATION` compatibility.
- Debug artifact expansion (`prompt_*`, `last_run_raw_*`, `last_run_validated_*`).

### Changed
- Replaced single-call + fallback logic with iterative accumulation & dedupe.
- Extended event window (default 120 days via `EVENT_WINDOW_DAYS`).

### Fixed
- Reduced synthetic / templated outputs via stricter prompt guidance and plausibility heuristics.

## [0.3.0] - 2025-08-11
### Added
- Plausibility filtering referencing `config/ground_truth.json` (known restaurants, venues, allowed domains).
- Dedupe heuristics favoring richer descriptions (restaurants) & earliest date (events).
- Newness & badge assignment using prior published JSON snapshots.

### Changed
- Prompt improvements to include established + new restaurants and stronger anti-fabrication language.

## [0.2.0] - 2025-08-10
### Added
- Migration from raw `requests` usage to xAI / OpenAI style SDK (initial integration) retaining fallback path.
- Environment variable controls for model selection (`GROK_MODEL`) and minimum fallback targets.

### Fixed
- Early low-count scenario by introducing fallback / multi-pass concept (precursor to 0.4.0 full implementation).

## [0.1.0] - 2025-08-09
### Added
- Initial repository scaffold: aggregation script (`scripts/aggregate.py`), base profile (`config/config_logic.json`), ground truth seed file, static front-end (`static/index.html`, `app.js`, `styles.css`), GitHub Actions workflow (scheduled aggregation), README, requirements, and debug artifact directory.
- Basic restaurant & event JSON generation with manual schema guidance in prompt.

---

## Unreleased
### Potential / Planned
- Citation-domain gating & weak-link repair pass.
- Snippet summarization for feedback loop (top-N unique citation snippets injected into subsequent prompts).
- Domain allow/deny refinement & canonical URL normalization.
- Profile-driven accent color theming (branding -> CSS variable injection).
- Repair pass for weak or generic directory links (REPAIR_WEAK_LINKS flag).

## Notes
- Dates approximate based on development sequence; multiple commits may have occurred the same day.
- Version numbers are semantic placeholders; increment as features stabilize.

## Prompt / Conversation Context Log
Chronological snapshots of key user (U) and assistant (A) prompt intents that drove changes.

### Phase 0 (Scaffold – v0.1.0)
- U: "Generate the full repository structure..." → A scaffolded initial aggregation script, static site, config, workflow.

### Phase 1 (Authenticity & Volume – v0.2.0 / v0.3.0)
- U: "Most of the results seem to be not real" → Added plausibility filtering, ground truth references.
- U: "There's not that many results" → Introduced multi-pass concept & target counts.

### Phase 2 (SDK Migration – v0.2.0)
- U: "Update the code to use the xai sdk for python" → Migrated to SDK (structured JSON mode placeholder).

### Phase 3 (Structured Outputs & Validation – v0.4.0)
- U: Request for "structured outputs (Pydantic) and maybe live search" → Implemented Pydantic models & multi-pass seeding.
- U: Concern about strict filtering reducing counts → Added VALIDATION_MODE (off/soft/strict).

### Phase 4 (Live Search Enablement – v0.5.0)
- U: "Can you confirm if live search is even enabled?" → Diagnosis revealed env defaults off; integrated profile-driven defaults & prompt hint.
- Issues: Indentation regression fixed after search integration attempt.

### Phase 5 (Frontend Modernization – v0.6.0)
- U: "Static index doesn’t work via Safari file://" → Added `serve.py` + guidance.
- U: "Style not like earlier ‘chitte’ look" → Full UI redesign (cards, tokens, layout switcher).

### Phase 6 (Link Quality & Citations – v0.7.0)
- U: "Links don't go where they belong—best validation?" → Added HTTP link validation, discussed verification strategies.
- U provided long optimization prompt ("Yo, Foodie Firebrand...") → Implemented url_groups rotation, pass-aware search parameters, feedback scaffolding, citation capture improvements.

### Misc Debug / Enhancements
- Iterative: Serialization errors (citations) fixed, search parameter API limit handling (max 5 websites) added after INVALID_ARGUMENT response.
- Added CHANGELOG on request; extended with this prompt log section on follow-up request.

### Future Prompt Hooks (Planned Section Alignment)
- Anticipated prompts around: "Filter items to those with citation domain", "Repair generic directory links", "Inject dynamic accent color from profile" – mapped to Unreleased roadmap entries.

---
