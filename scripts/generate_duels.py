"""
generate_duels.py
Fetches SEC EDGAR data for a fixed list of ticker pairs, runs the base
8-factor DUEL algorithm, and renders static HTML pages into ../docs/duels/.

Run manually:
    python scripts/generate_duels.py

Run automatically:
    see .github/workflows/update-duels.yml
"""

import asyncio
import html
import json
import os
from datetime import datetime, timezone

from duel_engine import fetch_pair, FACTOR_LABELS

# ════════════════════════════════════════════════════════════
# Fixed demo pairs — intentionally NOT the full S&P 500.
# This repo is a showcase of the algorithm, not a content farm.
# ════════════════════════════════════════════════════════════
PAIRS = [
    ("NVDA", "AMD"),
    ("MSFT", "GOOGL"),
    ("AVGO", "PLTR"),
    ("AAPL", "META"),
    ("AMZN", "TSLA"),
]

MAIN_SITE = "https://duelstocks.com"
REPO_DOCS = os.path.join(os.path.dirname(__file__), "..", "docs")
DUELS_DIR = os.path.join(REPO_DOCS, "duels")

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{ticker_a} vs {ticker_b} — Fundamental Duel (SEC Data) | DUEL</title>
<meta name="description" content="Head-to-head comparison of {ticker_a} and {ticker_b} across 8 fundamental factors, calculated exclusively from SEC EDGAR filings using the open-source DUEL scoring algorithm.">
<link rel="stylesheet" href="../style.css">
<meta property="og:title" content="{ticker_a} vs {ticker_b} — Fundamental Duel">
<meta property="og:description" content="Relative fundamentals comparison based on SEC EDGAR data.">
<meta property="og:type" content="article">
</head>
<body>
<header class="site-header">
  <a href="../index.html" class="brand">DUEL — Open Algorithm</a>
  <a href="{main_site}" class="cta">Run unlimited duels on duelstocks.com &rarr;</a>
</header>

<main>
  <h1>{ticker_a} vs {ticker_b}</h1>
  <p class="subtitle">Relative fundamentals comparison &middot; SEC EDGAR data only &middot; no analyst estimates</p>

  <div class="score-board">
    <div class="score {a_win_class}"><span class="ticker">{ticker_a}</span><span class="score-num">{score_a}</span></div>
    <div class="vs">VS</div>
    <div class="score {b_win_class}"><span class="ticker">{ticker_b}</span><span class="score-num">{score_b}</span></div>
  </div>
  <p class="verdict"><strong>{winner}</strong> wins ({strength}, gap of {gap} points) based on the weighted 8-factor model below.</p>

  <table class="factor-table">
    <thead>
      <tr><th>Factor</th><th>{ticker_a}</th><th>{ticker_b}</th><th>Weight</th></tr>
    </thead>
    <tbody>
      {factor_rows}
    </tbody>
  </table>

  <section class="pro-box">
    <h2>This is the free base comparison.</h2>
    <p>The full DUEL platform also includes custom factor weights, unlimited daily duels, a downloadable PDF Battle Report, DCF Valuation, and the Resilience (STR) Report — all built on top of this same open algorithm.</p>
    <a class="cta-large" href="{main_site}">Compare any two stocks on duelstocks.com &rarr;</a>
  </section>

  <p class="disclaimer">Data source: SEC EDGAR (10-K / 10-Q filings). For informational and educational purposes only — not investment advice. Report date: {report_date}.</p>
  <p class="updated">Last updated: {updated_at} (UTC)</p>
</main>

<footer class="site-footer">
  <a href="{main_site}">duelstocks.com</a> &middot;
  <a href="{main_site}/methodology">Methodology</a> &middot;
  <a href="https://github.com/duelstocks">GitHub</a>
</footer>
</body>
</html>
"""

FACTOR_ROW = """<tr>
  <td>{label}</td>
  <td class="{a_cls}">{a_val}</td>
  <td class="{b_cls}">{b_val}</td>
  <td>{weight}%</td>
</tr>"""


def fmt_val(v):
    if v is None:
        return "—"
    return f"{v:.2f}"


def render_pair(ticker_a, ticker_b, data_a, data_b, result):
    rows = []
    for f in result["factors"]:
        a_cls = "better" if f["a_score"] > f["b_score"] else ""
        b_cls = "better" if f["b_score"] > f["a_score"] else ""
        rows.append(FACTOR_ROW.format(
            label=html.escape(f["label"]),
            a_val=fmt_val(f["a_raw"]),
            b_val=fmt_val(f["b_raw"]),
            weight=int(f["weight"] * 100),
            a_cls=a_cls,
            b_cls=b_cls,
        ))

    page = PAGE_TEMPLATE.format(
        ticker_a=ticker_a,
        ticker_b=ticker_b,
        main_site=MAIN_SITE,
        score_a=result["score_a"],
        score_b=result["score_b"],
        winner=result["winner"],
        strength=result["strength"],
        gap=result["gap"],
        a_win_class="winner" if result["winner"] == ticker_a else "",
        b_win_class="winner" if result["winner"] == ticker_b else "",
        factor_rows="\n      ".join(rows),
        report_date=data_a.get("report_date", "unknown"),
        updated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    )
    return page


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DUEL — Open-Source Stock Comparison Algorithm | SEC EDGAR Data</title>
<meta name="description" content="Open-source companion to duelstocks.com. Example head-to-head stock comparisons calculated from SEC EDGAR filings using the DUEL 8-factor algorithm.">
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="site-header">
  <span class="brand">DUEL — Open Algorithm</span>
  <a href="{main_site}" class="cta">duelstocks.com &rarr;</a>
</header>
<main>
  <h1>DUEL: Open-Source Stock Comparison Algorithm</h1>
  <p class="subtitle">This repository contains the base 8-factor relative-scoring algorithm behind <a href="{main_site}">duelstocks.com</a>, plus a handful of example duels generated automatically from live SEC EDGAR data.</p>

  <h2>Example duels</h2>
  <ul class="duel-list">
    {duel_links}
  </ul>

  <section class="pro-box">
    <h2>Want to compare any two stocks?</h2>
    <p>The full platform on <a href="{main_site}">duelstocks.com</a> lets you run unlimited duels on any US-listed company, adjust factor weights, and download PDF Battle Reports, DCF Valuations, and Resilience (STR) Reports.</p>
    <a class="cta-large" href="{main_site}">Try duelstocks.com &rarr;</a>
  </section>

  <p class="disclaimer">Data source: SEC EDGAR. For informational and educational purposes only — not investment advice.</p>
</main>
<footer class="site-footer">
  <a href="{main_site}">duelstocks.com</a> &middot;
  <a href="{main_site}/methodology">Methodology</a>
</footer>
</body>
</html>
"""


def render_index(pairs):
    links = []
    for a, b in pairs:
        links.append(f'<li><a href="duels/{a.lower()}-vs-{b.lower()}.html">{a} vs {b}</a></li>')
    return INDEX_TEMPLATE.format(main_site=MAIN_SITE, duel_links="\n    ".join(links))


async def main():
    os.makedirs(DUELS_DIR, exist_ok=True)
    successful_pairs = []

    for ticker_a, ticker_b in PAIRS:
        print(f"Fetching {ticker_a} vs {ticker_b}...")
        outcome = await fetch_pair(ticker_a, ticker_b)
        if not outcome:
            print(f"  SKIPPED: could not fetch data for {ticker_a} vs {ticker_b}")
            continue

        page = render_pair(ticker_a, ticker_b, outcome["a"], outcome["b"], outcome["result"])
        filename = f"{ticker_a.lower()}-vs-{ticker_b.lower()}.html"
        with open(os.path.join(DUELS_DIR, filename), "w", encoding="utf-8") as f:
            f.write(page)
        print(f"  OK -> docs/duels/{filename}")
        successful_pairs.append((ticker_a, ticker_b))

    with open(os.path.join(REPO_DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_index(successful_pairs))

    with open(os.path.join(REPO_DOCS, ".nojekyll"), "w") as f:
        f.write("")

    print(f"\nDone. {len(successful_pairs)}/{len(PAIRS)} duels generated.")


if __name__ == "__main__":
    asyncio.run(main())
