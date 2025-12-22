# Happenstance - Bug Fix List

## Overview

This document tracks known bugs, issues, and technical debt in the Happenstance platform. Issues are categorized by severity and component.

**Priority Levels:**
- 🔴 **CRITICAL**: Breaks core functionality, must fix immediately
- 🟠 **HIGH**: Significant impact on user experience, fix within 1 week
- 🟡 **MEDIUM**: Moderate impact, fix within 1 month
- 🟢 **LOW**: Minor impact, fix when convenient
- 🔵 **ENHANCEMENT**: Not a bug, but improvement opportunity

**Last Updated:** December 21, 2024

---

## Table of Contents
1. [Critical Bugs](#critical-bugs)
2. [High Priority Bugs](#high-priority-bugs)
3. [Medium Priority Bugs](#medium-priority-bugs)
4. [Low Priority Bugs](#low-priority-bugs)
5. [Technical Debt](#technical-debt)
6. [Enhancement Requests](#enhancement-requests)

---

## Critical Bugs 🔴

### None Currently Identified ✅

All critical functionality is working as expected. Core features (data aggregation, UI rendering, deployment) are operational.

---

## High Priority Bugs 🟠

### BUG-001: Geocoding Failures in Restricted Environments
**Component:** Backend (aggregate.py)  
**Severity:** 🟠 HIGH  
**Reported:** December 2024  

**Description:**
The geocoding function `_geocode_address()` fails when network access to `nominatim.openstreetmap.org` is blocked or unavailable. This results in warnings during data aggregation and missing latitude/longitude coordinates for events.

**Impact:**
- Events don't get geocoded locations
- Distance calculations between events and restaurants fail
- Pairing algorithm can't find nearby restaurants
- Warnings clutter the build logs

**Reproduction Steps:**
```bash
python -m happenstance.cli aggregate
# Observe: "Geocoding failed for ..." warnings
```

**Current Workaround:**
Events without geocoded locations fall back to None, and distance-based features are disabled for those events.

**Proposed Fix:**
1. Add geocoding cache (JSON file) to avoid re-geocoding same addresses
2. Use Google Geocoding API as fallback (when API key available)
3. Allow manual coordinate specification in config
4. Better error handling with retry logic

**Code Location:**
- `happenstance/aggregate.py:_geocode_address()` (lines 63-109)

**Priority Justification:**
While the app still functions, missing geocoding significantly degrades the pairing feature quality.

---

### BUG-002: Slow Build Times Due to Serial Geocoding
**Component:** Backend (aggregate.py)  
**Severity:** 🟠 HIGH  
**Reported:** December 2024  

**Description:**
Geocoding is performed serially with 1-second delays between requests (to respect Nominatim rate limits), causing build times of 15-30 seconds when processing 20+ events.

**Impact:**
- Slow GitHub Actions workflows (30+ seconds)
- Poor local development experience
- Delays in deploying updates

**Reproduction Steps:**
```bash
time python -m happenstance.cli aggregate
# Real time: 0m 30s (with 20 events)
```

**Proposed Fix:**
1. Implement geocoding cache (persistent JSON file)
2. Only geocode new/changed addresses
3. Use batch geocoding APIs when available
4. Parallelize with rate limiting (e.g., 1 request per second across threads)

**Code Location:**
- `happenstance/aggregate.py:_geocode_address()` (line 100: `time.sleep(1)`)
- `happenstance/aggregate.py:aggregate()` (geocoding loop)

**Priority Justification:**
Build time directly impacts iteration speed and deployment frequency.

---

### BUG-003: AI Data Source Parsing Failures
**Component:** Backend (sources.py)  
**Severity:** 🟠 HIGH  
**Reported:** December 2024  

**Description:**
The AI-powered data source (`fetch_ai_restaurants`, `fetch_ai_events`) expects JSON in a specific format (markdown code block with JSON array). If the AI returns data in a different format (plain JSON, JSON object instead of array, etc.), parsing fails silently and falls back to fixture data.

**Impact:**
- AI data source not usable with all AI providers
- Inconsistent behavior based on AI response format
- No clear error messages to user

**Reproduction Steps:**
```bash
export AI_RESTAURANTS_DATA='{"restaurants": [...]}'  # JSON object, not array
python -m happenstance.cli aggregate
# Silently falls back to fixtures without clear error
```

**Proposed Fix:**
1. More robust JSON parsing (handle objects, arrays, markdown, plain text)
2. Better error messages indicating what format was expected
3. Schema validation with helpful error output
4. Support multiple AI response formats

**Code Location:**
- `happenstance/sources.py:_parse_json_from_text()` (lines 20-43)
- `happenstance/sources.py:fetch_ai_restaurants()` (lines 273-328)

**Priority Justification:**
AI data source is a key feature for users without API keys.

---

## Medium Priority Bugs 🟡

### BUG-004: No Error Handling for Malformed JSON Files
**Component:** Backend (io.py)  
**Severity:** 🟡 MEDIUM  
**Reported:** December 2024  

**Description:**
If a generated JSON file (restaurants.json, events.json, etc.) is malformed or corrupted, the frontend loads but displays no data. No error message is shown to the user.

**Impact:**
- Silent failure in UI
- Users see empty views with no explanation
- Difficult to debug for non-technical users

**Reproduction Steps:**
```bash
# Corrupt a JSON file
echo "invalid json" > docs/restaurants.json
# Load the app - no error shown, just empty view
```

**Proposed Fix:**
1. Add JSON schema validation in build process
2. Frontend: try/catch around JSON parsing with error UI
3. Add `data-hs-error` attribute on body when data fails to load
4. Display user-friendly error message

**Code Location:**
- `docs/app.js:loadData()` (lines 230-249)
- `happenstance/io.py:write_json()` (lines 20-24)

**Priority Justification:**
Error handling improves user experience and debuggability.

---

### BUG-005: Filter Input Not Debounced
**Component:** Frontend (app.js)  
**Severity:** 🟡 MEDIUM  
**Reported:** December 2024  

**Description:**
The filter input re-renders on every keystroke without debouncing. With large datasets (100+ items), this could cause performance issues and make typing feel sluggish.

**Impact:**
- Potential performance issues with large datasets
- Unnecessary re-renders on every keypress

**Current Behavior:**
```javascript
filterInput.addEventListener("input", () => {
  state.filter = filterInput.value;
  render(); // Called immediately on every keystroke
});
```

**Proposed Fix:**
```javascript
// Debounce render by 150ms
let debounceTimer;
filterInput.addEventListener("input", () => {
  state.filter = filterInput.value;
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(render, 150);
});
```

**Code Location:**
- `docs/app.js` (event listener for filter input, line ~252)

**Priority Justification:**
Not critical with current dataset size, but will become important as data grows.

---

### BUG-006: Pairing Match Reasons Too Generic
**Component:** Backend (aggregate.py)  
**Severity:** 🟡 MEDIUM  
**Reported:** December 2024  

**Description:**
The pairing algorithm generates match reasons like "Great for live music + Italian" but doesn't leverage more sophisticated matching from the `pairing.py` module which has detailed scoring and reasoning.

**Impact:**
- Less helpful recommendations
- Doesn't showcase the advanced pairing algorithm
- Generic explanations don't help users make decisions

**Current Implementation:**
```python
# In _build_pairings()
match_reason = f"Great for {event_category} + {restaurant_cuisine}"
```

**Proposed Fix:**
1. Integrate `pairing.py` module into aggregate process
2. Use `PairingRecommendation.whyMatched` field
3. Generate detailed reasons based on service style, travel time, cuisine fit

**Code Location:**
- `happenstance/aggregate.py:_build_pairings()` (lines 370-445)
- `happenstance/pairing.py` (ready to use but not integrated)

**Priority Justification:**
Better match reasons increase user trust and engagement.

---

### BUG-007: Missing Event End Times
**Component:** Backend (sources.py, aggregate.py)  
**Severity:** 🟡 MEDIUM  
**Reported:** December 2024  

**Description:**
Many events don't have end times, only start times. This makes the pairing algorithm use default duration (2 hours) which may be inaccurate for some event types.

**Impact:**
- Less accurate pairing recommendations for AFTER_EVENT meal intent
- Can't properly calculate dining windows

**Proposed Fix:**
1. Infer end times based on event type (concerts: 2-3 hours, sports: 2.5-3 hours, etc.)
2. Fetch duration from API if available
3. Add manual duration overrides in config

**Code Location:**
- `happenstance/sources.py` (all event fetchers)
- `happenstance/pairing.py:_compute_dining_windows()` (uses durationMinutes)

**Priority Justification:**
Improves pairing accuracy but has reasonable defaults.

---

## Low Priority Bugs 🟢

### BUG-008: No Loading State in UI
**Component:** Frontend (app.js)  
**Severity:** 🟢 LOW  
**Reported:** December 2024  

**Description:**
When the app first loads, there's a brief moment where the UI shows empty sections before data loads. No loading spinner or skeleton UI is shown.

**Impact:**
- Slight visual jarring on initial load
- User may think app is broken during slow network

**Proposed Fix:**
```javascript
// Show loading state before fetch
document.body.classList.add('loading');

loadData().then(() => {
  document.body.classList.remove('loading');
});
```

```css
body.loading main {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 80vh;
}
body.loading main::after {
  content: "Loading...";
  font-size: 24px;
}
```

**Code Location:**
- `docs/app.js:loadData()` (lines 230-249)
- `docs/styles.css` (add loading styles)

**Priority Justification:**
Minor UX polish, app loads fast enough that it's rarely noticed.

---

### BUG-009: Inconsistent Date Formatting
**Component:** Frontend (app.js)  
**Severity:** 🟢 LOW  
**Reported:** December 2024  

**Description:**
Event dates are formatted using `toLocaleDateString()` which varies by user's browser locale. This can cause confusion if user expects consistent format.

**Current Behavior:**
```javascript
formatEventDate(dateString) {
  return new Date(dateString).toLocaleDateString('en-US', { 
    weekday: 'short', month: 'short', day: 'numeric', 
    year: 'numeric', hour: '2-digit', minute: '2-digit' 
  });
}
// Output: "Fri, Jan 15, 2025, 7:00 PM"
```

**Proposed Fix:**
1. Use consistent ISO format or configurable format
2. Add "Relative time" option ("Tonight at 7 PM", "Tomorrow at 2 PM")
3. Localize properly based on user preference

**Code Location:**
- `docs/app.js:formatEventDate()` (lines 62-70)

**Priority Justification:**
Cosmetic issue, current format is readable.

---

### BUG-010: External Links Open in Same Tab (Some Cases)
**Component:** Frontend (index.html, app.js)  
**Severity:** 🟢 LOW  
**Reported:** December 2024  

**Description:**
While most external links have `target="_blank" rel="noopener"`, there may be edge cases where this is missing, causing users to navigate away from the app.

**Impact:**
- User loses their place in the app
- Extra click to return

**Proposed Fix:**
1. Audit all links in HTML and JS-generated content
2. Ensure consistent `target="_blank" rel="noopener"`
3. Add test to verify external links behavior

**Code Location:**
- `docs/app.js` (all link generation in render functions)
- `docs/index.html`

**Priority Justification:**
Low impact, most links are already correct.

---

## Technical Debt 🔧

### DEBT-001: No Automated E2E Tests for UI
**Component:** Testing (Playwright)  
**Severity:** 🟡 MEDIUM  

**Description:**
While there's a Playwright setup (`package.json` has `@playwright/test`), there are no E2E tests written. UI changes are only manually tested.

**Impact:**
- Risk of UI regressions
- Manual testing is time-consuming
- No CI validation of frontend

**Proposed Fix:**
1. Write E2E tests for core user journeys:
   - Load app and see restaurants
   - Switch between views
   - Filter data
   - Click through to external links
2. Run in GitHub Actions CI

**Code Location:**
- `tests/` directory (missing E2E tests)
- `.github/workflows/ci.yml` (no E2E test step)

---

### DEBT-002: Duplicate Pairing Logic
**Component:** Backend (aggregate.py vs pairing.py)  
**Severity:** 🟡 MEDIUM  

**Description:**
There are two pairing implementations:
1. `aggregate.py:_build_pairings()` - Simple distance-based
2. `pairing.py:rank_restaurants_for_event()` - Sophisticated two-phase algorithm

The simple one is currently used, the advanced one is not integrated.

**Impact:**
- Code duplication
- Advanced algorithm not utilized
- Confusion about which to use

**Proposed Fix:**
1. Migrate aggregate.py to use pairing.py
2. Remove duplicate logic
3. Update documentation

**Code Location:**
- `happenstance/aggregate.py:_build_pairings()` (lines 370-445)
- `happenstance/pairing.py` (entire module)

---

### DEBT-003: No Frontend Build Process
**Component:** Frontend  
**Severity:** 🟢 LOW  

**Description:**
Frontend is vanilla JS with no build step. This means:
- No minification
- No tree-shaking
- No TypeScript checking
- No module bundling

**Impact:**
- Slightly larger file sizes
- No type safety
- Manual dependency management

**Proposed Fix (if needed):**
1. Add Vite or esbuild for minimal build process
2. Optionally: Convert to TypeScript
3. Enable minification and bundling

**Note:** Current approach is intentionally simple and may be preferred.

---

### DEBT-004: Hardcoded Constants in Multiple Files
**Component:** Backend  
**Severity:** 🟢 LOW  

**Description:**
Constants like `NEARBY_RESTAURANT_RADIUS_METERS`, `EVENING_HOUR_THRESHOLD`, etc. are defined in multiple places and not centralized.

**Impact:**
- Risk of inconsistency
- Harder to tune parameters

**Proposed Fix:**
Create `happenstance/constants.py`:
```python
# Constants
NEARBY_RESTAURANT_RADIUS_METERS = 800.0
MAX_NEARBY_RESTAURANTS_PER_EVENT = 3
EVENING_HOUR_THRESHOLD = 19
# etc.
```

**Code Location:**
- `happenstance/aggregate.py` (lines 28-35)
- `happenstance/pairing.py` (PairingConfig dataclass)

---

## Enhancement Requests 🔵

### FEATURE-001: Dark/Light Theme Toggle
**Requested By:** User feedback  
**Priority:** 🟡 MEDIUM  

**Description:**
Currently only dark theme is available. Users may prefer light theme or system-based preference.

**Proposed Implementation:**
```javascript
// Detect system preference
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

// Toggle button
const themeToggle = document.createElement('button');
themeToggle.addEventListener('click', () => {
  document.body.classList.toggle('light-theme');
  localStorage.setItem('theme', isDark ? 'light' : 'dark');
});
```

---

### FEATURE-002: Export Itinerary to Calendar
**Requested By:** User feedback  
**Priority:** 🟡 MEDIUM  

**Description:**
Users want to export pairings to their calendar (Google Calendar, Apple Calendar, etc.)

**Proposed Implementation:**
1. Generate .ics file for each pairing
2. "Add to Calendar" button
3. Pre-fill event title, location, time

---

### FEATURE-003: Keyboard Shortcuts
**Requested By:** Power users  
**Priority:** 🟢 LOW  

**Description:**
Add keyboard shortcuts for common actions:
- `1`, `2`, `3` - Switch views
- `/` - Focus filter input
- `Esc` - Clear filter
- `?` - Show help overlay

---

### FEATURE-004: Print-Friendly View
**Requested By:** User feedback  
**Priority:** 🟢 LOW  

**Description:**
Create a print stylesheet for printing itineraries/pairings.

---

## Bug Reporting Process

### How to Report a Bug
1. Check this document to see if it's already listed
2. Open a GitHub Issue with:
   - Clear title
   - Reproduction steps
   - Expected vs actual behavior
   - Screenshots if applicable
3. Label appropriately (bug, enhancement, etc.)

### Bug Triage Process
1. Bug reported → Assigned severity
2. High/Critical → Fix immediately
3. Medium → Fix within sprint
4. Low → Backlog for future sprint

---

## Testing Checklist Before Releases

### Pre-Deployment Checks
- [ ] All unit tests pass (`pytest`)
- [ ] Linter passes (`ruff check .`)
- [ ] Manual smoke test:
  - [ ] App loads successfully
  - [ ] All three views render
  - [ ] Filtering works
  - [ ] External links work
  - [ ] Mobile responsive
- [ ] Data quality check:
  - [ ] Restaurants have valid URLs
  - [ ] Events have dates
  - [ ] Pairings are relevant
- [ ] Performance check:
  - [ ] Page load < 2s
  - [ ] No console errors

---

## Fixed Bugs Archive

### Recently Fixed ✅

**BUG-FIXED-001: Empty pairings in meta.json**  
**Fixed:** December 2024  
**Fix:** Added validation to ensure events have geocoded locations before pairing.

**BUG-FIXED-002: Incorrect cuisine inference for generic restaurants**  
**Fixed:** December 2024  
**Fix:** Improved cuisine mapping in `_infer_cuisine()` with more specific type mappings.

---

**Last Updated:** December 21, 2024  
**Total Active Bugs:** 10 (0 Critical, 3 High, 4 Medium, 3 Low)  
**Total Technical Debt Items:** 4  
**Total Enhancement Requests:** 4
