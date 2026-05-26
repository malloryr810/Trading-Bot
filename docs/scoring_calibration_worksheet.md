# Scoring Calibration Worksheet

## Purpose

This worksheet is for manually recording observations from generated stock
reports before making any scoring changes. Copy it, fill it in for each ticker
reviewed, and use the pattern-tracking table to find repeated issues across
multiple tickers.

**Important:**

- This worksheet does not change scoring behavior.
- It is not financial advice.
- It is not a backtest.
- It is used to support careful future calibration decisions only.

See `docs/scoring_calibration_plan.md` for the full calibration process,
decision gate, and list of tunable levers.

---

## How to Use This Worksheet

1. **Run a single-ticker report** using the CLI:
   ```
   python -m app.main AAPL --save-markdown --save-json
   ```
   Or for a watchlist:
   ```
   python -m app.main --watchlist watchlists/default.txt --save-markdown --save-json
   ```

2. **Open the saved Markdown report** from `outputs/reports/`. It is the most
   readable format for manual review.

3. **Copy the key values** — score, category, confidence, sub-scores, summaries,
   key positives, key risks — into the ticker review table below.

4. **Add your manual judgment.** Does the category feel right for this company?
   Is the score proportionate? Are the key risks and strengths plausible?

5. **Record whether the current rating feels too aggressive, too conservative, or
   reasonable.** Be specific about which part seems off.

6. **Do not change scoring code** until enough examples across different tickers
   show the same repeated pattern. One outlier is not enough.

---

## Ticker Review Table

Each row represents one ticker reviewed at one point in time. Add rows as you
work through the evaluation set. Do not delete previous rows.

| Date Reviewed | Ticker | Company | Sector / Industry | Current Price | Score | Category | Confidence | Technical Summary | Fundamental Summary | News Summary | Risk Summary | Key Positives | Key Risks | Manual Judgment | Too Aggressive / Too Conservative / Reasonable | Proposed Change | Notes |
|---------------|--------|---------|-------------------|---------------|-------|----------|------------|-------------------|---------------------|--------------|--------------|---------------|-----------|-----------------|------------------------------------------------|-----------------|-------|
| YYYY-MM-DD | TICKER | Company Name | Sector / Industry | $0.00 | 0.0 | Category | low/medium/high | *(paste technical summary)* | *(paste fundamental summary)* | *(paste news summary)* | *(paste risk summary)* | *(paste key positives)* | *(paste key risks)* | *(your assessment)* | Reasonable | none | *(free-form notes)* |

---

## Pattern Tracking Table

After reviewing several tickers, use this table to record patterns that appear
across more than one example. A single outlier does not justify a scoring change.
Look for the same issue showing up across at least two or three different tickers
before recording it here.

| Pattern Observed | Example Tickers | Affected Signal Area | Possible Cause | Proposed Future Adjustment | Evidence Strength |
|------------------|-----------------|----------------------|----------------|----------------------------|-------------------|
| *(describe the repeated pattern)* | TICKER1, TICKER2 | Technical / Fundamental / News / Risk / Confidence / Category thresholds / Composite weights | *(what might be causing it)* | *(specific proposed change, or "needs more examples")* | Weak / Moderate / Strong |

**Evidence strength guidance:**

| Strength | Meaning |
|----------|---------|
| Weak | Seen in 1–2 tickers; not yet conclusive |
| Moderate | Seen in 3–5 tickers with similar characteristics |
| Strong | Seen consistently across 6+ tickers in different contexts |

Only "Strong" evidence should drive a code change. "Moderate" evidence should
prompt collecting more examples. "Weak" evidence should be noted but not acted on.

---

## Decision Rules Before Changing Scoring

1. **Do not change scoring based on one ticker.** A single example may reflect
   unusual market conditions, stale data, or a genuine edge case — not a
   systematic flaw.

2. **Look for repeated patterns across several tickers.** The same signal area
   appearing miscalibrated in multiple unrelated companies is a meaningful signal.

3. **Prefer changing the smallest possible part of the scoring system.** Adjust
   a single threshold or a single signal's impact value before touching composite
   weights. Category thresholds are lower-risk than weight changes.

4. **Update `docs/scoring_rules.md`** if any scoring logic changes. The rationale
   for each change — including which worksheet rows motivated it — should be
   recorded there.

5. **Add or update tests if scoring code changes.** Pin specific input → output
   expectations to catch future drift.

6. **Record the reason for any scoring change in `docs/development_log.md`.** This
   keeps the history of calibration decisions alongside the code history.
