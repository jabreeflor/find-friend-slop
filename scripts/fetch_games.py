"""Fetches trending games from Steam and enriches them with price/sale data."""

from __future__ import annotations

import time
import urllib.parse
import urllib.request
import json
from dataclasses import dataclass, asdict
from typing import Iterable

FEATURED_URL = "https://store.steampowered.com/api/featuredcategories?cc=us&l=en"
APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"

# Steam's trending buckets — ordered by priority (top_sellers first).
BUCKETS = ("specials", "top_sellers", "new_releases", "coming_soon")


@dataclass
class Game:
    appid: int
    name: str
    header_image: str
    store_url: str
    price_cents: int          # final price in cents (after discount)
    original_cents: int       # pre-discount price in cents
    discount_pct: int         # 0–100
    is_free: bool
    on_sale: bool
    short_description: str
    trending_rank: int        # lower = more trending (position across buckets)
    source_bucket: str        # which bucket it came from

    @property
    def price_dollars(self) -> float:
        return self.price_cents / 100.0


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "find-friend-slop/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_featured() -> list[tuple[int, str, int]]:
    """Returns [(appid, bucket, rank_within_bucket), ...] across trending buckets."""
    data = _http_get_json(FEATURED_URL)
    seen: dict[int, tuple[str, int]] = {}
    for bucket in BUCKETS:
        items = (data.get(bucket) or {}).get("items") or []
        for rank, item in enumerate(items):
            appid = item.get("id")
            if not appid or appid in seen:
                continue
            seen[appid] = (bucket, rank)
    # Emit in bucket priority order, preserving rank-within-bucket.
    out = []
    for bucket in BUCKETS:
        for appid, (b, rank) in seen.items():
            if b == bucket:
                out.append((appid, bucket, rank))
    return out


def fetch_details(appid: int) -> dict | None:
    params = urllib.parse.urlencode({
        "appids": appid,
        "cc": "us",
        "l": "en",
    })
    try:
        data = _http_get_json(f"{APPDETAILS_URL}?{params}")
    except Exception:
        return None
    entry = data.get(str(appid)) or {}
    if not entry.get("success"):
        return None
    return entry.get("data") or {}


def build_games(
    appid_bucket_rank: Iterable[tuple[int, str, int]],
    sleep_between: float = 0.25,
) -> list[Game]:
    games: list[Game] = []
    for i, (appid, bucket, bucket_rank) in enumerate(appid_bucket_rank):
        details = fetch_details(appid)
        if not details:
            continue
        price = details.get("price_overview")
        is_free = details.get("is_free", False) or price is None
        if is_free:
            price_cents = 0
            original_cents = 0
            discount_pct = 0
        else:
            price_cents = price.get("final", 0)
            original_cents = price.get("initial", price_cents)
            discount_pct = price.get("discount_percent", 0)

        games.append(Game(
            appid=appid,
            name=details.get("name", f"App {appid}"),
            header_image=details.get("header_image", ""),
            store_url=f"https://store.steampowered.com/app/{appid}/",
            price_cents=price_cents,
            original_cents=original_cents,
            discount_pct=discount_pct,
            is_free=is_free,
            on_sale=discount_pct > 0,
            short_description=(details.get("short_description") or "").strip(),
            trending_rank=i,  # global position across buckets
            source_bucket=bucket,
        ))
        # Polite pacing to avoid Steam's rate limit.
        time.sleep(sleep_between)
    return games


def games_to_dicts(games: list[Game]) -> list[dict]:
    return [asdict(g) for g in games]


# ---------------------------------------------------------------------------
# Filtering + ranking
# ---------------------------------------------------------------------------

def filter_by_price(games: list[Game], min_dollars: float, max_dollars: float) -> list[Game]:
    min_c = int(round(min_dollars * 100))
    max_c = int(round(max_dollars * 100))
    return [g for g in games if min_c <= g.price_cents <= max_c]


def score_game(
    game: Game,
    *,
    prioritize_sales: bool,
    price_min: float,
    price_max: float,
) -> float:
    """Weighted sum, higher = better. Sale 50% / trending 30% / price fit 20%."""
    import math

    # Trending: exponential decay so rank 0 ≈ 1.0, rank 25 ≈ 0.54, rank 60 ≈ 0.22.
    trend = math.exp(-game.trending_rank / 40.0)

    # Sale: normalized discount. Free-to-play stays neutral (no boost, no penalty).
    sale = (game.discount_pct / 100.0) if (prioritize_sales and game.on_sale) else 0.0

    # Price fit: 1.0 at midpoint, linear falloff to 0 at range edges.
    span = max(price_max - price_min, 0.01)
    midpoint = (price_min + price_max) / 2.0
    fit = max(0.0, 1.0 - abs(game.price_dollars - midpoint) / (span / 2.0))

    if prioritize_sales:
        return 0.50 * sale + 0.30 * trend + 0.20 * fit
    # When sale boost is off, redistribute the 50% across trending and price-fit.
    return 0.65 * trend + 0.35 * fit


def rank_games(
    games: list[Game],
    *,
    prioritize_sales: bool,
    price_min: float,
    price_max: float,
) -> list[Game]:
    return sorted(
        games,
        key=lambda g: score_game(
            g,
            prioritize_sales=prioritize_sales,
            price_min=price_min,
            price_max=price_max,
        ),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run(min_dollars: float, max_dollars: float, prioritize_sales: bool,
        limit: int = 18, sleep_between: float = 0.25) -> dict:
    import sys
    print("[find-friend-slop] fetching featured categories...", file=sys.stderr)
    pool = fetch_featured()
    print(f"[find-friend-slop] {len(pool)} candidate appids — enriching with price/details", file=sys.stderr)
    games = build_games(pool, sleep_between=sleep_between)
    print(f"[find-friend-slop] enriched {len(games)} games", file=sys.stderr)
    filtered = filter_by_price(games, min_dollars, max_dollars)
    print(f"[find-friend-slop] {len(filtered)} games in ${min_dollars:.2f}-${max_dollars:.2f}", file=sys.stderr)
    ranked = rank_games(
        filtered,
        prioritize_sales=prioritize_sales,
        price_min=min_dollars,
        price_max=max_dollars,
    )
    top = ranked[:limit]
    return {
        "generated_at": int(time.time()),
        "filters": {
            "min_dollars": min_dollars,
            "max_dollars": max_dollars,
            "prioritize_sales": prioritize_sales,
        },
        "count": len(top),
        "games": games_to_dicts(top),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    from pathlib import Path

    p = argparse.ArgumentParser(description="Fetch trending Steam games in a price range.")
    p.add_argument("--min", dest="min_dollars", type=float, required=True, help="Minimum price ($).")
    p.add_argument("--max", dest="max_dollars", type=float, required=True, help="Maximum price ($).")
    p.add_argument("--prioritize-sales", action="store_true", help="Boost discounted games.")
    p.add_argument("--out", type=Path, default=Path("games.json"), help="Output JSON path.")
    p.add_argument("--limit", type=int, default=18, help="Max games to return.")
    args = p.parse_args(argv)

    if args.min_dollars < 0 or args.max_dollars < args.min_dollars:
        print("error: --max must be >= --min >= 0", file=sys.stderr)
        return 2

    payload = run(args.min_dollars, args.max_dollars, args.prioritize_sales, limit=args.limit)
    args.out.write_text(json.dumps(payload, indent=2))
    print(f"[find-friend-slop] wrote {payload['count']} games to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
