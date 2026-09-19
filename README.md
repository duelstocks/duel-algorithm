# DUEL — Open-Source Relative Stock Scoring Algorithm

**Live product:** [duelstocks.com](https://duelstocks.com) — compare any two US-listed stocks head-to-head using only official SEC EDGAR data.

This repository contains the **base 8-factor algorithm** that powers DUEL, plus one fully worked example (NVDA vs AMD) using real SEC EDGAR figures. It exists to show, transparently, exactly how the free relative score is calculated — no black box.

## What's here

- [`scripts/duel_engine.py`](scripts/duel_engine.py) — the scoring algorithm (`normalize_pair`, `compute_duel`) and the SEC EDGAR XBRL fetcher used to derive the 8 factors from 10-K / 10-Q filings.
- [`docs/duels/nvda-vs-amd.html`](docs/duels/nvda-vs-amd.html) — a full worked example, including a preview of what PRO subscribers get for the same duel.

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

Each factor is scored by the **magnitude of the gap** between the two companies, not just who's ahead — a narrow gap stays close to a draw, and only a genuinely wide gap approaches a full win:

```
t = (a − b) / (|a| + |b|)
N_a = 0.5 + 0.5·t
N_b = 0.5 − 0.5·t
```

The per-factor scores are then combined using the weights above. (Before September 2026, this used a pure min-max normalization instead, which could swing all the way to a 100/0 split even for a modest gap — the current version is a more honest reflection of *how much* stronger one company is, not just *that* it's stronger.) See [`duel_engine.py`](scripts/duel_engine.py) for the exact code.

## What's intentionally *not* here

This repo open-sources only the free base comparison. The following are deliberately **not** published — they're proprietary methodology, not just a locked feature:

- Custom factor weights and unlimited daily duels (free tier is 5/day on the site)
- **Resilience (STR) Report** — a fundamental-resilience scoring model with its own metrics and conflict-detection logic
- **DCF Valuation Report** — a multi-factor discounted cash flow model with company-specific WACC and growth-quality adjustments

You can see a preview of both reports' *output* (not their method) in the [worked example](docs/duels/nvda-vs-amd.html).

## A note on updates

This is a **static, hand-verified snapshot**, not an automated feed. (We initially tried automating it via GitHub Actions, but SEC EDGAR blocks requests from major cloud-provider IP ranges including GitHub's runners — so for now this repo is updated manually and occasionally, not on a schedule.) For current, live data on any pair of stocks, use [duelstocks.com](https://duelstocks.com).

## Changelog

- **September 2026** — scoring formula updated from min-max normalization to a magnitude-aware model (see "The 8 factors" above). Example page and figures updated to match.
- **September 2026** — initial open-source release: base algorithm + one worked example (NVDA vs AMD).

## Disclaimer

For informational and educational purposes only. Not investment advice. Data comes exclusively from SEC EDGAR — no analyst estimates. Always do your own research before making investment decisions.

## License

See [LICENSE](LICENSE) — AGPLv3.
