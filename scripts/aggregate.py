#!/usr/bin/env python3
import os, json, sys, time, hashlib, datetime
import uuid
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import re
try:
    import requests  # retained for any future non-SDK calls
    REQUESTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    REQUESTS_AVAILABLE = False

try:
    from openai import OpenAI  # legacy path kept if still needed elsewhere
    OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    OPENAI_AVAILABLE = False

# Structured outputs & live search via xai-sdk
try:
    from pydantic import BaseModel, Field
    from xai_sdk import Client as XAIClient
    from xai_sdk.chat import system as xai_system, user as xai_user
    from xai_sdk.search import SearchParameters, web_source, news_source, x_source, rss_source
    XAI_AVAILABLE = True
except ImportError:
    # Fallback flag – will revert to OpenAI style JSON mode if xai-sdk not installed
    XAI_AVAILABLE = False

CONFIG_PATH = Path('config/config_logic.json')
STATIC_DIR = Path('docs')
DEBUG_DIR = Path('debug')
EVENTS_JSON = STATIC_DIR / 'events.json'
RESTAURANTS_JSON = STATIC_DIR / 'restaurants.json'
CONFIG_OUT_JSON = STATIC_DIR / 'config.json'
GROUND_TRUTH_PATH = Path('config/ground_truth.json')
META_JSON = STATIC_DIR / 'meta.json'

API_URL = 'https://api.x.ai/v1/chat/completions'
# Allow overriding model via GROK_MODEL env; default to more capable 'grok-3'
MODEL = os.environ.get('GROK_MODEL', 'grok-3')

# Optional cost estimation (USD) – override via env; set to 0 if unknown.
COST_PER_1K_PROMPT = float(os.environ.get('COST_PER_1K_PROMPT', '0'))  # manual override (USD)
COST_PER_1K_COMPLETION = float(os.environ.get('COST_PER_1K_COMPLETION', '0'))  # manual override

# Pricing reference (snapshot; update as needed). Values USD per 1K tokens.
# Sources: https://docs.x.ai/docs/models and https://platform.openai.com/docs/pricing
XAI_PRICING = {
    'grok-3': (2.00, 10.00),           # example placeholder (prompt, completion)
    'grok-2-mini': (0.20, 0.60),       # adjust with real values
    'grok-2': (1.00, 5.00),            # adjust with real values
}
OPENAI_PRICING = {
    'gpt-4.1': (5.00, 15.00),          # USD per 1K tokens
    'gpt-4o': (5.00, 15.00),
    'gpt-4o-mini': (0.15, 0.60),
    'gpt-4.1-mini': (1.00, 5.00),
    'gpt-3.5-turbo': (0.50, 1.50),     # legacy example
}

def get_model_pricing(provider: str, model: str) -> tuple:
    """Return (prompt_rate, completion_rate) or (0,0) if unknown.
    Env overrides COST_PER_1K_* take precedence when > 0.
    """
    if COST_PER_1K_PROMPT > 0 or COST_PER_1K_COMPLETION > 0:
        return (COST_PER_1K_PROMPT, COST_PER_1K_COMPLETION)
    provider = provider.lower()
    model_lc = (model or '').lower()
    if provider == 'xai':
        for k, v in XAI_PRICING.items():
            if model_lc.startswith(k):
                return v
    if provider == 'openai':
        for k, v in OPENAI_PRICING.items():
            if model_lc.startswith(k):
                return v
    return (0.0, 0.0)

# Live search controls
LIVE_SEARCH_MODE = os.environ.get('LIVE_SEARCH_MODE', 'off')  # off|auto|on
LIVE_SEARCH_MAX_RESULTS = int(os.environ.get('LIVE_SEARCH_MAX_RESULTS', '15'))
LIVE_SEARCH_ALLOWED_SITES = os.environ.get('LIVE_SEARCH_ALLOWED_SITES', '')  # comma list
LIVE_SEARCH_COUNTRY = os.environ.get('LIVE_SEARCH_COUNTRY', '')  # ISO alpha-2 if set
LIVE_SEARCH_FROM_DATE = os.environ.get('LIVE_SEARCH_FROM_DATE', '')  # YYYY-MM-DD optional
LIVE_SEARCH_TO_DATE = os.environ.get('LIVE_SEARCH_TO_DATE', '')  # YYYY-MM-DD optional
LIVE_SEARCH_INCLUDE_X = os.environ.get('LIVE_SEARCH_INCLUDE_X', '0') == '1'
LIVE_SEARCH_INCLUDE_NEWS = os.environ.get('LIVE_SEARCH_INCLUDE_NEWS', '0') == '1'
LIVE_SEARCH_RSS = os.environ.get('LIVE_SEARCH_RSS', '')  # single RSS url

# Link validation (optional HTTP check). Enable with LINK_HTTP_VALIDATE=1
LINK_HTTP_VALIDATE = os.environ.get('LINK_HTTP_VALIDATE','0') == '1'
LINK_DROP_INVALID = os.environ.get('LINK_DROP_INVALID','0') == '1'  # drop items whose link fails HTTP validation

# Configurable event window days (default extended beyond 30 days). Override with EVENT_WINDOW_DAYS env.
def get_event_window_days() -> int:
    try:
        return max(7, int(os.environ.get('EVENT_WINDOW_DAYS', '120')))
    except ValueError:
        return 120

class AggregationError(Exception):
    pass

def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH) as f:
        return json.load(f)

def load_ground_truth() -> Dict[str, Any]:
    if GROUND_TRUTH_PATH.exists():
        try:
            with open(GROUND_TRUTH_PATH) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def select_profile(config: Dict[str, Any], name: str) -> Dict[str, Any]:
    for p in config.get('profiles', []):
        if p.get('name') == name:
            return p
    raise AggregationError(f'Profile {name} not found')


def serialize_geo_boundary(boundary: Dict[str, Any]) -> str:
    try:
        coords = boundary.get('coordinates')
        return f"geofenced by Polygon with coords {coords}" if coords else ''
    except Exception:
        return ''


def build_prompt(profile: Dict[str, Any], kind: str, extra_focus: str = '') -> str:
    region = profile.get('region', {})
    branding = profile.get('branding', {})
    pred = profile.get('user_predilections', [])
    sources = profile.get('sources', {}).get(kind, [])
    geo = ''
    if region.get('geo_boundary'):
        geo = serialize_geo_boundary(region['geo_boundary'])
    window_days = get_event_window_days()
    timeframe = f'upcoming {window_days} days' if kind == 'events' else 'currently operating and notable (both new and established)'
    instructions = profile.get('instructions', '')
    schema = profile.get('json_schema', {}).get(kind, {})
    # Provide a reduced schema hint
    schema_fields = []
    if schema and schema.get('items', {}).get('properties'):
        schema_fields = list(schema['items']['properties'].keys())
    today = datetime.date.today().isoformat()
    strict = (
        "Return ONLY actual, plausible, non-fabricated {kind} for the specified region. If insufficient verifiable data, return an empty array. "
        "For events: include only those dated from today ({today}) through +{window_days} days (ISO YYYY-MM-DD). "
        "Include both newly opened AND long-established reputable restaurants (avoid large chains unless regionally iconic). "
        "Do NOT fabricate precise addresses—use real, commonly listed addresses / venues. Avoid repetitive filler themes."
    ).format(kind=kind, today=today, window_days=window_days)
    target_counts = (
        "Aim for 30-40 diverse restaurants (mix of new openings, rising spots, and long-established standouts) if available"
        if kind == 'restaurants' else
        f"Aim for up to 25 events within {window_days} days if available"
    )
    focus_line = f"Additional focus: {extra_focus}." if extra_focus else ''
    live_search_mode = os.environ.get('LIVE_SEARCH_MODE','').lower()
    search_hint = ''
    if live_search_mode in {'on','auto'}:
        search_hint = ('Leverage current web search results you have access to; prefer items with corroborated sources. '
                        'Favor entries you can cite; omit unverifiable items rather than guessing.')
    return (
        f"You are an aggregator for {region.get('name')} focusing on {region.get('focus')}. {geo}.\n"
        f"Today is {today}. {strict}\n"
        f"Produce high-quality JSON ONLY (object with a single key '{kind}' or an array) for {kind}.\n"
        f"Inspiration (do not fabricate beyond plausible aggregations): {sources}. Predilections: {pred}. {search_hint}\n"
        f"Timeframe / scope: {timeframe}. {instructions}. {target_counts}. {focus_line}\n"
        f"Return an array of {kind} objects. Fields: {schema_fields}. Ensure strictly valid JSON with no commentary."
    )


class RestaurantItem(BaseModel):
    name: str
    address: str
    cuisine: str
    description: str
    link: str
    is_new: Optional[bool] = None
    badge: Optional[str] = None


class EventItem(BaseModel):
    name: str
    date: str
    venue: str
    category: str
    description: str
    link: str
    is_new: Optional[bool] = None
    badge: Optional[str] = None


class RestaurantsWrapper(BaseModel):
    restaurants: List[RestaurantItem]


class EventsWrapper(BaseModel):
    events: List[EventItem]


def build_search_parameters(kind: str, pass_index: int = 0, profile: Optional[Dict[str, Any]] = None) -> Optional[SearchParameters]:
    if not XAI_AVAILABLE:
        return None
    if LIVE_SEARCH_MODE not in { 'auto', 'on'}:
        if LIVE_SEARCH_MODE != 'off':
            # default treat unknown as off
            pass
        return None
    sources = []
    allowed_sites = [s.strip() for s in LIVE_SEARCH_ALLOWED_SITES.split(',') if s.strip()]
    # If profile has url_groups and allowed_sites empty, dynamically compose per pass
    if profile and not allowed_sites:
        ls_cfg = profile.get('live_search', {})
        url_groups = ls_cfg.get('url_groups', {}) if isinstance(ls_cfg, dict) else {}
        group_order_events = ['general','venues_arts','albany_specific','saratoga','schenectady','troy']
        group_order_restaurants = ['general','albany_specific','saratoga','schenectady','troy']
        order = group_order_events if kind == 'events' else group_order_restaurants
        # rotate selection based on pass index
        if order:
            group_name = order[pass_index % len(order)]
            group_urls = url_groups.get(group_name, [])
            # Fallback to concatenated first two groups if empty
            if not group_urls:
                group_urls = []
                for g in order[:2]:
                    group_urls.extend(url_groups.get(g, []))
            # limit to 15 for token economy
            # API limit: enforce max 5 allowed websites
            allowed_sites = [u.rstrip('/') for u in group_urls][:5]
    if allowed_sites:
        sources.append(web_source(allowed_websites=allowed_sites, country=LIVE_SEARCH_COUNTRY or None))
    else:
        # plain web with optional country
        sources.append(web_source(country=LIVE_SEARCH_COUNTRY or None))
    if LIVE_SEARCH_INCLUDE_NEWS:
        sources.append(news_source(country=LIVE_SEARCH_COUNTRY or None))
    if LIVE_SEARCH_INCLUDE_X and kind == 'events':  # X more relevant for events / buzz
        sources.append(x_source(post_view_count=None))
    if LIVE_SEARCH_RSS:
        sources.append(rss_source(links=[LIVE_SEARCH_RSS]))

    # Date range (use only for events to narrow to upcoming window)
    from_date = None
    to_date = None
    try:
        if LIVE_SEARCH_FROM_DATE:
            y, m, d = map(int, LIVE_SEARCH_FROM_DATE.split('-'))
            from_date = datetime.datetime(y, m, d)
        if LIVE_SEARCH_TO_DATE:
            y, m, d = map(int, LIVE_SEARCH_TO_DATE.split('-'))
            to_date = datetime.datetime(y, m, d)
    except Exception:
        from_date = to_date = None

    return SearchParameters(
        mode=LIVE_SEARCH_MODE if LIVE_SEARCH_MODE in {'auto','on'} else 'auto',
        sources=sources if sources else None,
        max_search_results=LIVE_SEARCH_MAX_RESULTS,
        from_date=from_date,
        to_date=to_date,
        return_citations=True,
    )


def extract_domain(url: str) -> str:
    if not isinstance(url, str) or '://' not in url:
        return ''
    return url.split('://',1)[1].split('/',1)[0].lower()


def _parse_usage_obj(raw_usage: Any, provider: str, model: str) -> Dict[str, Any]:
    """Normalize various usage representations into a dict with numeric token counts.
    Supports:
      - dict with keys already
      - object with attributes prompt_tokens / completion_tokens
      - raw multiline string 'prompt_tokens: 123' lines
    """
    out: Dict[str, Any] = {}
    if isinstance(raw_usage, dict):
        out.update(raw_usage)
    elif hasattr(raw_usage, 'prompt_tokens') or hasattr(raw_usage, 'completion_tokens'):
        for k in ['prompt_tokens','completion_tokens','total_tokens']:
            if hasattr(raw_usage, k):
                try:
                    out[k] = int(getattr(raw_usage, k))
                except Exception:
                    pass
    elif isinstance(raw_usage, str):
        for line in raw_usage.splitlines():
            if ':' in line:
                k, v = line.split(':',1)
                k = k.strip()
                v = v.strip()
                if v.isdigit():
                    out[k] = int(v)
                else:
                    # attempt float then fallback
                    try:
                        out[k] = float(v)
                    except Exception:
                        out[k] = v
    # Derive totals if missing
    if 'total_tokens' not in out:
        pt = out.get('prompt_tokens')
        ct = out.get('completion_tokens')
        if isinstance(pt, (int,float)) and isinstance(ct, (int,float)):
            out['total_tokens'] = pt + ct
    # Estimate cost if rates configured
    try:
        pt = float(out.get('prompt_tokens', 0) or 0)
        ct = float(out.get('completion_tokens', 0) or 0)
        p_rate, c_rate = get_model_pricing(provider, model)
        if p_rate or c_rate:
            est_cost = (pt/1000.0)*p_rate + (ct/1000.0)*c_rate
            out['estimated_cost_usd'] = round(est_cost, 6)
            out['pricing_model_prompt_per_1k'] = p_rate
            out['pricing_model_completion_per_1k'] = c_rate
    except Exception:
        pass
    return out


def call_grok(prompt: str, kind: str, system_instructions: str = 'You are a helpful data curation assistant.', temperature: float = 0.0, pass_index: int = 0, profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    api_key = os.environ.get('GROK_API_KEY') or os.environ.get('XAI_API_KEY')
    if not api_key:
        raise AggregationError('Missing GROK_API_KEY / XAI_API_KEY env var')

    # Prefer xai-sdk structured outputs if available
    if XAI_AVAILABLE:
        client = XAIClient(api_key=api_key)
        search_params = build_search_parameters(kind, pass_index=pass_index, profile=profile)
        chat = client.chat.create(model=MODEL, search_parameters=search_params)
        chat.append(xai_system(system_instructions))
        chat.append(xai_user(prompt))
        # Choose wrapper based on kind
        wrapper_cls = RestaurantsWrapper if kind == 'restaurants' else EventsWrapper
        try:
            response, parsed = chat.parse(wrapper_cls)  # returns tuple (response, pydantic instance)
        except Exception as e:
            raise AggregationError(f'Structured parse failed: {e}') from e
        # Extract citations if any
        citations = getattr(response, 'citations', None)
        usage = getattr(response, 'usage', None)
        if citations or usage:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if citations:
                cit_serializable = list(citations) if not isinstance(citations, list) else citations
                (DEBUG_DIR / f'citations_{kind}.json').write_text(json.dumps(cit_serializable, indent=2))
            parsed_usage = {}
            if usage:
                try:
                    parsed_usage = _parse_usage_obj(usage, 'xai', MODEL)
                except Exception:
                    parsed_usage = {'raw': str(usage)}
                (DEBUG_DIR / f'usage_{kind}.json').write_text(json.dumps(parsed_usage if parsed_usage else {'raw': str(usage)}, indent=2))
        except Exception as ser_err:
            (DEBUG_DIR / f'serialize_error_{kind}.txt').write_text(str(ser_err))
        # Convert back to dict aligned with previous code paths
        data = parsed.model_dump()
        # attach citations & domains for feedback / metrics
        data['_citations'] = citations if citations else []
        if citations:
            data['_citation_domains'] = sorted({extract_domain(c) for c in citations if isinstance(c, str)})
        if usage:
            data['_usage'] = parsed_usage
        return data

    # Legacy OpenAI style fallback (only if library present)
    if not OPENAI_AVAILABLE:
        raise AggregationError('xai-sdk unavailable and openai fallback not installed')
    client = OpenAI(api_key=api_key, base_url='https://api.x.ai/v1')
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            stream=False,
            response_format={"type": "json_object"}
        )
    except Exception as e:
        raise AggregationError(f'SDK request failed: {e}') from e
    try:
        content = resp.choices[0].message.content  # type: ignore[attr-defined]
    except Exception as e:
        raise AggregationError(f'Unexpected SDK response structure: {resp}') from e
    try:
        return json.loads(content)
    except Exception as e:
        raise AggregationError(f'Content not JSON: {content[:200]}') from e


def load_existing(path: Path) -> List[Dict[str, Any]]:
    """Load existing dataset list, stripping trailing meta sentinel if present."""
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list) and data and isinstance(data[-1], dict) and '_meta' in data[-1]:
                return data[:-1]
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def mark_new(items: List[Dict[str, Any]], existing: List[Dict[str, Any]], kind: str, branding: Dict[str, Any]):
    existing_keys = set()
    if kind == 'restaurants':
        for r in existing:
            existing_keys.add((r.get('name','').lower(), r.get('address','').lower()))
    else:  # events
        for e in existing:
            existing_keys.add((e.get('name','').lower(), e.get('venue','').lower(), e.get('date','').lower()))
    for item in items:
        if kind == 'restaurants':
            key = (item.get('name','').lower(), item.get('address','').lower())
        else:
            key = (item.get('name','').lower(), item.get('venue','').lower(), item.get('date','').lower())
        is_new = key not in existing_keys
        item['is_new'] = is_new
        badge_key = 'new_restaurant' if kind == 'restaurants' else 'new_event'
        if is_new:
            item['badge'] = branding.get('badges', {}).get(badge_key, 'New')
        else:
            item.setdefault('badge', '')


def validate_against_schema(items: List[Dict[str, Any]], schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Lightweight manual validation to avoid jsonschema dependency
    required = schema.get('items', {}).get('required', [])
    props = schema.get('items', {}).get('properties', {})
    validated = []
    for obj in items:
        if not isinstance(obj, dict):
            continue
        if any(r not in obj for r in required):
            continue
        # basic type checks
        ok = True
        for k, spec in props.items():
            if k in obj and spec.get('type') == 'string' and not isinstance(obj[k], str):
                ok = False
                break
            if k in obj and spec.get('type') == 'boolean' and not isinstance(obj[k], bool):
                ok = False
                break
        if ok:
            validated.append(obj)
    return validated


def plausibility_filter(restaurants: List[Dict[str, Any]], events: List[Dict[str, Any]], profile_name: str, ground: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Filter items according to VALIDATION_MODE / STRICT_VALIDATION.
    Modes:
      off   -> return as-is
      soft  -> apply lightweight heuristics; allow novel domains if they look syntactically valid
      strict or STRICT_VALIDATION=1 -> require ground-truth membership OR allowed domain (restaurants) / venue match (events)
    """
    mode = os.environ.get('VALIDATION_MODE', 'soft').lower()
    if os.environ.get('STRICT_VALIDATION', '0') == '1':
        mode = 'strict'
    if mode not in {'off','soft','strict'}:
        mode = 'soft'
    if mode == 'off':
        return restaurants, events
    prof_ground = ground.get(profile_name, {})
    known_rest = set(r.lower() for r in prof_ground.get('known_restaurants', []))
    known_venues = set(v.lower() for v in prof_ground.get('known_venues', []))
    allowed_domains = set(prof_ground.get('allowed_link_domains', []))

    def domain_ok(link: str) -> bool:
        if not link or '://' not in link:
            return False
        host = link.split('://',1)[1].split('/',1)[0].lower()
        # allow subdomains of allowed domains
        return any(host == d or host.endswith('.'+d) for d in allowed_domains) if allowed_domains else True

    filtered_rest = []
    for r in restaurants:
        name = (r.get('name') or '').strip()
        desc = (r.get('description') or '')
        # Heuristics: reject if name too generic or description overly templated / contains improbable fusion phrases repeated
        if len(name) < 3:
            continue
        if desc.count('fusion') > 2 and 'taco' in desc.lower() and 'authentic' in desc.lower():
            # likely templated
            continue
        if mode == 'strict':
            if known_rest and name.lower() not in known_rest and not domain_ok(r.get('link','')):
                continue
        elif mode == 'soft':
            # allow if domain syntactically plausible even if not in allow-list
            link = r.get('link','')
            if not domain_ok(link):
                # simple syntactic pass (contains dot and no spaces)
                host_ok = ('://' in link and '.' in link.split('://',1)[1] and ' ' not in link)
                if not host_ok:
                    continue
        filtered_rest.append(r)

    filtered_events = []
    for e in events:
        venue = (e.get('venue') or '').lower()
        if mode == 'strict':
            if known_venues and not any(v in venue for v in known_venues):
                continue
        name = (e.get('name') or '').lower()
        # Basic repetition / hype filtering
        if name.count('taco') > 1 and name.count('festival') > 1:
            continue
        filtered_events.append(e)

    return filtered_rest, filtered_events


def http_validate_links(items: List[Dict[str, Any]], kind: str) -> None:
    """Perform shallow HTTP validation to mark link_ok.
    Adds fields: link_ok (bool), status (int|None). Respects LINK_HTTP_VALIDATE.
    If LINK_DROP_INVALID=1 then invalid links removed by caller.
    """
    if not LINK_HTTP_VALIDATE:
        return
    if not REQUESTS_AVAILABLE:
        return
    session = requests.Session()
    out = []
    for it in items:
        url = it.get('link')
        ok = False
        status = None
        if isinstance(url, str) and url.startswith('http'):
            try:
                resp = session.head(url, allow_redirects=True, timeout=5)
                status = resp.status_code
                if status in (405, 403) or status >= 400:
                    # some sites disallow HEAD; fallback GET
                    resp = session.get(url, allow_redirects=True, timeout=6)
                    status = resp.status_code
                ok = 200 <= status < 400
            except Exception:
                ok = False
        it['link_ok'] = ok
        it['status'] = status
        out.append({'name': it.get('name'), 'link': url, 'ok': ok, 'status': status})
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        (DEBUG_DIR / f'link_validation_{kind}.json').write_text(json.dumps(out, indent=2))
    except Exception:
        pass


def write_if_changed(path: Path, data: Any) -> bool:
    serialized = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
    old = path.read_text() if path.exists() else ''
    if hashlib.sha256(old.encode()).hexdigest() != hashlib.sha256(serialized.encode()).hexdigest():
        path.write_text(serialized)
        return True
    return False

def canonical_items_hash(items: List[Dict[str, Any]]) -> str:
    """Stable hash of items content (excluding meta sentinel)."""
    try:
        # remove volatile fields if any later
        dumped = json.dumps(items, sort_keys=True, ensure_ascii=False, separators=(',',':'))
        return hashlib.sha256(dumped.encode('utf-8')).hexdigest()
    except Exception:
        return ''


def save_debug(name: str, payload: Any):
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    with open(DEBUG_DIR / name, 'w') as f:
        json.dump(payload, f, indent=2)


def save_text(name: str, text: str):
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    with open(DEBUG_DIR / name, 'w') as f:
        f.write(text)


def _valid_event_window(date_str: str) -> bool:
    try:
        d = datetime.date.fromisoformat(date_str)
    except Exception:
        return False
    today = datetime.date.today()
    window = datetime.timedelta(days=get_event_window_days())
    return today <= d <= today + window


def main():
    try:
        run_start_ts = time.time()
        run_id = uuid.uuid4().hex[:12]
        # Load configuration and profile
        config = load_config()
        profile_name = os.environ.get('PROFILE', 'capital_region')
        profile = select_profile(config, profile_name)
        branding = profile.get('branding', {})
        ground_truth = load_ground_truth()

        # Apply profile live_search defaults if env not explicitly set
        ls = profile.get('live_search', {})
        def set_if_empty(env_key: str, value: str):
            if not os.environ.get(env_key) and value is not None:
                os.environ[env_key] = str(value)
        if ls:
            set_if_empty('LIVE_SEARCH_MODE', ls.get('mode',''))
            if ls.get('allowed_sites'):
                set_if_empty('LIVE_SEARCH_ALLOWED_SITES', ','.join(ls.get('allowed_sites')))
            if ls.get('include_news'):
                set_if_empty('LIVE_SEARCH_INCLUDE_NEWS', '1')
            if ls.get('include_x'):
                set_if_empty('LIVE_SEARCH_INCLUDE_X', '1')
            if ls.get('country'):
                set_if_empty('LIVE_SEARCH_COUNTRY', ls.get('country'))
            if ls.get('max_results'):
                set_if_empty('LIVE_SEARCH_MAX_RESULTS', str(ls.get('max_results')))

        # Targets & multi-pass settings (kept inside try block)
        target_rest = int(os.environ.get('TARGET_RESTAURANTS', '30'))
        target_events = int(os.environ.get('TARGET_EVENTS', '40'))
        # Allow separate pass counts per kind; fall back to MAX_PROMPT_PASSES then default 5
        default_passes = int(os.environ.get('MAX_PROMPT_PASSES', '5'))
        rest_passes = int(os.environ.get('REST_PASSES', str(default_passes)))
        event_passes = int(os.environ.get('EVENT_PASSES', str(default_passes)))
        rest_seeds = [s.strip() for s in os.environ.get('PASS_SEEDS_RESTAURANTS','tacos,breweries,coffee,brunch,farm-to-table,vegan,pizza,seafood,steakhouses,global fusion').split(',') if s.strip()] or ['varied']
        event_seeds = [s.strip() for s in os.environ.get('PASS_SEEDS_EVENTS','live music,food festivals,art exhibitions,farmer markets,theater,community events,seasonal festivals,craft beer events,cultural celebrations').split(',') if s.strip()] or ['varied']

        schema = profile.get('json_schema', {})

        # Overall pass cap (across both kinds and providers)
        max_total_passes = int(os.environ.get('MAX_RUN_PASSES', '5'))
        total_passes = 0  # counts every invocation of run_pass that actually executes

        def call_openai(prompt: str, kind: str):
            if not OPENAI_AVAILABLE:
                return {kind: []}
            api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('OPENAI_KEY') or os.environ.get('OPENAI_TOKEN')
            if not api_key:
                return {kind: []}
            model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
            try:
                client = OpenAI(api_key=api_key)
            except Exception:
                return {kind: []}
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a precise data extraction assistant. Output valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=float(os.environ.get('OPENAI_TEMPERATURE','0.2')),
                    response_format={"type": "json_object"}
                )
            except Exception as e:
                save_text(f'openai_error_{kind}.txt', str(e))
                return {kind: []}
            usage_obj = getattr(resp, 'usage', None)
            parsed_usage = _parse_usage_obj(usage_obj, 'openai', model) if usage_obj else {}
            try:
                content = resp.choices[0].message.content  # type: ignore[attr-defined]
            except Exception:
                return {kind: []}
            try:
                data = json.loads(content)
            except Exception:
                save_text(f'openai_parse_failed_{kind}.txt', content[:5000])
                return {kind: []}
            if isinstance(data, list):
                data = {kind: data}
            if isinstance(data, dict):
                data['_usage'] = parsed_usage
                data['_citation_domains'] = []
            return data

        first_api_ts: Optional[float] = None
        last_api_ts: Optional[float] = None

        def run_pass(kind: str, extra_focus: str, feedback: str, provider: str, pass_index: int):
            nonlocal total_passes
            nonlocal first_api_ts, last_api_ts
            if total_passes >= max_total_passes:
                return []
            pass_start = time.time()
            prompt = build_prompt(profile, kind, extra_focus=extra_focus)
            if feedback:
                prompt += f"\nFeedback from prior passes (use this ONLY to enhance completeness, do NOT repeat earlier items): {feedback}\n"
            if provider != 'xai':
                prompt += ("\nAugmentation pass: Prefer high-confidence real items (new OR established) even if some appeared earlier; "
                           "you may repeat a small subset (<=25%) if wording can enhance description richness. Avoid fabrications.")
            save_text(f'prompt_{provider}_{kind}_{extra_focus or "base"}.txt', prompt)
            raw_call_start = time.time()
            raw = call_grok(prompt, kind, pass_index=pass_index, profile=profile) if provider == 'xai' else call_openai(prompt, kind)
            raw_call_end = time.time()
            if first_api_ts is None:
                first_api_ts = raw_call_start
            last_api_ts = raw_call_end
            items = raw.get(kind) if isinstance(raw, dict) else raw
            if isinstance(items, dict):
                items = items.get(kind, [])
            if not isinstance(items, list):
                items = []
            save_debug(f'last_run_raw_{provider}_{kind}_{extra_focus or "base"}.json', items)
            metrics_path = DEBUG_DIR / 'pass_metrics.json'
            snapshot = {
                'ts': time.time(),
                'pass': pass_index,
                'kind': kind,
                'focus': extra_focus,
                'raw_count': len(items),
                'citation_domains': raw.get('_citation_domains', []) if isinstance(raw, dict) else [],
                'provider': provider,
                'model': MODEL if provider == 'xai' else os.environ.get('OPENAI_MODEL',''),
                'overall_pass': total_passes + 1,
                'pass_duration_ms': int((raw_call_end - pass_start)*1000),
                'search_sources_count': len(raw.get('_citation_domains', [])) if isinstance(raw, dict) else 0,
                'search_mode': os.environ.get('LIVE_SEARCH_MODE','off')
            }
            if isinstance(raw, dict) and raw.get('_usage'):
                usage_meta = raw['_usage']
                for k in ['prompt_tokens','completion_tokens','total_tokens','estimated_cost_usd']:
                    if k in usage_meta:
                        snapshot[k] = usage_meta[k]
            try:
                DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                existing = []
                if metrics_path.exists():
                    existing = json.loads(metrics_path.read_text())
                existing.append(snapshot)
                metrics_path.write_text(json.dumps(existing, indent=2))
            except Exception:
                pass
            total_passes += 1
            return items

        # Collect restaurants multi-pass
        collected_rest: List[Dict[str, Any]] = []
        seen_rest = set()
        feedback_notes_rest = ''
        pass_index = 0
        while pass_index < rest_passes and len(collected_rest) < target_rest and total_passes < max_total_passes:
            focus = '' if pass_index == 0 else rest_seeds[(pass_index-1) % len(rest_seeds)]
            new_items = run_pass('restaurants', focus, feedback_notes_rest, provider='xai', pass_index=pass_index)
            if new_items:
                cuisines = {(it.get('cuisine') or '').lower() for it in new_items if it.get('cuisine')}
                wanted = {'tacos','thai','ethiopian','vegan','seafood'} - cuisines
                if wanted:
                    feedback_notes_rest = f"Prior results lacked cuisines: {', '.join(sorted(wanted))}. Prioritize these if real."
            new_count_this_pass = 0
            for it in new_items:
                key = (it.get('name','').lower(), it.get('address','').lower())
                if key in seen_rest:
                    continue
                seen_rest.add(key)
                collected_rest.append(it)
                new_count_this_pass += 1
            # Augment last snapshot with novelty metrics
            try:
                metrics_path = DEBUG_DIR / 'pass_metrics.json'
                metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else []
                if metrics and metrics[-1].get('kind') == 'restaurants':
                    cumulative_new = len({(r.get('name','').lower(), r.get('address','').lower()) for r in collected_rest})
                    raw_count = metrics[-1].get('raw_count', 1) or 1
                    metrics[-1]['new_items_this_pass'] = new_count_this_pass
                    metrics[-1]['cumulative_new_items'] = cumulative_new
                    metrics[-1]['novelty_rate'] = round(new_count_this_pass / raw_count, 4)
                    metrics[-1]['domain_diversity'] = len({(r.get('cuisine') or '').lower() for r in collected_rest if r.get('cuisine')})
                    metrics_path.write_text(json.dumps(metrics, indent=2))
            except Exception:
                pass
            pass_index += 1

        # Collect events multi-pass
        collected_events: List[Dict[str, Any]] = []
        seen_events = set()
        feedback_notes_events = ''
        pass_index = 0
        while pass_index < event_passes and len(collected_events) < target_events and total_passes < max_total_passes:
            focus = '' if pass_index == 0 else event_seeds[(pass_index-1) % len(event_seeds)]
            new_items = run_pass('events', focus, feedback_notes_events, provider='xai', pass_index=pass_index)
            if isinstance(new_items, list):
                categories = {(it.get('category') or '').lower() for it in new_items if it.get('category')}
                desired = {'live music','festival','food','theater','comedy'}
                missing = desired - categories
                if missing:
                    feedback_notes_events = f"Missing categories so far: {', '.join(sorted(missing))}. Prefer verified upcoming items in these categories."
            new_count_this_pass = 0
            for it in new_items:
                key = (it.get('name','').lower(), it.get('venue','').lower(), it.get('date','').lower())
                if key in seen_events:
                    continue
                seen_events.add(key)
                collected_events.append(it)
                new_count_this_pass += 1
            try:
                metrics_path = DEBUG_DIR / 'pass_metrics.json'
                metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else []
                if metrics and metrics[-1].get('kind') == 'events':
                    cumulative_new = len({(e.get('name','').lower(), e.get('venue','').lower(), e.get('date','').lower()) for e in collected_events})
                    raw_count = metrics[-1].get('raw_count', 1) or 1
                    metrics[-1]['new_items_this_pass'] = new_count_this_pass
                    metrics[-1]['cumulative_new_items'] = cumulative_new
                    metrics[-1]['novelty_rate'] = round(new_count_this_pass / raw_count, 4)
                    metrics[-1]['domain_diversity'] = len({(e.get('category') or '').lower() for e in collected_events if e.get('category')})
                    metrics_path.write_text(json.dumps(metrics, indent=2))
            except Exception:
                pass
            pass_index += 1

        # Optional OpenAI augmentation
        if (len(collected_rest) < target_rest or len(collected_events) < target_events) and os.environ.get('AUGMENT_WITH_OPENAI','0') == '1' and total_passes < max_total_passes:
            aug_passes = int(os.environ.get('OPENAI_AUG_PASSES','2'))
            aug_focus_cycler_rest = iter(rest_seeds)
            aug_focus_cycler_events = iter(event_seeds)
            for aug_i in range(aug_passes):
                if total_passes >= max_total_passes:
                    break
                if len(collected_rest) < target_rest:
                    try:
                        focus = next(aug_focus_cycler_rest)
                    except StopIteration:
                        aug_focus_cycler_rest = iter(rest_seeds)
                        focus = next(aug_focus_cycler_rest)
                    new_items = run_pass('restaurants', focus, feedback_notes_rest, provider='openai', pass_index=aug_i)
                    for it in new_items:
                        key = (it.get('name','').lower(), it.get('address','').lower())
                        if key in seen_rest:
                            continue
                        seen_rest.add(key)
                        collected_rest.append(it)
                    # annotate last snapshot for restaurants openai augmentation
                    try:
                        metrics_path = DEBUG_DIR / 'pass_metrics.json'
                        metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else []
                        if metrics and metrics[-1].get('kind') == 'restaurants':
                            metrics[-1]['augmentation_provider'] = 'openai'
                            metrics_path.write_text(json.dumps(metrics, indent=2))
                    except Exception:
                        pass
                if total_passes >= max_total_passes:
                    break
                if len(collected_events) < target_events:
                    try:
                        focus = next(aug_focus_cycler_events)
                    except StopIteration:
                        aug_focus_cycler_events = iter(event_seeds)
                        focus = next(aug_focus_cycler_events)
                    new_items = run_pass('events', focus, feedback_notes_events, provider='openai', pass_index=aug_i)
                    for it in new_items:
                        key = (it.get('name','').lower(), it.get('venue','').lower(), it.get('date','').lower())
                        if key in seen_events:
                            continue
                        seen_events.add(key)
                        collected_events.append(it)
                    try:
                        metrics_path = DEBUG_DIR / 'pass_metrics.json'
                        metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else []
                        if metrics and metrics[-1].get('kind') == 'events':
                            metrics[-1]['augmentation_provider'] = 'openai'
                            metrics_path.write_text(json.dumps(metrics, indent=2))
                    except Exception:
                        pass
                if total_passes >= max_total_passes:
                    break

        # Trim to preliminary targets
        collected_rest = collected_rest[:target_rest]
        collected_events = collected_events[:target_events]

        rest_valid = validate_against_schema(collected_rest, schema.get('restaurants', {}))
        event_valid = validate_against_schema(collected_events, schema.get('events', {}))

        # Event date window filtering
        filtered_events = [ev for ev in event_valid if _valid_event_window(ev.get('date',''))]
        if filtered_events or not event_valid:
            event_valid = filtered_events

        # Existing data for newness flags
        existing_rest = load_existing(RESTAURANTS_JSON)
        existing_events = load_existing(EVENTS_JSON)
        mark_new(rest_valid, existing_rest, 'restaurants', branding)
        mark_new(event_valid, existing_events, 'events', branding)

        # Plausibility filtering (mode-based)
        rest_valid, event_valid = plausibility_filter(rest_valid, event_valid, profile_name, ground_truth)

        # Deduplication utilities
        def norm_name(s: str) -> str:
            return re.sub(r'[^a-z0-9]+','', s.lower()) if s else ''

        def dedupe_rest(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            best: Dict[Tuple[str,str], Dict[str, Any]] = {}
            for it in items:
                key = (norm_name(it.get('name','')), norm_name(it.get('address','')))
                cur = best.get(key)
                if not cur:
                    best[key] = it
                    continue
                if len((it.get('description') or '')) > len((cur.get('description') or '')):
                    best[key] = it
            return list(best.values())

        def dedupe_events(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            best: Dict[str, Dict[str, Any]] = {}
            for it in items:
                key = norm_name(it.get('name',''))
                cur = best.get(key)
                if not cur:
                    best[key] = it
                    continue
                try:
                    d_new = datetime.date.fromisoformat(it.get('date','1970-01-01'))
                    d_old = datetime.date.fromisoformat(cur.get('date','1970-01-01'))
                    if d_new < d_old:
                        best[key] = it
                except Exception:
                    pass
            return list(best.values())

        rest_valid = dedupe_rest(rest_valid)[:target_rest]
        event_valid = dedupe_events(event_valid)[:target_events]

        # HTTP link validation (optional)
        http_validate_links(rest_valid, 'restaurants')
        http_validate_links(event_valid, 'events')
        if LINK_HTTP_VALIDATE and LINK_DROP_INVALID:
            rest_valid = [r for r in rest_valid if r.get('link_ok')]
            event_valid = [e for e in event_valid if e.get('link_ok')]

        save_debug('last_run_validated_restaurants.json', rest_valid)
        save_debug('last_run_validated_events.json', event_valid)

        # Prepare meta sentinel entries with timestamps & hashes
        run_end_ts = time.time()
        gen_time_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        def build_meta(items: List[Dict[str, Any]], existing_items: List[Dict[str, Any]], kind: str) -> Dict[str, Any]:
            new_hash = canonical_items_hash(items)
            prev_hash = canonical_items_hash(existing_items)
            changed = new_hash != prev_hash
            return {
                '_meta': {
                    'run_id': run_id,
                    'kind': kind,
                    'generated_at': gen_time_iso,
                    'run_start': datetime.datetime.utcfromtimestamp(run_start_ts).isoformat() + 'Z',
                    'run_end': datetime.datetime.utcfromtimestamp(run_end_ts).isoformat() + 'Z',
                    'first_api_response': datetime.datetime.utcfromtimestamp(first_api_ts).isoformat() + 'Z' if first_api_ts else None,
                    'last_api_response': datetime.datetime.utcfromtimestamp(last_api_ts).isoformat() + 'Z' if last_api_ts else None,
                    'item_count': len(items),
                    'items_hash_sha256': new_hash,
                    'previous_items_hash_sha256': prev_hash,
                    'items_changed': changed
                }
            }

        meta_rest = build_meta(rest_valid, existing_rest, 'restaurants')
        meta_events = build_meta(event_valid, existing_events, 'events')

        rest_with_meta = list(rest_valid) + [meta_rest]
        events_with_meta = list(event_valid) + [meta_events]

        # Always write (timestamps differ each run) but report whether items changed
        write_if_changed(RESTAURANTS_JSON, rest_with_meta)
        write_if_changed(EVENTS_JSON, events_with_meta)
        changed_rest = meta_rest['_meta']['items_changed']
        changed_events = meta_events['_meta']['items_changed']

        front_cfg = {
            'branding': branding,
            'pairing_rules': profile.get('pairing_rules', []),
            'version': 'v2.1-wave0',
            'last_generated_at': gen_time_iso,
            'run_id': run_id
        }
        write_if_changed(CONFIG_OUT_JSON, front_cfg)

        # Consolidated meta file (summary)
        try:
            meta_summary = {
                'version': 'v2.1-wave0',
                'profile': profile_name,
                'run_id': run_id,
                'generated_at': gen_time_iso,
                'restaurants': meta_rest['_meta'],
                'events': meta_events['_meta']
            }
            META_JSON.write_text(json.dumps(meta_summary, indent=2))
        except Exception:
            pass

        # Usage metrics consolidation (cost fields deprecated)
        try:
            metrics_path = DEBUG_DIR / 'pass_metrics.json'
            if metrics_path.exists():
                metrics = json.loads(metrics_path.read_text())
            else:
                metrics = []
            total_prompt = sum(m.get('prompt_tokens', 0) for m in metrics)
            total_completion = sum(m.get('completion_tokens', 0) for m in metrics)
            providers = sorted({m.get('provider','xai') for m in metrics})
            # Aggregate per provider/model
            aggregates: Dict[str, Any] = {}
            for m in metrics:
                prov = m.get('provider','unknown')
                mod = m.get('model','') or 'unknown'
                aggregates.setdefault(prov, {'models':{}, 'prompt_tokens':0,'completion_tokens':0,'passes':0})
                ag = aggregates[prov]
                ag['prompt_tokens'] += m.get('prompt_tokens',0) or 0
                ag['completion_tokens'] += m.get('completion_tokens',0) or 0
                ag['passes'] += 1
                ag['models'].setdefault(mod, {'prompt_tokens':0,'completion_tokens':0,'passes':0})
                agm = ag['models'][mod]
                agm['prompt_tokens'] += m.get('prompt_tokens',0) or 0
                agm['completion_tokens'] += m.get('completion_tokens',0) or 0
                agm['passes'] += 1
            first_pass_ts = metrics[0]['ts'] if metrics else None
            last_pass_ts = metrics[-1]['ts'] if metrics else None
            xai_passes = sum(1 for m in metrics if m.get('provider')=='xai')
            openai_passes = sum(1 for m in metrics if m.get('provider')=='openai')
            novelty_final_rest = round(sum(1 for r in rest_valid if r.get('is_new')) / max(len(rest_valid),1),4)
            novelty_final_events = round(sum(1 for e in event_valid if e.get('is_new')) / max(len(event_valid),1),4)
            live_search_domains = sorted({d for m in metrics for d in (m.get('citation_domains') or [])})
            usage_summary = {
                'run_id': run_id,
                'ts': time.time(),
                'providers': providers,
                'aggregates': aggregates,
                'prompt_tokens_total': total_prompt,
                'completion_tokens_total': total_completion,
                'passes_total': len(metrics),
                'targets': {'restaurants': target_rest, 'events': target_events},
                'final_counts': {'restaurants': len(rest_valid), 'events': len(event_valid)},
                'novelty_final': {'restaurants': novelty_final_rest, 'events': novelty_final_events},
                'augmentation': {'xai_passes': xai_passes, 'openai_passes': openai_passes},
                'live_search': {'distinct_citation_domains': len(live_search_domains), 'citation_domains': live_search_domains},
                'first_pass_ts': first_pass_ts,
                'last_pass_ts': last_pass_ts,
                'deprecated_cost_summary': True
            }
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / 'usage_summary.json').write_text(json.dumps(usage_summary, indent=2))
            # keep deprecated file for backward compatibility
            (DEBUG_DIR / 'cost_summary.json').write_text(json.dumps({'deprecated': True, 'see': 'usage_summary.json'}, indent=2))
            history_path = DEBUG_DIR / 'usage_history.json'
            history = []
            if history_path.exists():
                try:
                    history = json.loads(history_path.read_text())
                except Exception:
                    history = []
            history.append({k: v for k,v in usage_summary.items() if k not in {'live_search'} or k})
            history_path.write_text(json.dumps(history, indent=2))
            print(f"Run {run_id}: providers={providers} tokens(prompt={total_prompt}, completion={total_completion}) final(rest={len(rest_valid)}, events={len(event_valid)}) openai_passes={openai_passes}")
        except Exception as cost_err:
            print(f'Cost summary error: {cost_err}', file=sys.stderr)
        # Final high-level change summary
        print(f'Restaurants items_changed={changed_rest}, Events items_changed={changed_events}')
    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(0)

if __name__ == '__main__':
    main()
