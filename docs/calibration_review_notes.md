# Calibration Review Notes

## Purpose

This document records observations from the first calibration sample run. It is
used to decide whether future scoring calibration is needed and, if so, where to
focus.

**Important:**

- This is not financial advice.
- This is not a backtest.
- This does not change scoring behavior.
- This does not recommend buying or selling any ticker.

---

## Run Details

| Field | Value |
|-------|-------|
| Date | 2026-05-26 |
| Command | `python -m app.main --watchlist watchlists/calibration_sample.txt --save-markdown --save-json` |
| Watchlist file | `watchlists/calibration_sample.txt` |
| Tickers attempted | 14 |
| Tickers succeeded | 14 |
| Tickers failed | 0 |
| Markdown output reviewed | `outputs/reports/WATCHLIST_20260526_053942.md` |
| JSON output reviewed | `outputs/results/WATCHLIST_20260526_053942.json` |

Neither output file was committed to the repository.

---

## Watchlist Results Summary

All scores are from the run above. Company names and prices were not populated
by the watchlist pipeline (see observations below). Categories and scores are
the raw output of the current scoring model.

| Ticker | Company | Score | Category | Confidence | Price | Initial Observation |
|--------|---------|-------|----------|------------|-------|---------------------|
| KO | — | 77.5 | Buy Candidate | Medium | — | Highest score in the set; may warrant individual review to check whether consumer staples signal weights are pulling this higher than expected. |
| JNJ | — | 72.8 | Buy Candidate | Medium | — | Reasonable for a large healthcare name with stable fundamentals. Worth confirming during individual review. |
| XOM | — | 72.6 | Buy Candidate | Medium | — | Energy sector landing near healthcare and pharma is notable. Worth individual review to check risk signal behavior for cyclical exposure. |
| NVDA | — | 72.1 | Buy Candidate | Medium | — | High-growth tech landing lower than KO/JNJ is worth checking; fundamental signals for high-valuation names may be pulling this down. |
| JPM | — | 68.0 | Watchlist | Medium | — | Looks plausible. Financial sector in Watchlist range seems reasonable. |
| PFE | — | 65.6 | Watchlist | Medium | — | Higher than expected given recent challenges; worth individual review to check whether fundamental signals are reading trailing data. |
| MSFT | — | 65.0 | Watchlist | Medium | — | Notably lower than KO and XOM despite MSFT's stronger recent fundamentals. Category may be worth checking during calibration. |
| TSLA | — | 60.4 | Watchlist | Medium | — | Mid-Watchlist for a volatile high-growth name; seems plausible. |
| SPY | — | 59.8 | Watchlist | Medium | — | ETF scoring is informational only; signals designed for individual equities are less meaningful here. |
| CAT | — | 59.1 | Watchlist | Medium | — | Cyclical industrial in Watchlist range; looks reasonable given macro sensitivity. |
| AMZN | — | 58.9 | Watchlist | Medium | — | Large-cap growth landing near CAT and SPY may be worth individual review. |
| WMT | — | 54.1 | Hold | Medium | — | Low-growth retail at the bottom of Watchlist / top of Hold boundary; plausible. |
| INTC | — | 53.5 | Hold | Medium | — | Challenged tech in Hold range; this is one of the expected lower-score examples and the result looks directionally correct. |
| MCD | — | 50.8 | Hold | Medium | — | Lowest score in the set; may be worth checking whether news or risk signals are depressing a relatively stable consumer name. |

---

## Data Gaps Observed

### Company names and prices not populated

Every row in the JSON output shows `"company_name": null` and `"current_price":
null`. The Markdown report renders these as `—`. This is expected behavior given
the current pipeline: the watchlist scanner collects results from `build_stock_report`,
which assembles a `StockReport` from a `Rating`. The `Rating` model does not
carry company name or current price, so these fields do not flow through to
`WatchlistResult`.

**Impact:** The watchlist-level output is less readable for manual review without
company names. Individual single-ticker reports would include more context if the
`StockReport` model has those fields populated.

**Proposed action:** No code change now. Note as a candidate data completeness
improvement for a later task. Individual ticker review (see Follow-Up section)
will provide richer context.

### All confidence levels are "medium"

Every ticker received `confidence_level: "medium"` regardless of score spread.
The scores range from 50.8 to 77.5 — a spread of nearly 27 points — yet all
14 tickers landed on the same confidence level. This suggests the confidence
calculation may not be differentiating across the current score distribution.

**Impact:** Confidence level is an important explanatory output. If it does not
vary, it adds little information to the report.

**Proposed action:** No code change now. Flag as a candidate calibration target
after individual ticker reports are reviewed. See Potential Calibration Patterns.

---

## Potential Calibration Patterns

Patterns are recorded only where the current output provides visible evidence.
All evidence strength ratings are Weak at this stage — a single watchlist run
is not enough to draw conclusions.

| Pattern Observed | Example Tickers | Affected Area | Evidence Strength | Notes |
|------------------|-----------------|---------------|-------------------|-------|
| Consumer staples and energy scoring above large-cap tech | KO (77.5) vs MSFT (65.0), AMZN (58.9) | Fundamental / Composite weights | Weak | KO and XOM rank higher than MSFT and AMZN. Could reflect technical momentum differences at the time of the run, or fundamental signal weighting that favors dividend/stability profiles. Needs individual report review to determine cause. |
| All confidence levels identical across a 27-point score range | All 14 tickers | Confidence calculation | Weak | No confidence variation observed. May indicate the confidence bands are set too broadly, or that the current signal set consistently produces medium-range confidence values. Needs individual report inspection. |
| Score compression — no ticker scored above 85 or below 50 | Full set | Category thresholds / Signal impacts | Weak | The full 14-ticker set landed between 50.8 and 77.5. No "Strong Buy Candidate" or below-Hold categories appeared. Could be appropriate for current market conditions, or could indicate the upper and lower score ranges are difficult to reach. Needs more data points. |
| PFE ranking similarly to MSFT despite different fundamental conditions | PFE (65.6) vs MSFT (65.0) | Fundamental signals | Weak | A recently challenged pharma company and a dominant software platform received nearly identical scores. Worth individual report comparison to understand which signals drove the similarity. |

**No pattern currently has sufficient evidence to justify a code change.**

---

## Follow-Up Individual Reviews Needed

The following tickers should be run individually with `--save-markdown --save-json`
and reviewed against the calibration worksheet before any scoring logic is changed.
Priority is based on results that seem surprising or are near category boundaries.

1. **KO** — Highest score in the set; check whether the result reflects genuine
   signal strength or a weighting artifact.
2. **MSFT** — Lower than expected relative to its fundamentals and market position;
   check which signal categories are pulling the score down.
3. **PFE** — Higher than expected given recent performance challenges; check
   trailing fundamental data.
4. **MCD** — Lowest score in the set; check whether news or risk signals are
   disproportionately penalizing a stable consumer name.
5. **NVDA** — Buy Candidate at 72.1 despite high valuations; check how the
   fundamental valuation signals are interacting with strong technical signals.

Commands for individual review:

```
python -m app.main KO --save-markdown --save-json
python -m app.main MSFT --save-markdown --save-json
python -m app.main PFE --save-markdown --save-json
python -m app.main MCD --save-markdown --save-json
python -m app.main NVDA --save-markdown --save-json
```

Open each generated Markdown report and fill in one row of the calibration
worksheet at `docs/scoring_calibration_worksheet.md`.

---

## Decision

**No scoring code changes should be made yet.**

The first watchlist run provides a high-level snapshot but not enough detail to
identify systematic miscalibrations. Before tuning thresholds, weights, or signal
logic:

- Individual reports for the five priority tickers above must be reviewed.
- At least one pattern needs to reach "Moderate" evidence strength (3–5 consistent
  examples) in the calibration worksheet.
- The confidence calculation behavior should be investigated to understand whether
  the current output is expected or indicates a gap.

See `docs/scoring_calibration_plan.md` for the full decision gate criteria.
