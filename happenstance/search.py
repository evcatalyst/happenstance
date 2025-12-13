from typing import Dict, Mapping


def build_live_search_params(config: Mapping) -> Dict:
    live_cfg = dict(config.get("live_search", {}))
    params = {
        "mode": live_cfg.get("mode", "local"),
        "radius_km": live_cfg.get("radius_km", 5),
        "limit": live_cfg.get("limit", 10),
    }
    if "query" in live_cfg:
        params["query"] = live_cfg["query"]
    return params
