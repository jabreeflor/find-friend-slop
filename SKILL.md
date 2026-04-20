---
name: find-friend-slop
description: Find trending Steam games in a price range to propose to friends. Use when the user asks for Steam game recommendations, "slop for my friends", budget-constrained game suggestions, or anything of the form "what should we play, under $X". Takes a price range and optional sale-prioritization, then builds a polished HTML proposal page where each card links to the Steam store.
---

# find-friend-slop

Build a clickable HTML proposal page of trending Steam games that fit a price range, so the user can send it to friends and they can one-click into the Steam store for any title that catches their eye.

## When to trigger

- "find some slop for my friends"
- "recommend Steam games under $20" / "between $10 and $40"
- "what should we play tonight, budget $X"
- Any ask for Steam recs bounded by price, with or without "on sale"

## Arguments to parse from the user

- **Price range** (required). Accept `$0-$30`, `under $20`, `free to $15`, `$5–$25`. If only a max is given, default min to `0`. If the user is vague, default to `$0-$30`.
- **Prioritize sales** (optional, default off). Turn on if the user mentions "on sale", "discounted", "cheap", "best deals", "sale".
- **Limit** (optional, default 18).

## Procedure

1. **Work from the skill directory.** Create `out/` if missing.

2. **Fetch + rank:**
   ```bash
   python3 scripts/fetch_games.py \
     --min <MIN> --max <MAX> \
     [--prioritize-sales] \
     --limit <N> \
     --out out/games.json
   ```
   Hits Steam's public `featuredcategories` and `appdetails` endpoints (no API key needed). Filters by final price. Ranks via `score_game()` in `scripts/fetch_games.py` — that function is the intentional customization point.

3. **Render HTML:**
   ```bash
   python3 scripts/generate_html.py --in out/games.json --out out/proposals.html
   ```

4. **Report back** to the user with:
   - Path to `out/proposals.html`
   - Price range + whether sales were prioritized
   - Number of proposals
   - Suggest `open out/proposals.html` (macOS) to launch it

5. **If fewer than 5 games** come back, suggest widening the price range or turning off `--prioritize-sales`.

## Outputs

- `out/games.json` — raw ranked game data (keep for re-rendering without refetching)
- `out/proposals.html` — polished, shareable page. Every card is a link to the Steam store.

## Customization points

- `scripts/fetch_games.py` → `score_game()` — tune ranking (bucket weights, sale boost).
- `scripts/generate_html.py` → `CSS` constant — tune visuals.

## Notes

- Prices default to USD (`cc=us`). Change in `fetch_games.py` for other regions.
- Free-to-play titles have `price_overview == null`; treated as $0 and included when `min == 0`.
- Between `appdetails` requests the fetcher sleeps 0.25s to respect Steam's rate limit (~200 req / 5 min per IP).
