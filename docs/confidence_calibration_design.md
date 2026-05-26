# Confidence Calibration Design

## Purpose

This document defines the observed confidence output problem, summarizes the
evidence collected during calibration, outlines possible future fixes, and
establishes a decision gate that must be cleared before any code change is made.

**Scope:** The `confidence_level` field in scoring output only. The composite
score, category thresholds, and signal `score_impact` values are outside scope.

**Constraint:** No Python code should change as a result of this document. This
is a design and evidence record only.

**Not financial advice.** This document does not recommend buying or selling any
security.

---

## Current Behavior

Confidence is computed in `app/analysis/scoring.py` by `_map_confidence()`:

```python
def _map_confidence(signals: list[Signal]) -> ConfidenceLevel:
    avg = sum(s.confidence for s in signals) / len(signals)
    if avg >= 0.70:
        return ConfidenceLevel.HIGH
    if avg >= 0.45:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW
```

Each `Signal` carries a `confidence` value between 0.0 and 1.0 assigned at
signal-creation time inside the four analysis modules. The function averages all
signal confidences across the full set (~20 signals per ticker) and maps the
result to one of three levels:

| Level  | Threshold       |
|--------|-----------------|
| HIGH   | average ≥ 0.70  |
| MEDIUM | average ≥ 0.45  |
| LOW    | average < 0.45  |

The `confidence_level` field appears in the terminal output, the Markdown report,
the JSON export, and the watchlist summary table. It is intended to give reviewers
a quick signal about how much of the score is backed by complete data versus
fallback neutral signals.

---

## Evidence From Calibration

All calibration runs were conducted on 2026-05-26. No ticker in any run returned
HIGH or LOW confidence.

### Watchlist Runs (14 tickers each)

| Run | Tickers | HIGH | MEDIUM | LOW | Score Range |
|-----|---------|------|--------|-----|-------------|
| First pass (~05:39 UTC) | 14 | 0 | 14 | 0 | 50.8 – 77.5 |
| Second pass (~19:53 UTC) | 14 | 0 | 14 | 0 | 50.8 – 79.8 |

### Individual Ticker Runs

| Ticker | Composite | Bullish Signals | Bearish Signals | Neutral Signals | Est. Avg Confidence | Confidence Level |
|--------|-----------|-----------------|-----------------|-----------------|---------------------|-----------------|
| KO | 79.8 | 14 | 0 | 6 | ~0.57 | Medium |
| MSFT | 66.2 | ~11 | ~4 | ~5 | ~0.56 | Medium |
| PFE | 65.0 | ~10 | ~2 | ~8 | ~0.54 | Medium |
| XOM | 59.5 | ~9 | ~4 | ~7 | ~0.53 | Medium |
| MCD | 50.8 | ~8 | ~4 | ~8 | ~0.52 | Medium |

Signal counts are approximate — derived from sub-scores and signal descriptions
in the Markdown reports. Estimated average confidence values are computed from
typical per-signal confidence ranges: bullish/bearish signals ~0.60–0.70,
neutral signals ~0.30–0.55.

**Across all 19 tickers reviewed in this calibration phase, zero returned HIGH
confidence and zero returned LOW confidence.**

---

## Problem Statement

The confidence output is structurally compressed into the MEDIUM band for all
real tickers under normal market conditions.

**Root cause:** A full signal set contains approximately 20 signals. The HIGH
threshold requires an average confidence of ≥ 0.70 across all 20. Most signal
types assign confidence in the 0.60–0.70 range for bullish/bearish signals and
0.30–0.55 for neutral signals. When a ticker has any neutral signals — which
every ticker does, because at minimum the three news signals and the RSI neutral
case are commonly neutral — the population average is pulled below 0.70.

**KO is the clearest illustration.** KO had 14 bullish signals and zero bearish
signals — the strongest signal composition of any ticker reviewed. Its estimated
average confidence is ~0.57. It would need all 20 signals to average ≥ 0.70 to
reach HIGH. Because six signals have individual confidence values in the 0.30–0.50
range, that is structurally impossible under the current assignments.

**Practical consequence:** The confidence field adds no information to the output.
Every ticker gets the same label regardless of signal strength, score, or data
completeness. A ticker with 14 bullish and 0 bearish signals reads identically to
one with 8 bullish and 4 bearish signals.

**This is not a bug.** The formula is producing expected values given the current
signal confidence assignments. But the practical effect is that one of the three
output fields specifically designed to communicate reliability has no variance.

---

## Possible Future Fixes

### Option A — Lower the HIGH threshold

Change the HIGH threshold from ≥ 0.70 to a lower value such as ≥ 0.60 or ≥ 0.62.

**What changes:** One line in `_map_confidence()` in `app/analysis/scoring.py`.

**Effect:** Tickers with strong bullish signal compositions (fewer neutral signals,
higher average) could reach HIGH. KO at ~0.57 estimated average would require the
threshold to be ≤ 0.57 to benefit — a more aggressive reduction than ≥ 0.60 would
provide without first auditing actual signal confidence values.

**Risk:** LOW — confidence level does not affect the composite score or category.
Only the explanatory label changes.

**Drawback:** A threshold change without first auditing actual signal confidence
values is guesswork. The right threshold depends on the distribution of averages
across many tickers, which is not yet known precisely. A poorly chosen threshold
could still produce all-MEDIUM output or flip to all-HIGH.

---

### Option B — Increase signal-level confidence assignments in analysis modules

Raise the confidence values attached to bullish and/or bearish signals in one or
more of the four analysis modules (`technicals.py`, `fundamentals_analysis.py`,
`news_analysis.py`, `risk_analysis.py`).

**What changes:** Multiple `Signal(confidence=...)` call sites across up to four
modules. The `_map_confidence()` threshold can stay at 0.70.

**Effect:** If bullish signal confidence is raised from ~0.65 to ~0.75 and neutral
signal confidence is raised from ~0.40 to ~0.50, the population average for
strongly bullish tickers like KO would rise enough to cross 0.70 and reach HIGH.

**Risk:** MEDIUM — touches multiple modules. Changes must be reviewed one module
at a time to avoid unintended effects. Confidence values are not currently used in
any other computation, but this should be verified before changing.

**Drawback:** Requires auditing all four modules to inventory current confidence
assignments before proposing new values. Cannot be done responsibly without that
inventory. Changes that raise confidence across the board would move all tickers
toward MEDIUM/HIGH without improving differentiation.

---

### Option C — Replace fixed-average with a distribution-aware calculation

Replace the simple average with a calculation that gives more weight to the signal
direction mix, such as: fraction of bullish signals, ratio of bullish-to-total
(excluding neutral), or a weighted average that uses score_impact magnitude.

**Example (illustrative only):**
```python
# Not proposed for implementation — illustrative only
bullish_count = sum(1 for s in signals if s.direction == Direction.BULLISH)
bearish_count = sum(1 for s in signals if s.direction == Direction.BEARISH)
neutral_count  = sum(1 for s in signals if s.direction == Direction.NEUTRAL)
ratio = bullish_count / len(signals)
# Map ratio to confidence level
```

**Effect:** Could differentiate KO (14/20 bullish = 70%) from MCD (8/20 = 40%)
in a way the current average cannot, since the current formula treats a bullish
signal at confidence 0.62 nearly identically to a neutral signal at confidence 0.55.

**Risk:** HIGH — architectural change to the confidence formula. Changes the
semantic meaning of `ConfidenceLevel` from "average data quality" to "signal
alignment." Would require careful definition of what confidence is supposed to
mean, and regression tests for the new formula.

**Drawback:** This changes what confidence means, not just its calibration. That
semantic change should be evaluated separately from calibration tuning.

---

### Option D — Add an explanation field, make no formula change

Keep the formula exactly as-is. Add a separate output field or text annotation
in the report that explains the confidence level — for example: "Medium (typical
for a 20-signal set; not driven by data gaps)."

**What changes:** Report templates and/or the `Rating` model, not scoring logic.

**Effect:** Does not fix the variance problem — confidence still shows Medium for
every ticker. But gives the reviewer context about what the label means rather
than implying it distinguishes between tickers when it currently does not.

**Risk:** LOWEST — no scoring or analysis code changes.

**Drawback:** Does not actually fix the problem. Addresses symptom (confusion)
without addressing cause (no variance). Acceptable as a short-term interim step,
not as a final resolution.

---

## Recommended Next Step

**Audit signal-level confidence assignments before choosing between options.**

Before selecting Option A, B, C, or D, build an inventory of what confidence
value each signal type actually assigns today. This means reading all four
analysis modules and recording every `Signal(confidence=...)` call site:

- Which signal name / direction assigns what confidence value?
- Are any signal types using confidence to proxy data quality vs. strength?
- What is the expected average for a ticker with all strong bullish signals,
  zero neutral signals, and no data gaps?

This audit requires no code changes. It produces a table of current values that
makes Option A's correct threshold and Option B's required per-signal adjustments
concrete rather than guessed.

**This audit is the one task that should be completed before any code change.**
The finding will determine whether Option A (simpler) or Option B (more precise)
is the right vehicle, and will provide the specific numbers needed.

**Why not Option C or D now?**
Option C changes the meaning of confidence — that decision should come after the
simpler options are evaluated and found insufficient. Option D is a fallback only
if the audit reveals that the formula cannot be fixed without a semantic change.

---

## Decision Gate Before Code Changes

No code change to the confidence calculation should be made until all of the
following are true:

1. **The signal confidence inventory is complete.** Every `Signal(confidence=...)`
   call site in all four analysis modules is documented with its value and the
   rationale for that value.

2. **The expected average for a strongly bullish ticker is computed.** Using the
   inventory, calculate the expected `_map_confidence` output for a hypothetical
   ticker with zero data gaps, all bullish signals, and realistic individual
   confidence values. If that expected value is below 0.70, Option A or B is
   needed. If it is already above 0.70 and real tickers still never reach HIGH,
   the cause is neutral signals pulling the average down — that is a different
   fix.

3. **A specific proposed value is stated with a rationale.** "Lower the threshold
   to 0.62 because the expected all-bullish average is 0.64" is an acceptable
   proposal. "Lower it to something around 0.60" is not.

4. **At least one failing case and one passing case are stated.** The proposal
   should name at least one ticker that should reach HIGH under the new logic and
   one that should stay MEDIUM, with the expected average for each derived from
   the inventory.

5. **A regression test is specified.** Before the code change, identify which
   existing test file(s) cover `_map_confidence` and what new assertion(s)
   would be added to pin the updated behavior.

**No weight, threshold, or signal confidence value should change without all five
gates above being cleared.**

---

*See also:*
- `docs/signal_confidence_audit.md` — complete signal-level confidence inventory,
  mathematical proof that HIGH is unreachable, and specific fix targets
- `docs/scoring_calibration_plan.md` — calibration process and decision framework
- `docs/calibration_review_notes.md` — evidence from all calibration runs to date
- `docs/scoring_rules.md` — authoritative reference for scoring weights and thresholds
