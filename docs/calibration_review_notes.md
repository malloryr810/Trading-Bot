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

---

## Individual Ticker Review Pass

**Important:** Not financial advice. Not a backtest. No scoring code was changed.

---

### Run Details

| Field | Value |
|-------|-------|
| Date | 2026-05-26 |
| Time (UTC approx.) | ~19:59–20:01 |
| Tickers reviewed | KO, XOM, MSFT, MCD, PFE |
| All five succeeded | Yes — no errors |

Commands used:

```
python -m app.main KO   --save-markdown --save-json
python -m app.main XOM  --save-markdown --save-json
python -m app.main MSFT --save-markdown --save-json
python -m app.main MCD  --save-markdown --save-json
python -m app.main PFE  --save-markdown --save-json
```

Output files reviewed (not committed):

| Ticker | Markdown | JSON |
|--------|----------|------|
| KO | `outputs/reports/KO_20260526_195905.md` | `outputs/results/KO_20260526_195905.json` |
| XOM | `outputs/reports/XOM_20260526_200010.md` | `outputs/results/XOM_20260526_200010.json` |
| MSFT | `outputs/reports/MSFT_20260526_200040.md` | `outputs/results/MSFT_20260526_200040.json` |
| MCD | `outputs/reports/MCD_20260526_200052.md` | `outputs/results/MCD_20260526_200052.json` |
| PFE | `outputs/reports/PFE_20260526_200113.md` | `outputs/results/PFE_20260526_200113.json` |

---

### Sub-scores for Reference

| Ticker | Composite | Technical | Fundamental | News | Risk |
|--------|-----------|-----------|-------------|------|------|
| KO | 79.8 | 97.5 | 87.5 | 50.0 | 75.0 |
| XOM | 59.5 | 47.5 | 80.0 | 52.5 | 65.0 |
| MSFT | 66.2 | 52.5 | 95.0 | 57.5 | 65.0 |
| MCD | 50.8 | 22.5 | 82.5 | 50.0 | 65.0 |
| PFE | 65.0 | 70.0 | 72.5 | 47.5 | 70.0 |

---

### Individual Review Table

| Ticker | Company | Score | Category | Confidence | Technical Read | Fundamental Read | News/Risk Read | Calibration Observation | Follow-Up Needed |
|--------|---------|-------|----------|------------|----------------|------------------|----------------|-------------------------|-----------------|
| KO | The Coca-Cola Company | 79.8 | Buy Candidate | Medium | 97.5 — near-perfect: bullish trend, all three SMAs bullish, MACD bullish, RSI neutral, beta 0.36, vol 15.7%. Zero bearish signals. | 87.5 — strong: fwd PE 23.1 attractive, 27.8% profit margin (Strong), revenue +12.1% and EPS +18.2% growing strongly, FCF positive. Moderate D/E (124.9) is the only non-bullish fundamental. | 50.0 — fully neutral: no positive or negative news terms matched in 10 headlines. News is not a drag, but adds no positive signal. | Score is well-explained. Buy Candidate at 79.8 is internally consistent: near-perfect technicals and strong fundamentals. The weakness area is news (50.0), which is itself neutral — not bearish. Zero bearish signals makes Medium confidence feel understated (see Patterns). | Confidence level with 14 bullish / 0 bearish signals — candidate for future confidence calibration review. |
| XOM | Exxon Mobil Corporation | 59.5 | Watchlist | Medium | 47.5 — weak: below SMA 20 and SMA 50 (downtrend), but SMA 200 still bullish and MACD bullish. Mixed picture with a bearish short-term trend dragging a 35%-weighted category. | 80.0 — solid: fwd PE 14.3 attractive, D/E 18.3 conservative, FCF positive. Profitability is only weak-bullish (7.8% margin). Growth is neutral because EPS fell -43.4% against revenue growth of +2.6%. | 52.5 — neutral-slight positive: "acquisition" triggered a weak bullish sentiment signal, no risk terms. Low news impact. | The Watchlist score at 59.5 is directly explained by the poor technical picture (47.5 at 35% weight). Strong fundamentals are not enough to lift the composite with technicals this weak. The -43.4% EPS decline contributing only a neutral (not bearish) growth signal is the most notable model behavior here — worth revisiting. | EPS growth signal behavior when revenue is slightly positive but earnings decline sharply (see Patterns). |
| MSFT | Microsoft Corporation | 66.2 | Watchlist | Medium | 52.5 — mixed: trend bullish (above SMA 20 and 50), but price is below SMA 200 (bearish strong signal) and MACD is bearish. The SMA 200 bearish signal is the largest single technical headwind. | 95.0 — exceptional: profit margin 39.3% (Strong), revenue +18.3% and EPS +23.4% (both Strong), D/E 30.3 conservative, FCF positive, fwd PE 21.5 attractive. Near-perfect fundamental read. | 57.5 — slightly positive: "beat," "earnings beat," and "partnership" terms fired. One risk signal (regulatory) was flagged but only weak-bearish. Modest positive news contribution. | Watchlist at 66.2 is internally consistent given the technical drag. The anomaly is the magnitude of the gap: MSFT has the strongest fundamental sub-score (95.0) of all five tickers and yet only ranks fourth. This is a structural result of the 35% technical weight overriding 25% fundamental weight. Worth noting as a calibration candidate but no change is warranted yet. The -33.9% maximum drawdown (moderate risk signal) also adds a moderate neutral drag. | MSFT below its 200-SMA with strong fundamentals — the structural tension between technical weight (35%) and fundamental weight (25%) is most visible here. |
| MCD | McDonald's Corporation | 50.8 | Hold | Medium | 22.5 — bearish across the board: all three SMA levels bearish (below SMA 20, 50, AND 200), trend bearish. Only MACD is bullish. Full technical downtrend with high 35% weight. | 82.5 — solid: fwd PE 19.6 attractive, profit margin 31.6% (Strong), revenue +9.4% and EPS +6.9% both positive, FCF positive. Debt-to-equity data is unavailable (null) — scored neutral with 0.30 confidence. | 50.0 — fully neutral: no positive or negative news terms matched in 10 headlines. Recent 30-day return is -8.3% — scored as neutral (just above the -10% bearish threshold). | Hold at 50.8 is directly explained by the technical picture: a technical score of 22.5 with 35% weight mathematically holds the composite near the Hold/Watchlist boundary regardless of fundamentals. The model is behaving as designed. Notable: D/E unavailable for MCD likely because yfinance does not report negative equity (franchise structure) — the null handling is graceful. | D/E data unavailability for franchise-model companies is a known limitation. The -8.3% 30-day return being just above the -10% bearish threshold is a borderline case worth watching. |
| PFE | Pfizer Inc. | 65.0 | Watchlist | Medium | 70.0 — mixed-positive: above SMA 20 and SMA 200, but below SMA 50. Trend classified as "mixed" (not bullish or bearish). MACD bullish. Reasonable technical reading. | 72.5 — moderate: fwd PE 9.1 very attractive (bullish), profit margin 11.8% weak-bullish, growth neutral (revenue +5.4% but EPS -10.1%), D/E 71.6 neutral, FCF positive. The EPS decline creates a neutral growth signal even though the forward PE is very cheap. | 47.5 — slightly negative: news balanced between positive and negative (neutral sentiment), but "investigation" risk term fired (weak bearish risk signal). The risk headline is PFE's weakest area. | Watchlist at 65.0 is plausible given the mixed signals. PFE's very low fwd PE (9.1) registers as attractive, which is correct under the current rules. However, a low PE combined with declining earnings can sometimes indicate a value trap — the current model reads the PE signal in isolation and cannot detect the context. This is a known limitation of rule-based valuation signals, not a bug. The investigation risk term is real and correctly weighted. | The interaction between a very low PE (scored bullish) and declining EPS (scored neutral, not bearish) is an area for future calibration review. |

---

### Cross-Ticker Patterns

| Pattern Observed | Example Tickers | Affected Area | Evidence Strength | Notes |
|------------------|-----------------|---------------|-------------------|-------|
| Technical score dominates category outcomes | MCD (tech 22.5 → Hold despite fund 82.5), XOM (tech 47.5 → Watchlist despite fund 80.0), KO (tech 97.5 → Buy Candidate) | Technical weight (35%) vs Fundamental weight (25%) | **Moderate** — consistent across all five tickers | The 35% technical weight means a poor technical setup can override strong fundamentals, and vice versa. Whether this weighting is appropriate is a candidate calibration question, but the behavior is consistent and explainable. At least three tickers demonstrate this pattern. |
| All five tickers show Medium confidence regardless of signal composition | KO (14 bullish, 0 bearish), MCD (8 bullish, 4 bearish), PFE (10 bullish, 2 bearish) | Confidence calculation | **Moderate** — five out of five in this pass; all 14 in the watchlist pass | Medium confidence spans 0.45–0.70 average signal confidence. Most signals have individual confidence values in the 0.50–0.70 range, so 20 mixed signals almost always average into the medium band. KO with zero bearish signals still gets Medium rather than High because the average stays below 0.70. This is the most consistent pattern observed and is the strongest calibration candidate. |
| EPS decline partially masked by neutral growth signal | XOM (EPS −43.4% → Growth: Neutral), PFE (EPS −10.1% → Growth: Neutral) | Growth signal logic in fundamentals_analysis.py | **Weak** — two cases, directionally consistent | The growth signal is neutral when revenue and earnings point in opposite directions. A very large EPS decline (XOM: −43.4%) produces the same neutral signal as a mild one (PFE: −10.1%). A graduated response to the magnitude of the divergence is a potential future enhancement, but no change is warranted without broader evidence. |
| High fundamental score does not guarantee high composite | MSFT (fund 95.0 → composite 66.2), MCD (fund 82.5 → composite 50.8) | Composite weighting | **Moderate** — two clear cases | The fundamental weight (25%) is intentionally lower than technical (35%). A nearly-perfect fundamental score can still result in a mid-range composite when technicals are weak. This is working as designed but is the most likely area to revisit if future calibration finds that fundamental strength is systematically underweighted. |
| KO high rank explained by multi-category alignment | KO (tech 97.5, fund 87.5, risk 75.0) | All categories | **Moderate** | KO's top score is not a weighting artifact — it scores well in every sub-category. The first-pass concern that consumer staples may be overweighted is not supported by the individual report: KO's signals are genuinely strong across the board at this point in time. |
| MCD Hold despite strong fundamentals is technically driven | MCD (fund 82.5, but tech 22.5 → composite 50.8) | Technical weight vs total picture | **Moderate** | MCD's Hold rating reflects a full technical downtrend (below all three SMAs) at the time of the run. The model is internally consistent. Whether the Hold is an appropriate representation depends on how much weight a reviewer places on the technical setup versus the business fundamentals — a calibration question, not a bug. |
| MSFT and PFE composite similarity despite very different sub-scores | MSFT (66.2), PFE (65.0) | Composite weighting formula | **Weak** — one coincidence | MSFT has much stronger fundamentals (95.0 vs 72.5) but weaker technicals (52.5 vs 70.0) and news (57.5 vs 47.5). The trade-offs nearly cancel out in the composite formula. This is the formula working correctly, not a miscalibration. |

---

### Confidence Pattern — Additional Detail

All five tickers received Medium confidence despite a range of signal compositions. The root cause is structural: with 20 signals, the average confidence is always pulled toward the center by the large number of neutral signals (confidence 0.30–0.55) and the moderate confidence attached to most bullish/bearish signals (0.60–0.70).

For KO — the clearest case — the average confidence across 20 signals is approximately:
- 14 bullish signals with confidence ~0.62 (weighted average of 0.60–0.70 across signal types)
- 6 neutral signals with confidence ~0.40 (news signals: 0.40–0.70; volume: 0.45; RSI neutral: 0.50)
- Estimated weighted average: ~0.57 → Medium (threshold for High is ≥0.70)

KO would need all 20 signals to average ≥0.70 confidence to reach High. With 6 neutral signals capped at 0.30–0.50, that is structurally difficult to achieve. This means the confidence level is unlikely to reach High for most real tickers under the current signal design — a genuine calibration gap worth scoping as a future task.

**The confidence calculation is not broken.** It is producing expected values for the current signal confidence assignments. But the practical effect is that confidence adds no information to the output because it is always Medium.

---

### Decision

**No scoring code changes should be made yet.**

The individual reports confirm:

1. **KO's high rank is internally consistent.** The score is driven by genuine multi-category strength, not a weighting artifact.

2. **MCD's Hold is entirely technical.** The full SMA downtrend suppresses the composite despite strong fundamentals. Internally consistent.

3. **MSFT's Watchlist despite exceptional fundamentals is explained** by the SMA 200 bearish signal (strong, −0.25 impact) and MACD bearish, which together hold the technical score at 52.5. The 35%/25% weighting ratio between technical and fundamental is the structural factor. No change warranted without more evidence.

4. **PFE's Watchlist is plausible.** The very low fwd PE is correctly read as attractive under current rules. The EPS/PE interaction does not expose a bug — it exposes a known limitation of isolated rule-based signals.

5. **XOM's Watchlist is explained by technical weakness.** The -43.4% EPS decline producing a neutral (not bearish) growth signal is the most notable model behavior. Worth flagging as a future calibration candidate, but weak evidence.

6. **Confidence compression is the strongest calibration candidate identified to date.** All five tickers returned Medium confidence despite materially different signal compositions. This is a structural outcome of the current signal confidence assignments and the 0.70 threshold for High. This should become **the first candidate for a future scoped calibration task** — specifically: review signal-level confidence assignments and/or the High confidence threshold to determine whether Medium can differentiate.

**Category thresholds and scoring weights should not be changed yet.**

The next step is to collect more individual ticker reports, fill in the calibration worksheet, and accumulate enough cases to determine whether the technical/fundamental weighting ratio warrants adjustment.
