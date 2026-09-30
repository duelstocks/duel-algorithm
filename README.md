# DUEL — Open-Source Relative Stock Scoring Algorithm

**Live product:** [duelstocks.com](https://duelstocks.com) — compare any two US-listed stocks head-to-head using only official SEC EDGAR data.

This repository contains the **base 8-factor algorithm** that powers DUEL, plus one fully worked example (NVDA vs AMD) using real SEC EDGAR figures. It exists to show, transparently, exactly how the free relative score is calculated — no black box.

## What's here

- [`scripts/duel_engine.py`](scripts/duel_engine.py) — the scoring algorithm (`normalize_pair`, `compute_duel`, `check_consistency_flags`) and the SEC EDGAR XBRL fetcher used to derive the 8 factors from 10-K / 10-Q filings.
- [`docs/duels/nvda-vs-amd.html`](docs/duels/nvda-vs-amd.html) — a full worked example, including the consistency flags and a preview of what PRO subscribers get for the same duel.

## The 8 factors, in 5 signal blocks

| Block | Factor | Weight |
|---|---|---|
| Growth | Revenue Growth (3Y CAGR) | 18% |
| Margin Conversion | Operating Margin | 9% |
| Margin Conversion | Operating Cash Flow Margin | 9% |
| Margin Conversion | Free Cash Flow Margin | 9% |
| Capital Efficiency | Return on Invested Capital (ROIC) | 17% |
| Capital Efficiency | Asset Turnover | 7% |
| Accrual Quality | Sloan Ratio (lower is better) | 17% |
| Financial Strength | Debt / Equity (lower is better) | 14% |

*(September 2026: Receivables Turnover was retired and replaced with Debt / Equity; weights were retuned along with the new grouping. See Changelog.)*

The overall score is:

```
DUEL Score = Σ ( Wᵢ × Nᵢ ) × 100
```

Where **Wᵢ** is the factor's weight (sum = 1.0) and **Nᵢ** is that factor's soft relative score — scored by the **magnitude of the gap** between the two companies, not just who's ahead. A narrow gap stays close to a draw, and only a genuinely wide gap approaches a full win:

```
t = (a − b) / (|a| + |b|)
N_a = 0.5 + 0.5·t
N_b = 0.5 − 0.5·t
```

**Debt / Equity** = (Short-Term Debt + Long-Term Debt) / Stockholders' Equity, inverted (lower is better). When book equity is zero or negative, Debt/Equity is undefined (not misleadingly low) — treated as missing data rather than zero. See [`duel_engine.py`](scripts/duel_engine.py) for the exact code.

## Consistency flags (informational only)

After every duel, the algorithm runs four checks per company. These **never change the score** — they surface tension between factors that a single headline number can hide:

| Flag | Trigger | What it means |
|---|---|---|
| Paper profits | Op. Cash Margin < Operating Margin × 0.7 | Reported profit is running well ahead of cash |
| CapEx vacuum | FCF Margin < Op. Cash Margin × 0.3 | Operating cash is almost entirely absorbed by CapEx |
| No safety cushion | FCF Margin < 0 and Debt/Equity > 1.5 | Meaningful leverage plus negative free cash flow |
| Non-positive equity | Book equity ≤ 0 | Debt/Equity isn't economically meaningful here |

See `check_consistency_flags()` in [`duel_engine.py`](scripts/duel_engine.py).

## What's intentionally *not* here

This repo open-sources only the free base comparison. The following are deliberately **not** published — they're proprietary methodology, not just a locked feature:

- Custom factor weights and unlimited daily duels (free tier is 5/day on the site)
- **Resilience (STR) Report** — a fundamental-resilience scoring model with its own metrics and conflict-detection logic
- **DCF Valuation Report** — a multi-factor discounted cash flow model with company-specific WACC and growth-quality adjustments

You can see a preview of both reports' *output* (not their method) in the [worked example](docs/duels/nvda-vs-amd.html).

## A note on updates

This is a **static, hand-verified snapshot**, not an automated feed. (We initially tried automating it via GitHub Actions, but SEC EDGAR blocks requests from major cloud-provider IP ranges including GitHub's runners — so for now this repo is updated manually and occasionally, not on a schedule.) For current, live data on any pair of stocks, use [duelstocks.com](https://duelstocks.com).

## Changelog

- **September 2026** — factor model updated: 8 factors regrouped into 5 signal blocks (Growth, Margin Conversion, Capital Efficiency, Accrual Quality, Financial Strength); Receivables Turnover retired and replaced with Debt / Equity; default weights retuned; added 4 informational consistency flags (`check_consistency_flags`, don't affect the score). Example page and figures updated to match.
- **September 2026** — scoring formula updated from min-max normalization to a magnitude-aware model (see "The 8 factors" above). Example page and figures updated to match.
- **September 2026** — initial open-source release: base algorithm + one worked example (NVDA vs AMD).

## Disclaimer

For informational and educational purposes only. Not investment advice. Data comes exclusively from SEC EDGAR — no analyst estimates. Always do your own research before making investment decisions.

## License

See [LICENSE](LICENSE) — AGPLv3.
