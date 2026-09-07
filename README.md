# DUEL — Open-Source Relative Stock Scoring Algorithm

**Live product:** [duelstocks.com](https://duelstocks.com) — compare any two US-listed stocks head-to-head using only official SEC EDGAR data.

This repository contains the **base 8-factor algorithm** that powers DUEL, plus a small set of example duels generated automatically from live SEC filings. It exists to show, transparently, exactly how the relative score is calculated — no black box.

## What's here

- `scripts/duel_engine.py` — the scoring algorithm (`normalize_pair`, `compute_duel`) and the SEC EDGAR XBRL fetcher used to derive the 8 factors from 10-K / 10-Q filings.
- `scripts/generate_duels.py` — generates static HTML pages for a fixed set of example pairs.
- `docs/` — the generated GitHub Pages site.
- `.github/workflows/update-duels.yml` — refreshes the example duels monthly from live data.

## The 8 factors

| Factor | Weight |
|---|---|
| Revenue Growth (3Y CAGR) | 16% |
| Operating Cash Flow Margin | 15% |
| Return on Invested Capital (ROIC) | 15% |
| Sloan Ratio (lower is better) | 12% |
| Operating Margin | 12% |
| Free Cash Flow Margin | 12% |
| Asset Turnover | 10% |
| Receivables Turnover | 8% |

Each factor is min-max normalized between the two companies being compared (so scores are **relative to the opponent**, not an absolute rating), then combined using the weights above.

## What's intentionally *not* here

This repo reproduces only the free base comparison. The following remain PRO features on [duelstocks.com](https://duelstocks.com), not open-sourced here:

- Custom factor weights
- Unlimited daily duels (free tier is 5/day on the site)
- PDF Battle Report export
- DCF Valuation
- Resilience Report (STR)

## Example duels

See the generated site: [duels index](docs/index.html) (or the live GitHub Pages URL once enabled).

Current showcase pairs: `NVDA vs AMD`, `MSFT vs GOOGL`, `AVGO vs PLTR`, `AAPL vs META`, `AMZN vs TSLA`.

## Running it yourself

```bash
pip install -r requirements.txt
cd scripts
python generate_duels.py
```

Requires outbound access to `sec.gov` / `data.sec.gov`.

## Disclaimer

For informational and educational purposes only. Not investment advice. Data comes exclusively from SEC EDGAR — no analyst estimates. Always do your own research before making investment decisions.

## License

See [LICENSE](LICENSE).
