# Aggregation Prompt & Output Brief for Provider Feedback

## Problem Statement
We are building an automated multi-pass regional aggregator ("Happenstance") that curates:
- Restaurants (mix of new openings and established reputable venues) for a specific geographic region (New York Capital Region)
- Upcoming events within a configurable future window (currently 120 days)

Goals:
1. Maximize authenticity (avoid fabricated venues or events)
2. Improve breadth & diversity (cuisines, categories, geographic sub-areas) while controlling duplication
3. Leverage live search / citations to prefer verifiable entries
4. Keep token/cost footprint reasonable (now adding pass cap & cost metrics)
5. Allow augmentation via a second provider (OpenAI) while avoiding hallucinated or redundant items

Current Pain Points:
- After multiple passes (xAI + augmentation), valid final counts remain below targets (restaurants target 35 -> ~18; events target 25 -> ~9) due to filtering, possible over-conservatism, or insufficient search breadth.
- Some passes produce low or zero novel items; diminishing returns not detected early.
- Event coverage sparse for certain categories (comedy, theater beyond a few venues, seasonal markets) even though seeds attempt to prompt them.
- Pricing estimation currently uses placeholder xAI rates (needs precise guidance for correct per 1K token cost modeling).
- Augmentation prompt originally *overly strict* ("ONLY additional") likely suppressing returns; recently relaxed but still limited gains.

## Environment & Inputs (Key Variables)
- PROFILE=capital_region (selects region config with sources, branding, json schema, url_groups for live search)
- LIVE_SEARCH_MODE=on (enables xAI SearchParameters with rotating url_groups per pass; limit 5 allowed sites per pass)
- REST_PASSES / EVENT_PASSES (initial multi-pass counts per kind; recently superseded by MAX_RUN_PASSES cap)
- MAX_RUN_PASSES=5 (new cap desired—implementation in progress to prevent >5 total passes per run)
- TARGET_RESTAURANTS=35, TARGET_EVENTS=25 (aspirational counts)
- EVENT_WINDOW_DAYS=120 (filtering window)
- AUGMENT_WITH_OPENAI=1, OPENAI_AUG_PASSES=2 (optional second provider augmentation)
- OPENAI_MODEL=gpt-4o-mini (default if not specified)
- VALIDATION_MODE=soft (heuristics + domain plausibility; may filter out items without acceptable link patterns)
- LINK_HTTP_VALIDATE optionally marks broken links (currently off during most runs)

## Request Construction (xAI / Grok path)
1. Build prompt via `build_prompt(profile, kind, extra_focus)` including:
   - Region name & focus
   - Today date and strict authenticity guardrail text
   - Timeframe guidance (events: upcoming N days; restaurants: currently operating)
   - Source inspiration arrays + user predilections
   - Additional focus seed (e.g., tacos, breweries, live music, art exhibitions) except first base pass
   - Schema field list hint (names only)
   - Live search hint when LIVE_SEARCH_MODE in {on, auto}
2. xAI SDK used with `chat.parse(PydanticWrapper)` returning structured JSON (restaurants[] / events[]). SearchParameters rotate `url_groups` (group order differs for restaurants vs events) with up to 5 allowed websites per pass.
3. Citations & usage data stored (citations_{kind}.json, usage_{kind}.json); domains extracted for metrics.
4. Items accumulate; dedupe (name+address or name+venue+date), plausibility & schema validation, event date window, newness tagging.
5. Per-pass metrics appended to `debug/pass_metrics.json` with: pass index, focus seed, raw_count, citation_domains, provider, tokens, estimated_cost.

### Example xAI Prompt (Restaurant base excerpt)
```
You are an aggregator for Capital Region focusing on Albany / Saratoga / Troy / Schenectady. ...
Today is 2025-08-13. Return ONLY actual, plausible, non-fabricated restaurants...
Inspiration: ["Yelp Capital Region", ...] Predilections: ["Prioritize tacos", ...] Leverage current web search results...
Aim for 30-40 diverse restaurants ... Additional focus: (blank for base)
Return an array of restaurants objects. Fields: ['name','address','cuisine','description','link','is_new','badge']...
```

### Example xAI Prompt (Events focused: live music excerpt)
```
You are an aggregator for Capital Region focusing on Albany / Saratoga / Troy / Schenectady.
Today is 2025-08-13. Return ONLY actual, plausible, non-fabricated events ... upcoming 120 days ...
Inspiration: ["Albany.org events", ...] Predilections: ["Prioritize tacos", "Music events"] Leverage current web search results...
Timeframe / scope: upcoming 120 days. Aim for up to 25 events within 120 days if available. Additional focus: live music.
Return an array of events objects. Fields: ['name','date','venue','category','description','link','is_new','badge']...
```

## Request Construction (OpenAI augmentation)
Augmentation pass adds to the same base prompt:
```
Augmentation pass: Prefer high-confidence real items (new OR established) even if some appeared earlier; you may repeat a small subset (<=25%) if wording can enhance description richness. Avoid fabrications.
```
Returned JSON expected as either `{ "restaurants": [...] }` or `{ "events": [...] }` or direct array (normalized).

## Representative Outputs (Post-Validation Extract)
Restaurants sample (from consolidated list):
```
[
  {"name": "Toro Cantina", "cuisine": "Mexican", ...},
  {"name": "Sheba Al-Yemen", "cuisine": "Ethiopian/Yemeni", ...},
  {"name": "Berben and Wolff's", "cuisine": "Vegan", ...},
  {"name": "Lark Street Taco & Burrito Bar", "cuisine": "Mexican/Tacos", ...},
  {"name": "Villa Di Valletta", "cuisine": "Italian", ...}
]
```
Events sample:
```
[
  {"name": "New York State Food Festival", "date": "2025-08-13", ...},
  {"name": "The American Revolution: An Evening with Ken Burns", "date": "2025-09-10", ...},
  {"name": "The Jinkx & DeLa Holiday Show", "date": "2025-11-29", ...}
]
```

## Metrics Snapshot (Recent Run)
From latest run (run_id 5c3e954d55f5):
- Providers: xai + openai
- Passes (total metrics entries cumulative): 41 (we seek to cap at 5 going forward)
- Final counts: restaurants=18 / events=9 (targets 35 / 25)
- Token totals (cumulative file): prompt 36,784 / completion 13,049
- Cost estimate (placeholder pricing) $204.06 (likely over-estimated; placeholder rates inflated)
- Diminishing returns: later passes add <2 net new validated items.

Per-pass examples (restaurants):
```
Pass 0 (focus=""): raw_count=7 citation_domains=[spectrumlocalnews.com, albany.com, albany.org, wamc.org]
Pass 1 (focus="tacos"): raw_count=10 citation_domains=[albanyny.gov, empirelivealbany.com, ...]
Pass 2 (focus="breweries"): raw_count=9 citation_domains=[discoversaratoga.org, saratoga.com]
```
Events show even steeper early drop-off.

## Observations & Hypotheses
1. Search breadth per pass limited to <=5 allowed sites; rotating groups may miss multi-source corroboration for underrepresented categories (e.g., comedy, niche cultural events) leading to conservative omissions.
2. Hard authenticity wording may bias model toward only high-profile / well-indexed venues; mid-tier but real venues lost.
3. Seed strategy static; after covering tacos/breweries/coffee/brunch, later diversity (Thai, Ethiopian, fine dining, dessert, food trucks) not explicitly prompted unless incidentally included.
4. Event schema requires specific date; some recurring series without concrete next date may be skipped.
5. Augmentation prompt still cautious; allowing partial repetition but not encouraging gap-filling taxonomy (e.g., "Identify missing cuisine types and supply real local examples").
6. Potential over-filtering: VALIDATION_MODE=soft still rejects links failing domain checks; some real smaller venues might have less standard web presence.
7. Dedup heuristic (name+address) may discard legitimate multi-location chains or expansions.

## Questions / Feedback Requests for Providers
1. Prompt Refinement: How to balance strict anti-fabrication with encouraging broader, yet still real, coverage? Suggested patterns or system messages that improve recall without hallucination?
2. Live Search Leverage: Guidance on structuring the search hint or SearchParameters to surface less prominent but real venues/events while maintaining verifiability.
3. Structured Output Reliability: Any best practices (temperature, additional system instructions, incremental JSON schema guidance) to reduce empty arrays or truncated lists?
4. Diversity Targeting: Recommended in-prompt strategies for expressing "fill gaps" (e.g., detect missing cuisine categories) without causing the model to fabricate to satisfy diversity.
5. Event Temporal Filtering: Better phrasing to ensure inclusion of future-dated events across the entire window (currently 120 days) instead of clustering near-term.
6. Cost Efficiency: Suggestions for combining multi-focus requests or batching categories without triggering hallucination, to reduce total passes.
7. Augmentation Strategy: Ideas on a two-stage approach (primary authoritative pass + enrichment/metadata refinement) vs. current additive multi-pass.
8. Citations: Tips to increase citation yield consistency (some passes show limited citation diversity despite different focus seeds).

## Files Provided For Review
Located in `debug/` directory:
- Prompts (xai & openai): `prompt_xai_*` and `prompt_openai_*`
- Raw outputs per pass: `last_run_raw_xai_*`, `last_run_raw_openai_*`
- Validated final outputs: `last_run_validated_restaurants.json`, `last_run_validated_events.json`
- Metrics: `pass_metrics.json`
- Cost summaries & history: `cost_summary.json`, `cost_history.json`
- Citations: `citations_restaurants.json`, `citations_events.json`
- Usage: `usage_restaurants.json`, `usage_events.json`

## Desired Outcomes From Provider Feedback
- Revised base & focus prompt templates
- Recommended maximum effective tokens or content partitioning strategies
- Suggested search configuration adjustments (parameters or phrasing) to broaden coverage
- Guidance on schema or output structuring that improves completeness
- Potential guardrail phrasing improvements to reduce filtering false positives

Thank you for any detailed suggestions you can provide.
