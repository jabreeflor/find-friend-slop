#!/usr/bin/env python3
"""Render the ranked games JSON from fetch_games.py into a polished HTML page.

JSON shape consumed (see fetch_games.py):
  {
    "generated_at": int,
    "filters": {"min_dollars", "max_dollars", "prioritize_sales"},
    "count": int,
    "games": [
      {appid, name, header_image, store_url, price_cents, original_cents,
       discount_pct, is_free, on_sale, short_description,
       trending_rank, source_bucket}
    ]
  }
"""
import argparse
import html
import json
import sys
from pathlib import Path

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Find Friend Slop — Steam game proposals</title>
<style>
  :root {{
    --bg: #0b0f17;
    --bg-elev: #131a26;
    --bg-card: #18202f;
    --border: #232c3d;
    --text: #e6edf7;
    --muted: #8a96ab;
    --accent: #66c0f4;
    --accent-2: #a4d007;
    --sale: #4c6b22;
    --sale-badge: #beee11;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
    background:
      radial-gradient(1200px 800px at 80% -10%, rgba(102,192,244,0.10), transparent 60%),
      radial-gradient(900px 700px at -10% 10%, rgba(164,208,7,0.07), transparent 60%),
      var(--bg);
    color: var(--text);
    min-height: 100vh;
  }}
  header {{
    padding: 56px 48px 32px;
    border-bottom: 1px solid var(--border);
    background: linear-gradient(180deg, rgba(255,255,255,0.02), transparent);
  }}
  header h1 {{
    margin: 0 0 8px; font-size: 38px; letter-spacing: -0.02em; font-weight: 700;
  }}
  header h1 .accent {{ color: var(--accent); }}
  header p.tagline {{ margin: 0; color: var(--muted); font-size: 16px; }}
  .meta-row {{
    display: flex; gap: 12px; flex-wrap: wrap; margin-top: 20px;
  }}
  .pill {{
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 6px 14px; font-size: 13px; color: var(--muted);
  }}
  .pill strong {{ color: var(--text); font-weight: 600; }}
  main {{ padding: 32px 48px 64px; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 20px;
  }}
  .card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
    text-decoration: none;
    color: inherit;
    display: flex;
    flex-direction: column;
    transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
    position: relative;
  }}
  .card:hover {{
    transform: translateY(-3px);
    border-color: var(--accent);
    box-shadow: 0 12px 28px -16px rgba(102,192,244,0.6);
  }}
  .img-wrap {{
    aspect-ratio: 460 / 215;
    background: #0a0e16;
    overflow: hidden;
    position: relative;
  }}
  .img-wrap img {{
    width: 100%; height: 100%; object-fit: cover; display: block;
  }}
  .badge-rank {{
    position: absolute; top: 10px; left: 10px;
    background: rgba(11,15,23,0.85);
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 11px; font-weight: 600; letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 4px 8px; border-radius: 6px;
  }}
  .badge-bucket {{
    position: absolute; bottom: 10px; left: 10px;
    background: rgba(11,15,23,0.85);
    border: 1px solid var(--border);
    color: var(--accent);
    font-size: 10px; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 3px 7px; border-radius: 4px;
  }}
  .badge-sale {{
    position: absolute; top: 10px; right: 10px;
    background: var(--sale-badge);
    color: #1f2a05;
    font-weight: 700;
    font-size: 13px;
    padding: 4px 8px;
    border-radius: 6px;
  }}
  .body {{
    padding: 14px 16px 16px;
    display: flex; flex-direction: column; gap: 10px;
    flex: 1;
  }}
  h3 {{ margin: 0; font-size: 17px; font-weight: 600; line-height: 1.25; }}
  .desc {{
    margin: 0; color: var(--muted); font-size: 13px; line-height: 1.45;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden;
  }}
  .price-row {{
    display: flex; align-items: center; gap: 10px;
    padding-top: 10px; margin-top: auto; border-top: 1px solid var(--border);
  }}
  .price-final {{ font-weight: 700; font-size: 16px; }}
  .price-original {{ color: var(--muted); text-decoration: line-through; font-size: 13px; }}
  .price-discount {{
    background: var(--sale); color: var(--sale-badge);
    font-weight: 700; font-size: 12px;
    padding: 2px 6px; border-radius: 4px;
  }}
  .price-free {{ color: var(--accent-2); font-weight: 700; }}
  .empty {{ padding: 80px 0; text-align: center; color: var(--muted); }}
  footer {{
    padding: 24px 48px 48px;
    text-align: center; color: var(--muted); font-size: 12px;
  }}
  footer a {{ color: var(--accent); text-decoration: none; }}
</style>
</head>
<body>
  <header>
    <h1>Find <span class="accent">Friend Slop</span></h1>
    <p class="tagline">Trending Steam games your friends will actually play this weekend.</p>
    <div class="meta-row">
      <span class="pill">Budget <strong>${min_price:.2f} – ${max_price:.2f}</strong></span>
      <span class="pill">Sale priority <strong>{sale_mode}</strong></span>
      <span class="pill"><strong>{count}</strong> proposals</span>
    </div>
  </header>
  <main>
    {body}
  </main>
  <footer>
    Generated by <a href="https://github.com/jabreeflor/find-friend-slop">find-friend-slop</a>.
    Click any card to open the Steam store page.
  </footer>
</body>
</html>
"""

BUCKET_LABEL = {
    "specials": "On Sale",
    "top_sellers": "Top Seller",
    "new_releases": "New Release",
    "coming_soon": "Coming Soon",
}


def render_card(game: dict, index: int) -> str:
    name = html.escape(game.get("name", "Unknown"))
    desc = html.escape(game.get("short_description", ""))
    img = html.escape(game.get("header_image") or "")
    url = html.escape(game.get("store_url", "#"))

    discount = game.get("discount_pct", 0) or 0
    is_free = game.get("is_free")
    price_cents = game.get("price_cents", 0)
    original_cents = game.get("original_cents", price_cents)
    bucket = game.get("source_bucket", "")

    if is_free:
        price_html = '<span class="price-final price-free">Free to Play</span>'
    elif discount > 0:
        price_html = (
            f'<span class="price-discount">-{discount}%</span>'
            f'<span class="price-original">${original_cents/100:.2f}</span>'
            f'<span class="price-final">${price_cents/100:.2f}</span>'
        )
    else:
        price_html = f'<span class="price-final">${price_cents/100:.2f}</span>'

    sale_badge = f'<span class="badge-sale">-{discount}%</span>' if discount > 0 else ""
    bucket_badge = (
        f'<span class="badge-bucket">{html.escape(BUCKET_LABEL.get(bucket, bucket))}</span>'
        if bucket
        else ""
    )
    img_html = f'<img src="{img}" alt="" loading="lazy" />' if img else ""

    return f"""
      <a class="card" href="{url}" target="_blank" rel="noopener">
        <div class="img-wrap">
          {img_html}
          <span class="badge-rank">#{index + 1}</span>
          {sale_badge}
          {bucket_badge}
        </div>
        <div class="body">
          <h3>{name}</h3>
          <p class="desc">{desc}</p>
          <div class="price-row">{price_html}</div>
        </div>
      </a>
    """


def render(payload: dict) -> str:
    games = payload.get("games", [])
    filters = payload.get("filters", {})
    if not games:
        body = '<div class="empty">No games matched your filters. Widen the price range and try again.</div>'
    else:
        cards = "".join(render_card(g, i) for i, g in enumerate(games))
        body = f'<div class="grid">{cards}</div>'

    return PAGE.format(
        min_price=filters.get("min_dollars", 0),
        max_price=filters.get("max_dollars", 0),
        sale_mode="ON" if filters.get("prioritize_sales") else "off",
        count=len(games),
        body=body,
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Render games JSON to HTML.")
    p.add_argument("--in", dest="input", required=True, help="Path to games JSON")
    p.add_argument("--out", dest="output", required=True, help="Path to write HTML")
    args = p.parse_args()
    payload = json.loads(Path(args.input).read_text("utf-8"))
    Path(args.output).write_text(render(payload), encoding="utf-8")
    print(f"[html] wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
