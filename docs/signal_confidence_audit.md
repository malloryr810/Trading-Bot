# Signal Confidence Audit

## Purpose

This document inventories the signal-level confidence values currently assigned
by each analysis module. It does not change any scoring or confidence logic.

The purpose is to:
1. Identify exactly where confidence values are set in code.
2. Explain how those values flow into the final `ConfidenceLevel` label.
3. Show mathematically why `HIGH` confidence is unreachable under the current
   signal confidence assignments.
4. Support a future scoped confidence calibration task by making the current
   system concrete rather than estimated.

**Confidence describes the reliability or completeness of the analysis that
produced a signal — not whether the ticker looks attractive or unattractive.**
A bullish signal and a bearish signal can have identical confidence values if
both are derived from equally complete data.

**Not financial advice.** This document does not recommend buying or selling
any security.

---

## Current Confidence Flow

### Where confidence values are created

Each signal confidence value is assigned as a literal constant inside the
signal-builder helper functions in the four analysis modules:

- `app/analysis/technicals.py` — functions `_trend_signal`, `_rsi_signal`,
  `_macd_signal`, `_price_vs_sma_signal`, `_volume_signal`
- `app/analysis/fundamentals_analysis.py` — functions `_valuation_signal`,
  `_profitability_signal`, `_growth_signal`, `_debt_signal`, `_cash_flow_signal`
- `app/analysis/news_analysis.py` — functions `_sentiment_signal`,
  `_risk_headline_signal`, `_coverage_signal`; confidence is derived from a
  formula rather than a constant (see below)
- `app/analysis/risk_analysis.py` — functions `_volatility_signal`,
  `_max_drawdown_signal`, `_recent_trend_signal`, `_liquidity_signal`,
  `_beta_signal`; missing-data fallback via `_insufficient_data_signal`

### How confidence is attached to signals

Each analysis module creates `Signal` Pydantic objects (defined in
`app/models/signal.py`). The `Signal` model has a `confidence` field:

```python
# app/models/signal.py
confidence: float = Field(default=0.5, ge=0.0, le=1.0)
```

The analysis modules set this field explicitly in every signal they create.
The default of 0.5 is never relied on in practice — every code path sets a
specific value.

### How final confidence is calculated

After all signals are produced, `score_signals()` in `app/analysis/scoring.py`
calls `_map_confidence(signals)`:

```python
def _map_confidence(signals: list[Signal]) -> ConfidenceLevel:
    avg = sum(s.confidence for s in signals) / len(signals)
    if avg >= 0.70:
        return ConfidenceLevel.HIGH
    if avg >= 0.45:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW
```

This takes a **simple unweighted average** of every signal's `.confidence`
value across all 20 signals (7 technical + 5 fundamental + 3 news + 4–5 risk).
No weighting by category, signal strength, or `score_impact` magnitude is applied.

### Where labels are generated

`_map_confidence()` returns a `ConfidenceLevel` enum:

```python
# app/models/rating.py
class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

This value is stored in the `Rating.confidence` field, then rendered as a string
in templates and JSON output. It appears in the terminal report, the Markdown
report (e.g., `| Confidence | Medium |`), and the watchlist summary table.

### Files and functions involved in the confidence pipeline

| Step | File | Function |
|------|------|----------|
| Technical signal confidence set | `app/analysis/technicals.py` | `_trend_signal`, `_rsi_signal`, `_macd_signal`, `_price_vs_sma_signal`, `_volume_signal` |
| Fundamental signal confidence set | `app/analysis/fundamentals_analysis.py` | `_valuation_signal`, `_profitability_signal`, `_growth_signal`, `_debt_signal`, `_cash_flow_signal` |
| News signal confidence set | `app/analysis/news_analysis.py` | `_sentiment_signal`, `_risk_headline_signal`, `_coverage_signal` |
| Risk signal confidence set | `app/analysis/risk_analysis.py` | `_volatility_signal`, `_max_drawdown_signal`, `_recent_trend_signal`, `_liquidity_signal`, `_beta_signal` |
| Missing-data fallback (risk) | `app/analysis/risk_analysis.py` | `_insufficient_data_signal` |
| Missing-data fallback (news) | `app/analysis/news_analysis.py` | `_no_data_signal` |
| Average computed, label applied | `app/analysis/scoring.py` | `_map_confidence` |
| Label stored in output | `app/models/rating.py` | `Rating.confidence` |

---

## Signal-Level Confidence Inventory

### Technical signals (`app/analysis/technicals.py`)

Seven signals are produced by `build_technical_signals()`.

| Signal | Condition / Direction | Confidence | Notes |
|--------|-----------------------|------------|-------|
| Trend | Bullish (close > SMA20 > SMA50) | 0.70 | Highest in the technical set |
| Trend | Bearish (close < SMA20 < SMA50) | 0.70 | Same value as bullish |
| Trend | Neutral (mixed) | 0.50 | Common when trend is ambiguous |
| RSI Condition | Overbought (RSI > 70) | 0.65 | Bearish direction |
| RSI Condition | Oversold (RSI < 30) | 0.65 | Bullish direction |
| RSI Condition | Neutral (30–70) | 0.50 | **Most common RSI state** |
| MACD Condition | Bullish (MACD > signal line) | 0.65 | |
| MACD Condition | Bearish (MACD < signal line) | 0.65 | Same value as bullish |
| MACD Condition | Neutral (aligned) | 0.50 | |
| Price vs SMA 20 | Above (bullish) | 0.60 | Defined in `_SMA_CONFIGS[20]` |
| Price vs SMA 20 | Below (bearish) | 0.60 | Same value as bullish |
| Price vs SMA 20 | Missing (SMA unavailable) | 0.30 | Missing-data case |
| Price vs SMA 50 | Above (bullish) | 0.65 | Defined in `_SMA_CONFIGS[50]` |
| Price vs SMA 50 | Below (bearish) | 0.65 | Same value as bullish |
| Price vs SMA 50 | Missing | 0.30 | |
| Price vs SMA 200 | Above (bullish) | 0.70 | Highest SMA; `_SMA_CONFIGS[200]` |
| Price vs SMA 200 | Below (bearish) | 0.70 | Same value as bullish |
| Price vs SMA 200 | Missing | 0.30 | |
| Volume vs Vol SMA 20 | Above average (bullish) | 0.50 | **Low even for bullish case** |
| Volume vs Vol SMA 20 | At or below average (neutral) | 0.45 | |
| Volume vs Vol SMA 20 | Missing | 0.30 | |

**Technical summary:** Maximum per-signal confidence in this area is 0.70 (Trend,
SMA 200). The two weakest structural contributors are the Volume signal (0.45–0.50)
and RSI Neutral (0.50) — both of which occur in most bullish tickers.

---

### Fundamental signals (`app/analysis/fundamentals_analysis.py`)

Five signals are produced by `build_fundamental_signals()`.

| Signal | Condition / Direction | Confidence | Notes |
|--------|-----------------------|------------|-------|
| Valuation | P/E unavailable (None) | 0.30 | Missing-data case |
| Valuation | Negative or zero P/E | 0.65 | Bearish |
| Valuation | Very low P/E (< 5) | 0.50 | Neutral — unusual context |
| Valuation | Attractive P/E (5–25) | 0.65 | Bullish |
| Valuation | Elevated P/E (25–40) | 0.60 | Neutral |
| Valuation | High P/E (> 40) | 0.60 | Bearish |
| Profitability | Margin unavailable (None) | 0.30 | Missing-data case |
| Profitability | Strong margin (≥ 15%) | 0.70 | Bullish; highest in fundamental set |
| Profitability | Moderate margin (5–14.9%) | 0.60 | Bullish |
| Profitability | Thin margin (0–4.9%) | 0.55 | Neutral |
| Profitability | Negative margin | 0.70 | Bearish; same value as strong |
| Growth | Both rev and earn unavailable | 0.30 | Missing-data case |
| Growth | Both strongly positive (> 10%) | 0.70 | Bullish |
| Growth | Both positive (0–10%) | 0.60 | Bullish |
| Growth | Both declining | 0.65 | Bearish |
| Growth | Mixed (revenue vs earnings diverge) | 0.50 | Neutral; common case |
| Growth | Partial data only | 0.45 | Partial missing |
| Debt Levels | D/E unavailable (None) | 0.30 | Missing-data case; common for franchise cos |
| Debt Levels | Negative D/E | 0.40 | Neutral — unusual |
| Debt Levels | Low D/E (≤ 50) | 0.65 | Bullish |
| Debt Levels | Moderate D/E (51–150) | 0.60 | Neutral |
| Debt Levels | High D/E (> 150) | 0.65 | Bearish; same as low |
| Free Cash Flow | FCF unavailable (None) | 0.30 | Missing-data case |
| Free Cash Flow | Positive FCF | 0.65 | Bullish |
| Free Cash Flow | Negative FCF | 0.65 | Bearish; same as positive |
| Free Cash Flow | Zero FCF | 0.55 | Neutral |

**Fundamental summary:** Maximum per-signal confidence is 0.70 (Profitability
strong, Growth strong positive). Most data-present fundamental signals cluster
at 0.60–0.65. The Debt signal tops out at 0.65 for both bullish (low D/E) and
bearish (high D/E) conditions.

---

### News signals (`app/analysis/news_analysis.py`)

Three signals are produced by `analyze_news()`. News confidence uses a **formula**
rather than fixed constants:

```python
coverage_conf = min(0.40 + article_count * 0.04, 0.70)
```

All three news signals (Sentiment, Risk Headlines, Coverage) receive the same
`coverage_conf` value derived from article count alone. Sentiment direction
does not affect confidence; only article count does.

| Article count | coverage_conf | Capped? |
|---------------|---------------|---------|
| 0 (no news) | 0.30 (via `_no_data_signal`) | No |
| 1 | 0.44 | No |
| 3 | 0.52 | No |
| 5 | 0.60 | No |
| 7 | 0.68 | No |
| 8 | 0.72 → **0.70** | Yes — cap reached |
| 10+ | 0.70 | Cap active |

| Signal | Condition | Confidence | Notes |
|--------|-----------|------------|-------|
| News Sentiment | No news available | 0.30 | `_no_data_signal` |
| News Sentiment | Net positive | `coverage_conf` | Same formula regardless of direction |
| News Sentiment | Net negative | `coverage_conf` | Same formula |
| News Sentiment | Neutral (tied or zero matches) | `coverage_conf` | Same formula |
| News Risk Headlines | No news available | 0.30 | `_no_data_signal` |
| News Risk Headlines | No risk terms | `coverage_conf` | Neutral; direction does not change conf |
| News Risk Headlines | Risk terms found | `coverage_conf` | Bearish; same conf as no-risk case |
| News Coverage | News available | `coverage_conf` | Always neutral |

**News summary:** All three news signals share a single `coverage_conf` value.
The cap of 0.70 is reached at 8+ articles. With 10 articles (a common yfinance
result), all three news signals contribute 0.70 to the average — but that is
also exactly the HIGH threshold, so news alone cannot push the overall average
above 0.70 without help from other areas.

---

### Risk signals (`app/analysis/risk_analysis.py`)

Four base signals plus an optional Beta signal (present when beta data is available).

| Signal | Condition / Direction | Confidence | Notes |
|--------|-----------------------|------------|-------|
| Volatility Risk | Data unavailable | 0.30 | `_insufficient_data_signal` |
| Volatility Risk | High (≥ 45% annualized) | 0.75 | **Highest confidence in the entire system** |
| Volatility Risk | Moderate (25–44.9%) | 0.60 | Neutral |
| Volatility Risk | Low (< 25%) | 0.65 | Bullish |
| Maximum Drawdown Risk | Data unavailable | 0.30 | |
| Maximum Drawdown Risk | Severe (≤ −35%) | 0.75 | **Tied for highest; bearish direction** |
| Maximum Drawdown Risk | Moderate (−15% to −35%) | 0.65 | Neutral |
| Maximum Drawdown Risk | Mild (> −15%) | 0.60 | Bullish — best-case is only 0.60 |
| Recent Trend Risk | Insufficient data (< 31 rows) | 0.30 | |
| Recent Trend Risk | Bearish (30d return ≤ −10%) | 0.65 | |
| Recent Trend Risk | Bullish (30d return ≥ +5%) | 0.60 | |
| Recent Trend Risk | Neutral (−10% to +5%) | 0.55 | Common for stable stocks |
| Liquidity Risk | Data unavailable | 0.30 | |
| Liquidity Risk | Low volume (< 500K avg daily) | 0.65 | Bearish |
| Liquidity Risk | Moderate volume (500K–1M) | 0.55 | Neutral |
| Liquidity Risk | High volume (≥ 1M) | 0.60 | Bullish — best-case is only 0.60 |
| Beta Risk | High beta (≥ 1.5) | 0.70 | Bearish |
| Beta Risk | Normal beta (0.8–1.5) | 0.65 | Neutral |
| Beta Risk | Low beta (< 0.8) | 0.65 | Bullish |

**Risk summary:** The highest confidence values in the entire system (0.75) are
attached to the *worst* outcomes — high volatility and severe drawdown. This means
risk signals contribute more to the overall average when conditions are bad than
when conditions are good. Best-case risk signals (Mild Drawdown: 0.60, High
Liquidity: 0.60, Bullish Recent Trend: 0.60) are all at or below 0.60.

---

## Final Confidence Labeling

From `_map_confidence()` in `app/analysis/scoring.py`:

```python
def _map_confidence(signals: list[Signal]) -> ConfidenceLevel:
    avg = sum(s.confidence for s in signals) / len(signals)
    if avg >= 0.70:
        return ConfidenceLevel.HIGH
    if avg >= 0.45:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW
```

| Level | Threshold | Behavior |
|-------|-----------|----------|
| HIGH | avg ≥ 0.70 | Requires every signal to contribute near-maximum confidence |
| MEDIUM | 0.45 ≤ avg < 0.70 | Extremely wide band; spans most realistic signal combinations |
| LOW | avg < 0.45 | Requires mostly missing-data or unavailable signals |

The MEDIUM band covers a 0.25-wide range (0.45–0.70). In practice, realistic
tickers land in a much narrower 0.55–0.65 sub-band within MEDIUM.

No weighting, normalization, or per-category breakdown is applied. All 20 signals
are treated equally in the average regardless of their `score_impact`, category
weight (35/25/25/15), or `strength` (WEAK/MODERATE/STRONG).

---

## Compression Findings

### 1. The HIGH threshold is mathematically unreachable

This is the central finding of this audit.

Even with an ideal ticker — all signals bullish, all data present, all 20 signals
at their maximum possible confidence value — the overall average cannot reach 0.70:

| Area | Signals | Best-case avg | Calculation |
|------|---------|---------------|-------------|
| Technical | 7 | 0.614 | (0.70 + 0.50 + 0.65 + 0.60 + 0.65 + 0.70 + 0.50) / 7 |
| Fundamental | 5 | 0.670 | (0.65 + 0.70 + 0.70 + 0.65 + 0.65) / 5 |
| News | 3 | 0.700 | 0.70 × 3 / 3 (cap reached at 8+ articles) |
| Risk | 5 | 0.620 | (0.65 + 0.60 + 0.60 + 0.60 + 0.65) / 5 |
| **Overall** | **20** | **0.643** | **All 20 signals averaged** |

The overall maximum is **~0.643**, which is **0.057 below the HIGH threshold of
0.70**. HIGH cannot be reached no matter what a ticker's actual conditions are.

For a realistic estimate of KO (the strongest calibration example, with 14 bullish
signals and 0 bearish, using actual reported data such as moderate D/E and neutral
recent trend), the estimated average is **~0.637** — confirming Medium.

### 2. Five signals structurally depress the average

These five signals appear at their low values in almost every real ticker,
even strongly bullish ones:

| Signal | Low confidence value | Why it's common |
|--------|---------------------|-----------------|
| RSI Condition — Neutral | 0.50 | RSI is in 30–70 range for most non-extreme stocks |
| MACD Condition — Neutral | 0.50 | MACD alignment near zero is common in sideways periods |
| Volume vs Vol SMA 20 — Bullish | 0.50 | Even "bullish" volume only receives 0.50 |
| Volume vs Vol SMA 20 — Neutral | 0.45 | Most common volume state |
| Recent Trend Risk — Neutral | 0.55 | 30-day return between −10% and +5% is common for stable stocks |

Any ticker with at least three of these five signals in their common states will
see the overall average pulled toward 0.55–0.60.

### 3. Best-case risk signals are weaker than worst-case risk signals

Risk signals exhibit an asymmetric confidence structure:

| State | Confidence |
|-------|------------|
| High volatility (bad) | **0.75** |
| Severe drawdown (bad) | **0.75** |
| Low volatility (good) | 0.65 |
| Mild drawdown (good) | 0.60 |
| High liquidity (good) | 0.60 |
| Bullish recent trend (good) | 0.60 |

The model is more confident when conditions are bad than when conditions are good.
A ticker with severe drawdown and high volatility will actually have a higher
average confidence than a stable, low-volatility stock — despite the stable stock
having stronger fundamentals and a healthier risk profile.

### 4. News confidence is capped at the HIGH threshold value

News confidence caps at exactly 0.70 (the HIGH threshold) at 8+ articles.
This means news can contribute as much as 0.70 to the average — but since
only 3 of 20 signals come from news, this alone is not enough to lift the
full average above 0.70.

### 5. Bullish and bearish signals often share identical confidence values

For most signal types, the confidence value is the same regardless of direction:

- Trend: bullish and bearish are both 0.70
- MACD: bullish and bearish are both 0.65
- SMA 20: bullish and bearish are both 0.60
- SMA 50: bullish and bearish are both 0.65
- SMA 200: bullish and bearish are both 0.70
- FCF: positive and negative are both 0.65
- Profitability: strong positive and negative margin are both 0.70

This means that signal direction (bullish vs bearish) has no effect on the
confidence average. A ticker with 14 bearish signals and a ticker with 14 bullish
signals will, if those signals share the same confidence values, produce identical
confidence levels.

### 6. No measure of signal agreement or direction balance exists

`_map_confidence()` averages per-signal confidence values but does not account
for signal direction alignment. A set of 14 bullish signals with confidence 0.65
and a set of 7 bullish and 7 bearish signals at the same confidence produce the
same average — and therefore the same label — despite representing very different
analytical situations.

---

## Evidence Alignment

### Watchlist runs (all 14 tickers returned Medium)

Both calibration watchlist runs on 2026-05-26 returned Medium for all 14 tickers.
Score range was 50.8–79.8 across the two runs — a 29-point spread — yet every
ticker received the same confidence label. This is consistent with the finding
above: the average for any real ticker lands in the 0.55–0.65 sub-band of Medium.

### Individual ticker review (all 5 returned Medium)

KO, XOM, MSFT, MCD, and PFE were run individually. All returned Medium.

KO is the most instructive case. It had:
- 14 bullish signals, 0 bearish signals, 6 neutral signals
- Near-perfect technical sub-score (97.5)
- Strong fundamental sub-score (87.5)

Despite this, the estimated overall confidence average is ~0.637. The six neutral
signals (RSI neutral, MACD neutral, Volume neutral/bullish, News Coverage/Risk,
Recent Trend neutral) collectively pull the average below the 0.70 threshold even
when all other signals are at maximum bullish confidence.

MCD provides the opposite case: 8 bullish, 4 bearish, 8 neutral signals —
a much weaker signal composition. Its estimated confidence average is ~0.620.
Yet KO and MCD both returned Medium. The 0.017 difference in estimated averages
is invisible under the current label bands.

---

## Possible Future Fix Targets

These are observation-based candidates. No values are changed in this document.

| Target | File / Location | Description |
|--------|-----------------|-------------|
| HIGH threshold | `scoring.py` → `_map_confidence()` | Currently 0.70. Theoretical max for a real ticker is ~0.643. A reduction to ≤ 0.63 would allow strongly bullish tickers to reach HIGH. |
| Volume Bullish confidence | `technicals.py` → `_volume_signal()` | Currently 0.50 — same as neutral RSI and neutral MACD. Could be raised (e.g., 0.60) to reflect that above-average volume is a meaningful signal. |
| RSI Neutral confidence | `technicals.py` → `_rsi_signal()` | Currently 0.50. Neutral RSI occurs in most healthy stocks; may be underselling its informational value as a "not extreme" confirmation. |
| MACD Neutral confidence | `technicals.py` → `_macd_signal()` | Currently 0.50. Same structural issue as RSI Neutral. |
| Recent Trend Neutral confidence | `risk_analysis.py` → `_recent_trend_signal()` | Currently 0.55. A stable stock with a neutral 30-day return is reasonably well-understood; could be 0.60. |
| Mild Drawdown confidence | `risk_analysis.py` → `_max_drawdown_signal()` | Currently 0.60. Best-case drawdown (mild) receives less confidence than worst-case (severe: 0.75). |
| High Liquidity confidence | `risk_analysis.py` → `_liquidity_signal()` | Currently 0.60. High-volume stocks are well-understood; 0.65 would be more consistent with other fully-observed signals. |
| Risk asymmetry (bad > good) | `risk_analysis.py` — multiple signals | The pattern of bad outcomes (0.75) having higher confidence than good outcomes (0.60–0.65) may be semantically correct (extremes are unambiguous) but contributes to compression of Medium. |
| News confidence per direction | `news_analysis.py` → `_sentiment_signal`, `_risk_headline_signal` | Direction does not currently affect confidence; only article count does. Whether sentiment direction should influence confidence is a design question. |
| Diagnostic breakdown field | `app/reports/` or `app/models/rating.py` | Adding a confidence breakdown (per-area sub-averages, signal counts by direction) to report output would make calibration evidence-based without changing the formula. |

---

## Recommended Next Step

**Add a diagnostic-only confidence breakdown to report output before changing
the formula or thresholds.**

The breakdown should expose, per run:

- Total signal count
- Overall confidence average (the number fed into `_map_confidence`)
- Per-area (technical / fundamental / news / risk) confidence sub-average
- Signal direction counts: bullish, bearish, neutral
- Missing-data signal count (signals with `confidence=0.30`)

This can be added to the JSON output and optionally to the Markdown report as
a collapsible debug section. It requires no change to the scoring formula or
any confidence values.

**Why this before changing the formula:**

1. It converts the estimates in this document into measured values per run.
2. It lets calibration targets be stated as specific per-area averages rather
   than estimated from code inspection alone.
3. It enables before/after comparison for any future threshold or value change.
4. It adds no semantic risk — confidence labels and composite scores are unchanged.

A simple per-area breakdown also makes it possible to answer the question:
"Is the problem the HIGH threshold, or specific signal confidence values in one
area?" without guessing.

---

## Decision Gate

Before changing confidence logic (thresholds or signal values), require:

1. **This audit is referenced and confirmed current.** If analysis modules are
   changed before a confidence fix, re-verify the inventory in this document.

2. **Diagnostic breakdown is available** — either via a new output field or via
   manually collected per-run averages for at least five tickers — to validate
   that the proposed change will produce the expected before/after label shift.

3. **Expected outcomes are stated for KO, XOM, MSFT, MCD, and PFE.** For each
   proposed change, specify: what the estimated average confidence would be
   after the change, and what `ConfidenceLevel` each ticker should receive.

4. **At least one ticker should stay MEDIUM** after the change. A fix that moves
   all tickers to HIGH is not calibration — it removes differentiation entirely.

5. **Regression tests are planned.** Identify which confidence edge cases in
   `tests/test_scoring.py` and `tests/test_composite_scoring.py` would need
   updating, and what new assertions would be added to pin the new behavior.

6. **Only one variable changes at a time.** Adjust either the HIGH threshold or
   specific signal-level values — not both simultaneously.

---

*See also:*
- `docs/confidence_calibration_design.md` — problem statement and four fix options
- `docs/calibration_review_notes.md` — evidence from calibration runs
- `docs/scoring_calibration_plan.md` — calibration process and decision framework
- `docs/scoring_rules.md` — authoritative scoring weights and thresholds
