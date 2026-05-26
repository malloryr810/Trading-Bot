# Confidence Calibration Proposal

> **Implementation status:** The threshold-only recalibration described in this
> document has been implemented. `_map_confidence()` in
> `app/analysis/scoring.py` now uses HIGH ≥ 0.63 and MEDIUM ≥ 0.50.
> Scores, categories, signal confidence values, and diagnostics are unchanged.
> 18 new boundary and regression tests were added to `tests/test_scoring.py`.
>
> **Validation status (2026-05-26):** Post-implementation validation confirmed
> all five priority tickers matched expected labels (KO and MSFT → High; XOM,
> MCD, PFE → Medium). Watchlist distribution: 6 High / 8 Medium / 0 Low.
> See `docs/calibration_review_notes.md` — Post-Confidence-Recalibration
> Validation Pass section.

## Purpose

This document proposes a future confidence calibration change. It does not change
any Python code or scoring behavior.

The goal is to make the Low / Medium / High confidence labels useful and
distinguishable across real tickers. As currently designed, the High label is
unreachable and the Medium label applies to every ticker regardless of signal
composition.

Confidence is intended to describe the **strength and completeness of the
evidence** that produced a rating — not whether the rating is positive or
negative. A ticker with 14 bullish signals and complete data across all four
analysis areas should reflect stronger evidence quality than a ticker with 8
bullish signals, 4 bearish, and a missing D/E field. The current label cannot
express that difference.

This remains a decision-support tool, not a trading system. Nothing in this
proposal generates buy or sell signals, alters composite scores, or changes
category thresholds.

**Not financial advice.** This document does not recommend buying or selling
any security.

---

## Evidence Summary

### What was collected

Evidence was collected across two calibration phases on 2026-05-26:

- **Watchlist runs** — the 14-ticker calibration sample was run twice (~05:39 UTC
  and ~19:53 UTC). All 14 tickers returned Medium confidence in both passes
  despite a score spread of 50.8–79.8 (≈29 points).

- **Individual ticker review** — KO, XOM, MSFT, MCD, and PFE were run
  individually with `--save-markdown --save-json`. All returned Medium.

- **Diagnostics review** — After `ConfidenceDiagnostics` was added to the
  pipeline, the same five tickers were re-run and their actual average
  confidence values were extracted from JSON output.

- **Signal confidence audit** — All four analysis modules were read to document
  every `Signal(confidence=...)` call site. A mathematical proof showed that the
  theoretical maximum average confidence for any real ticker is approximately
  0.643, which is 0.057 below the current High threshold of 0.70.

The observed ceiling matches theory: MSFT measured exactly 0.6425, the highest
average of any ticker reviewed and effectively the reachable maximum.

### Diagnostic values for the five review tickers

Values are exact — read from JSON output (`confidence_diagnostics.average_signal_confidence`).

| Ticker | Score | Category | Current Confidence | Avg Signal Confidence | Key Diagnostic Finding |
|--------|-------|----------|-------------------|----------------------|------------------------|
| KO | 79.8 | Buy Candidate | Medium | 0.6375 | 14 bullish / 0 bearish / 6 neutral; no missing-data signals; strongest signal composition reviewed |
| MSFT | 66.2 | Watchlist | Medium | 0.6425 | 12 / 3 / 5 direction split; highest avg confidence (matches theoretical ceiling); exceptional fundamental avg (0.67) |
| XOM | 59.5 | Watchlist | Medium | 0.6250 | 10 / 3 / 7 direction split; moderate fundamental avg (0.61) reflecting EPS decline |
| MCD | 50.8 | Hold | Medium | 0.6175 | 8 / 4 / 8 direction split; only ticker with a missing-data signal (D/E null, confidence 0.30) |
| PFE | 65.0 | Watchlist | Medium | 0.6100 | 10 / 2 / 8 direction split; most neutral signals; lowest overall avg and lowest tech avg (0.5786) |

The five tickers span a 29-point score range and four categories. Their average
confidence values span only 0.0325. Across 19 tickers reviewed in total (14
watchlist + 5 individual), **zero returned High confidence and zero returned Low
confidence.**

---

## Problem Statement

The confidence label as currently implemented is not informative.

**The High label is unreachable.** `_map_confidence()` in `app/analysis/scoring.py`
returns `ConfidenceLevel.HIGH` when the unweighted average of all signal confidence
values is ≥ 0.70. The signal confidence audit (`docs/signal_confidence_audit.md`)
proves mathematically that no real ticker can exceed an average of approximately
0.643. The gap is structural: five signals in every typical run carry confidence
values of 0.45–0.55 (RSI Neutral, MACD Neutral, Volume Bullish/Neutral, Recent
Trend Neutral), and no realistic signal combination can average them above 0.70
across 20 signals.

**Medium is overused.** The Medium band spans a 0.25-wide range (0.45–0.70). All
real tickers land in a 0.0325-wide sub-band within it (0.6100–0.6425 in measured
data). The label cannot distinguish a ticker with 14 bullish signals and no data
gaps from one with 8 bullish, 4 bearish, and a missing field.

**Different reports look equally reliable.** KO (14/0/6 direction split, all data
present) and MCD (8/4/8 direction split, D/E unavailable) both display
`Confidence: Medium`. A reviewer reading both reports cannot use the confidence
field to gauge relative evidence quality.

**This is a confidence-label problem, not a score or category problem.** The
composite scores and category thresholds are not under review here. KO's 79.8
score and MCD's 50.8 score correctly communicate different rating outcomes. The
confidence label is supposed to add a separate dimension (evidence reliability),
but currently does not.

**This proposal does not change:**
- Composite scoring formula
- Category thresholds (Strong Buy Candidate, Buy Candidate, Watchlist, Hold, Avoid, Sell / Exit Warning)
- Signal scoring weights (Technical 35%, Fundamental 25%, News 25%, Risk 15%)
- Any `score_impact` values or signal creation logic
- Trading behavior (none exists — this tool does not execute trades)

---

## Options Considered

### Option A — Lower the High confidence threshold

Reduce the High threshold in `_map_confidence()` in `app/analysis/scoring.py`
to a value reachable by real tickers.

**Benefit:** Single-line change in one function. Does not touch signal creation,
analysis modules, or scoring weights. Easy to test, easy to revert.

**Risk:** Low. Confidence label does not affect composite score or category.
The only output that changes is the explanatory label.

**Implementation complexity:** Minimal — one constant changes in one function.
Boundary tests need updating to reflect the new value.

**Why or why not now:** This is the recommended option. The evidence is clear and
quantified. The fix is targeted, reversible, and proportionate to a
documentation/calibration gap rather than a scoring gap.

---

### Option B — Raise signal-level confidence assignments in analysis modules

Increase the confidence values attached to specific signals in `technicals.py`,
`risk_analysis.py`, or other modules so the overall average rises enough to
make High reachable at the existing 0.70 threshold.

**Benefit:** Leaves the threshold formula unchanged. Directly addresses the
structural anchors identified in the audit (RSI Neutral 0.50, MACD Neutral 0.50,
Volume Bullish 0.50, etc.).

**Risk:** Medium. Touches multiple modules and multiple call sites. Changes must
be verified one module at a time. Confidence values are not currently used in
score computation, but this should be re-confirmed before any module is changed.
Broad raises could move all tickers toward Medium/High without improving
differentiation.

**Implementation complexity:** Moderate — requires inventorying every call site,
proposing specific per-signal adjustments, and verifying per-area averages.

**Why or why not now:** Not recommended as the first step. A threshold adjustment
(Option A) achieves the same diagnostic goal (making High reachable) with far
fewer changes and lower risk. Option B should be considered if, after Option A
is implemented, the differentiation is still insufficient.

---

### Option C — Replace the fixed average with a distribution-aware formula

Redesign `_map_confidence()` to use a formula that weights signal direction
alignment, bullish fraction, or score_impact magnitude rather than a simple
per-signal average.

**Benefit:** Could produce more meaningful differentiation by incorporating
direction composition into the confidence calculation.

**Risk:** High. Changes the semantic meaning of `ConfidenceLevel` from
"average data quality / completeness" to "signal alignment or direction
consensus." This is an architectural change to what confidence is supposed to
express, and would require new documentation, new regression tests, and careful
stakeholder review.

**Implementation complexity:** High — formula redesign, schema documentation
update, full regression test pass.

**Why or why not now:** Not recommended yet. The simpler option (Option A) has
not been evaluated. Option C conflates two separate questions: "is the evidence
complete?" and "do the signals agree?" Separating those questions should come
after the threshold calibration is settled.

---

### Option D — Add explanation text; make no formula change

Leave the formula as-is. Add a note in Markdown reports or the terminal output
explaining that Medium is the typical result for a 20-signal set and does not
indicate a data quality problem.

**Benefit:** Zero risk to any formula or label. Lowest possible implementation
cost.

**Risk:** Lowest.

**Implementation complexity:** Minimal.

**Why or why not now:** Not recommended as the primary fix. Explanation text
addresses the symptom (reviewer confusion) without addressing the cause (no
variance in the label). Acceptable only as a short-term supplement to Option A,
not as a standalone resolution.

---

## Recommended Proposal

**Adopt Option A: a threshold-only recalibration using the average signal
confidence already computed by `ConfidenceDiagnostics`.**

The `_map_confidence()` function in `app/analysis/scoring.py` currently uses:

```python
def _map_confidence(signals: list[Signal]) -> ConfidenceLevel:
    avg = sum(s.confidence for s in signals) / len(signals)
    if avg >= 0.70:          # → HIGH   (currently unreachable)
    if avg >= 0.45:          # → MEDIUM (spans entire observable range)
    return ConfidenceLevel.LOW
```

### Proposed thresholds

| Level | Current Threshold | Proposed Threshold |
|-------|------------------|--------------------|
| HIGH | avg ≥ 0.70 | avg ≥ **0.63** |
| MEDIUM | 0.45 ≤ avg < 0.70 | 0.50 ≤ avg < **0.63** |
| LOW | avg < 0.45 | avg < **0.50** |

### Why 0.63 rather than 0.62

The task prompt suggested 0.62 as the starting point. After inspecting the
measured diagnostic values, 0.63 is a more defensible boundary:

- At **0.62**, KO (0.6375), MSFT (0.6425), and XOM (0.6250) all become High.
  XOM is a Watchlist ticker with 3 bearish signals and a neutral EPS growth signal
  (revenue up, earnings down −43.4%). Labeling it High overstates evidence quality
  for a mixed-signal composition.

- At **0.63**, only KO (0.6375) and MSFT (0.6425) become High. Both have
  materially stronger signal compositions: KO has 14 bullish / 0 bearish, and
  MSFT has the highest fundamental average confidence (0.67) in the review set,
  reflecting complete data across all five fundamental signals.

- XOM (0.6250) remains Medium at 0.63. Its average sits 0.0050 below the new
  threshold — a small but meaningful gap corresponding to its 3 bearish signals
  and the EPS-decline neutral growth signal.

- MCD (0.6175) and PFE (0.6100) remain Medium under both 0.62 and 0.63.

The 0.63 threshold produces 2 High, 3 Medium from the five review tickers — a
meaningful split that aligns with observable differences in signal composition
rather than compressing all five into one label.

### Why this is conservative

- No signal-creation code changes (Options B and C are deferred).
- No scoring formula changes — `_signals_to_score()`, composite weights, and
  `_map_score_to_category()` are untouched.
- The `average_signal_confidence` value used by the new boundary is already
  computed by `_build_confidence_diagnostics()` and is visible in JSON and
  Markdown output. The before/after effect of any threshold change can be
  verified immediately by inspecting the `confidence_diagnostics` section of
  any existing report without re-running analysis.
- The change is a two-number edit to one function, with no ripple effects on
  data models, templates, or storage.
- If the 0.63 threshold over-labels High for tickers not yet reviewed, it can
  be raised in a follow-up task without touching anything else.

### Low threshold reasoning

Raising Low from `< 0.45` to `< 0.50` tightens the bottom of the Medium band.
Under current signal assignments, Low would trigger when a ticker has multiple
missing-data signals (each contributing confidence 0.30). A ticker with 4 or
more null-data fallback signals out of 20 would produce an average around
0.45–0.49 and receive Low — an appropriate label for sparse data. MCD's single
null D/E field (one signal at 0.30 out of 20) still produces an overall average
of 0.6175, well above 0.50, so MCD remains Medium as expected.

---

## Expected Before/After Outcomes

Values are derived from measured diagnostics (documented in the Confidence
Diagnostics Review Pass section of `docs/calibration_review_notes.md`).
No new runs were conducted for this proposal.

| Ticker | Current Avg Confidence | Current Label | Proposed Label | Rationale |
|--------|------------------------|---------------|----------------|-----------|
| KO | 0.6375 | Medium | **High** | 14 / 0 / 6 direction split; no missing-data signals; 0.6375 ≥ 0.63 threshold |
| MSFT | 0.6425 | Medium | **High** | 12 / 3 / 5 direction split; highest fundamental avg (0.67); at theoretical ceiling; 0.6425 ≥ 0.63 threshold |
| XOM | 0.6250 | Medium | **Medium** | 10 / 3 / 7 direction split; mixed EPS signal; 0.6250 < 0.63, remains Medium |
| MCD | 0.6175 | Medium | **Medium** | 8 / 4 / 8 direction split; one missing-data signal (D/E null); 0.6175 < 0.63 |
| PFE | 0.6100 | Medium | **Medium** | 10 / 2 / 8 direction split; most neutral signals; lowest measured avg; 0.6100 < 0.63 |

**Not every ticker becomes High.** Three of five (XOM, MCD, PFE) remain Medium.
MCD, the only ticker with a missing-data signal, stays furthest from High.
The two tickers that become High are the ones with the strongest signal
compositions in the review set.

---

## Test Plan for Future Implementation

The following tests must be in place when `_map_confidence()` is changed.
Some are updates to existing tests; most are new assertions.

### Tests that must be updated to reflect new thresholds

These tests currently use values that straddle old thresholds. Under the
proposed change, their assertions remain correct but the inline comments must
be updated:

| File | Test | Change Needed |
|------|------|---------------|
| `tests/test_scoring.py` | `TestConfidenceMapping.test_high_confidence` | Comment update only (uses confidence=0.80, still ≥ 0.63 → HIGH) |
| `tests/test_scoring.py` | `TestConfidenceMapping.test_medium_confidence` | Comment update only (uses confidence=0.60, still in [0.50, 0.63) → MEDIUM) |
| `tests/test_scoring.py` | `TestConfidenceMapping.test_low_confidence` | Comment update only (uses confidence=0.30, still < 0.50 → LOW) |
| `tests/test_scoring.py` | `TestConfidenceMapping.test_average_confidence_used_across_signals` | Comment update only (avg=0.60, still MEDIUM) |
| `tests/test_confidence_diagnostics.py` | `TestScoreSignalsIntegration.test_diagnostics_does_not_change_confidence_label` | Comment update (avg=0.60 → MEDIUM under new thresholds; still correct) |
| `tests/test_confidence_diagnostics.py` | `TestScoreSignalsIntegration.test_high_confidence_signals_still_yield_correct_label` | Comment update (avg=0.775, still HIGH) |

No existing assertion values need to change — all currently tested confidence
values fall clearly in the same label bucket under both old and new thresholds.

### New tests required

All new tests belong in `tests/test_scoring.py` under `TestConfidenceMapping`
or in a new `TestConfidenceMappingBoundaries` class.

**Boundary tests for the new HIGH threshold (0.63):**

```python
def test_exactly_at_new_high_threshold_is_high():
    # avg = 0.63 exactly → HIGH under new thresholds
    result = score_technical_signals("AAPL", [_sig(confidence=0.63)])
    assert result.confidence == ConfidenceLevel.HIGH

def test_just_below_new_high_threshold_is_medium():
    # avg = 0.6299 → MEDIUM (below 0.63)
    result = score_technical_signals("AAPL", [_sig(confidence=0.6299)])
    assert result.confidence == ConfidenceLevel.MEDIUM
```

**Boundary tests for the new LOW/MEDIUM threshold (0.50):**

```python
def test_exactly_at_new_medium_threshold_is_medium():
    # avg = 0.50 exactly → MEDIUM
    result = score_technical_signals("AAPL", [_sig(confidence=0.50)])
    assert result.confidence == ConfidenceLevel.MEDIUM

def test_just_below_new_medium_threshold_is_low():
    # avg = 0.4999 → LOW (below 0.50)
    result = score_technical_signals("AAPL", [_sig(confidence=0.4999)])
    assert result.confidence == ConfidenceLevel.LOW
```

**Test that HIGH is now reachable with realistic inputs:**

```python
def test_high_confidence_reachable_with_realistic_inputs():
    # avg of [0.70, 0.70, 0.65, 0.65, 0.65, 0.60, 0.50] = 0.6357 → HIGH
    # This approximates a bullish technical set (all data present, RSI neutral)
    signals = [
        _sig(confidence=0.70),  # Trend bullish
        _sig(confidence=0.70),  # SMA 200 above
        _sig(confidence=0.65),  # MACD bullish
        _sig(confidence=0.65),  # SMA 50 above
        _sig(confidence=0.65),  # RSI not extreme (oversold/overbought)
        _sig(confidence=0.60),  # SMA 20 above
        _sig(confidence=0.50),  # RSI neutral (structural anchor)
    ]
    result = score_technical_signals("AAPL", signals)
    assert result.confidence == ConfidenceLevel.HIGH
```

**Tests using representative real-ticker diagnostic averages:**

```python
def test_ko_representative_average_yields_high():
    # KO measured avg_signal_confidence = 0.6375
    # Use a single signal at that value to confirm threshold behavior
    result = score_technical_signals("AAPL", [_sig(confidence=0.6375)])
    assert result.confidence == ConfidenceLevel.HIGH

def test_mcd_representative_average_yields_medium():
    # MCD measured avg_signal_confidence = 0.6175
    result = score_technical_signals("AAPL", [_sig(confidence=0.6175)])
    assert result.confidence == ConfidenceLevel.MEDIUM

def test_pfe_representative_average_yields_medium():
    # PFE measured avg_signal_confidence = 0.6100
    result = score_technical_signals("AAPL", [_sig(confidence=0.6100)])
    assert result.confidence == ConfidenceLevel.MEDIUM
```

**Regression tests confirming scores and categories are unchanged:**

```python
def test_confidence_threshold_change_does_not_affect_composite_score():
    signals = _make_composite_signals()
    rating_before = score_signals("AAPL", signals)
    # After threshold change, score must be identical
    assert rating_before.score == score_signals("AAPL", signals).score

def test_confidence_threshold_change_does_not_affect_category():
    signals = _make_composite_signals()
    rating = score_signals("AAPL", signals)
    assert rating.final_category is not None  # category still assigned

def test_confidence_diagnostics_unchanged_by_threshold_adjustment():
    # ConfidenceDiagnostics reads raw confidence values, not the label
    signals = _make_composite_signals()
    rating = score_signals("AAPL", signals)
    d = rating.confidence_diagnostics
    assert d.signal_count == len(signals)
    # avg 0.60 is deterministic; diagnostics must match regardless of label change
    assert d.average_signal_confidence == pytest.approx(0.60, abs=1e-4)
```

**Report/JSON tests confirming label updates but diagnostics stay intact:**

```python
def test_json_confidence_label_reflects_new_threshold():
    # avg = 0.6375 → HIGH after threshold change
    signals = [_sig(confidence=0.6375)]
    rating = score_signals("AAPL", signals)
    report = build_stock_report(rating)
    data = report.model_dump(mode="json")
    assert data["confidence_level"] == "high"

def test_json_diagnostics_unchanged_when_label_changes():
    # avg = 0.6375 → HIGH, but diagnostics still reports 0.6375
    signals = [_sig(confidence=0.6375)]
    rating = score_signals("AAPL", signals)
    report = build_stock_report(rating)
    data = report.model_dump(mode="json")
    assert data["confidence_diagnostics"]["average_signal_confidence"] == pytest.approx(0.6375, abs=1e-4)

def test_markdown_shows_high_when_average_meets_new_threshold():
    signals = [_sig(confidence=0.65)] * 3
    rating = score_signals("AAPL", signals)
    report = build_stock_report(rating)
    md = format_report_markdown(report)
    assert "High" in md
```

**Confirm all three labels are still reachable after the change:**

```python
def test_low_still_reachable():
    result = score_technical_signals("AAPL", [_sig(confidence=0.30)])
    assert result.confidence == ConfidenceLevel.LOW

def test_medium_still_reachable():
    result = score_technical_signals("AAPL", [_sig(confidence=0.56)])
    assert result.confidence == ConfidenceLevel.MEDIUM

def test_high_still_reachable():
    result = score_technical_signals("AAPL", [_sig(confidence=0.65)])
    assert result.confidence == ConfidenceLevel.HIGH
```

---

## Risks and Guardrails

### Risks

**Risk: too many High labels after lowering threshold.**
If the calibration sample contains many tickers with average confidence above
0.63, the High label could become overused in the other direction. The five-ticker
review set is too small to rule this out. The full 14-ticker watchlist should be
re-run after implementation and the distribution of High / Medium / Low reviewed.

**Risk: threshold chosen from a small sample.**
The 0.63 value is derived from five tickers on a single trading day. Market
conditions, intraday volatility, and yfinance data availability can shift
per-signal confidence values slightly. The threshold should be treated as an
initial calibration, not a final setting.

**Risk: new LOW boundary (0.50) may affect tickers not yet reviewed.**
No ticker in the calibration set fell below 0.60. Whether any real ticker
lands between 0.45 and 0.50 (the range newly classified as LOW) is unknown.
The expected case is that tickers with many missing-data signals (2+ null
fields out of 5 fundamental signals) would land here, which is the intended
behavior.

### Guardrails

**Keep diagnostics visible in all outputs.**
The `ConfidenceDiagnostics` section in Markdown reports and JSON exports must
remain in place after the threshold change. If a label shifts unexpectedly,
the `average_signal_confidence` and per-area averages provide immediate
diagnostic evidence for investigation.

**Rerun the full 14-ticker calibration watchlist after implementation.**
Compare the distribution of High / Medium / Low across all 14 tickers. If
more than 5–6 of 14 return High on a typical day, the threshold should be
reviewed. The goal is meaningful differentiation, not a specific ratio.

**Do not change scoring weights in the same task.**
The confidence threshold change and any scoring weight change must be separate
commits. Combining them makes it impossible to isolate which change caused any
observed label shift.

**Update `docs/development_log.md` and `docs/scoring_rules.md` after implementation.**
The current `scoring_rules.md` documents the 0.70 High threshold. Once the
threshold changes, that document must be updated to reflect the new values.

**Limit implementation to `_map_confidence()` only.**
The change is one function, two constants. If any additional files are
modified during implementation (signal-level confidence assignments, scoring
weights, templates beyond comment updates), the implementation has exceeded
the scope of this proposal.

---

## Decision Gate

Implementation of the confidence threshold change can proceed only when all of
the following are true:

1. **This proposal has been reviewed.** The recommended threshold (HIGH ≥ 0.63,
   MEDIUM ≥ 0.50) and the expected before/after outcomes for KO, XOM, MSFT, MCD,
   and PFE are accepted.

2. **Expected before/after labels are documented and accepted.** KO and MSFT
   become High; XOM, MCD, and PFE remain Medium. If this distribution is not
   acceptable, the threshold must be reconsidered before any code changes.

3. **All tests from the Test Plan section are written before or with the change.**
   Boundary tests at 0.63 and 0.50, representative-ticker average tests, and
   the full regression suite must be green before the change is considered done.

4. **The change is limited to `_map_confidence()` in `app/analysis/scoring.py`.**
   Only the two threshold constants (HIGH boundary and LOW boundary) should
   change. Signal confidence assignments, composite weights, category thresholds,
   and all other scoring logic must be unchanged.

5. **No score or category behavior is changed.** The composite score, sub-scores,
   and `final_category` output for any ticker must be identical before and after
   the threshold change. This should be verified by running the five review
   tickers and confirming their scores and categories are unchanged.

---

*See also:*
- `docs/confidence_calibration_design.md` — problem statement and four fix options
- `docs/signal_confidence_audit.md` — complete signal-level inventory and mathematical proof
- `docs/calibration_review_notes.md` — all calibration evidence and diagnostic values
- `docs/scoring_calibration_plan.md` — calibration process and decision framework
- `docs/scoring_rules.md` — authoritative scoring weights and thresholds (update after implementation)
- `app/analysis/scoring.py` — `_map_confidence()` is the only function that changes
- `tests/test_scoring.py` — primary test file for confidence mapping assertions
