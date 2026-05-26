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

---

## Second Calibration Pass

**Important:** Not financial advice. Not a backtest. No scoring code was changed.

---

### Run Details

| Field | Value |
|-------|-------|
| Date | 2026-05-26 |
| Time (UTC approx.) | ~19:53 — approximately 14 hours after the first pass |
| Command | `python -m app.main --watchlist watchlists/calibration_sample.txt --save-markdown --save-json` |
| Watchlist file | `watchlists/calibration_sample.txt` |
| Tickers attempted | 14 |
| Tickers succeeded | 14 |
| Tickers failed | 0 |
| Markdown output reviewed | `outputs/reports/WATCHLIST_20260526_195322.md` |
| JSON output reviewed | `outputs/results/WATCHLIST_20260526_195322.json` |

Neither output file was committed to the repository.

---

### Data Completeness Check

| Check | First Pass | Second Pass | Status |
|-------|-----------|-------------|--------|
| Company names populated | No — all null | Yes — all 14 present | ✅ Fixed |
| Current prices populated | No — all null | Yes — all 14 present | ✅ Fixed |
| Categories present | Yes | Yes | ✅ No change |
| Scores present | Yes | Yes | ✅ No change |
| Confidence levels present | Yes | Yes | ✅ No change |
| JSON `company_name` field | null for all | Populated for all | ✅ Fixed |
| JSON `current_price` field | null for all | Populated for all | ✅ Fixed |
| Any failures | 0 | 0 | ✅ No change |

The data completeness gap identified in the first pass is resolved. Company names and
current prices now flow correctly from the pipeline through to both the terminal summary,
the Markdown report, and the JSON export.

---

### Scoring Pattern Check

Results from both passes side by side. Scores reflect live market data at run time and
are expected to shift between runs.

| Ticker | First Pass Score | First Pass Category | Second Pass Score | Second Pass Category | Score Δ | Category Change? |
|--------|-----------------|---------------------|------------------|-----------------------|---------|-----------------|
| KO | 77.5 | Buy Candidate | 79.8 | Buy Candidate | +2.3 | No |
| JNJ | 72.8 | Buy Candidate | 67.5 | Watchlist | −5.3 | Yes — dropped |
| XOM | 72.6 | Buy Candidate | 59.5 | Watchlist | −13.1 | Yes — dropped |
| NVDA | 72.1 | Buy Candidate | 64.0 | Watchlist | −8.1 | Yes — dropped |
| JPM | 68.0 | Watchlist | 67.4 | Watchlist | −0.6 | No |
| PFE | 65.6 | Watchlist | 57.1 | Watchlist | −8.5 | No |
| MSFT | 65.0 | Watchlist | 66.2 | Watchlist | +1.2 | No |
| TSLA | 60.4 | Watchlist | 61.0 | Watchlist | +0.6 | No |
| SPY | 59.8 | Watchlist | 59.8 | Watchlist | 0.0 | No |
| CAT | 59.1 | Watchlist | 63.9 | Watchlist | +4.8 | No |
| AMZN | 58.9 | Watchlist | 58.9 | Watchlist | 0.0 | No |
| WMT | 54.1 | Hold | 58.2 | Watchlist | +4.1 | Yes — rose |
| INTC | 53.5 | Hold | 54.1 | Hold | +0.6 | No |
| MCD | 50.8 | Hold | 50.8 | Hold | 0.0 | No |

**Score range:** 50.8 – 79.8 (first pass: 50.8 – 77.5). Spread slightly wider.

**Category shifts across the 14-hour window:**
- JNJ, XOM, NVDA all moved down from Buy Candidate to Watchlist.
- WMT moved up from Hold to Watchlist.
- KO remained the top-scoring ticker and widened its lead.

These shifts are consistent with the pipeline responding to intraday price and
news changes. They do not indicate a scoring bug — they reflect that the model
consumes live market data, and results will vary between runs.

**Confidence levels:** All 14 tickers again received `confidence_level: medium`
despite a score spread of approximately 29 points. The confidence compression
pattern from the first pass persists. This is noted again but not acted on.

**Score compression:** No ticker reached Strong Buy Candidate (≥85) or Sell / Exit
Warning (<30). The full set landed between 50.8 and 79.8. This was also observed
in the first pass.

**Patterns still visible from first pass:**
- Score compression at the upper and lower ends remains (both passes).
- All-medium confidence regardless of score spread remains (both passes).
- KO still ranks highest, now more clearly ahead of the rest of the set.
- MCD still ranks lowest (50.8 in both passes — identical score, suggesting
  stable fundamental/risk conditions).

**New patterns observed:**
- Scores for energy (XOM) and healthcare (JNJ, NVDA) shifted more between
  passes than consumer staples (KO, MCD, WMT) or tech (MSFT, AMZN). This
  is consistent with higher intraday volatility in those sectors but is noted
  as a weak observation only.
- SPY and AMZN returned identical scores in both passes (59.8 and 58.9
  respectively), suggesting their underlying signals did not change between
  the two runs.

---

### Follow-Up Needed

Priority for individual ticker review is adjusted based on second-pass results:

1. **KO** — Still the top scorer, now at 79.8. Still worth individual review to
   understand the signal composition. Priority unchanged.
2. **XOM** — Moved from Buy Candidate (72.6) to Watchlist (59.5) in a single
   day. A 13-point intraday shift for a large stable energy company is notable.
   Adding to priority for individual review.
3. **MSFT** — Stable between passes (+1.2). Remains lower than expected for its
   fundamentals. Still a priority for individual review.
4. **MCD** — Identical score in both passes (50.8). Still lowest in the set.
   Priority unchanged.
5. **PFE** — Dropped 8.5 points but stayed in Watchlist. Still a priority for
   individual review to check trailing fundamental data.

Commands for individual review (unchanged from first pass):

```
python -m app.main KO --save-markdown --save-json
python -m app.main XOM --save-markdown --save-json
python -m app.main MSFT --save-markdown --save-json
python -m app.main MCD --save-markdown --save-json
python -m app.main PFE --save-markdown --save-json
```

---

### Decision

**No scoring code changes should be made yet.**

The second pass confirms:

1. The company name and current price data gap from the first pass is fully
   resolved. The watchlist output is now usable for manual calibration review.
2. All 14 tickers succeeded with no errors in both passes.
3. Score volatility between same-day runs is real and expected — the pipeline
   is producing live results, not cached snapshots. Individual ticker review
   should be done on a single run, not compared across separate watchlist runs.
4. The confidence compression pattern (all-medium across a 30-point spread)
   persists and remains a candidate calibration target, but does not warrant
   a code change without individual report evidence.
5. Score compression at the upper and lower ends persists and also remains a
   weak-evidence pattern only.

**Next step:** Run individual reports for the five priority tickers above and
fill in the calibration worksheet at `docs/scoring_calibration_worksheet.md`
before any scoring logic is discussed.
