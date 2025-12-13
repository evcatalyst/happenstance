from typing import Iterable, List


def build_gap_bullets(missing: Iterable[str], limit: int = 3) -> List[str]:
    bullets: List[str] = []
    for item in missing:
        if len(bullets) >= limit:
            break
        bullets.append(f"Add more options for {item}.")
    return bullets


def month_spread_guidance(months: int = 2) -> str:
    return f"Spread recommendations across the next {months} months when available."
