# Scoring Calibration Plan

## Purpose

The goal is to make the rule-based scoring system more reliable and explainable
over time — not to turn this project into an automated trading system.

Before any scoring weights, thresholds, or signal logic can be changed with
confidence, we need a lightweight process for collecting observations, recording
what feels wrong, and making changes one variable at a time with documented
reasoning. This document defines that process.

No scoring code, weights, or thresholds are changed as part of this document.

---

## Current Scoring Model

### Composite Score Formula

**Composite = (Technical × 0.35) + (Fundamental × 0.25) + (News × 0.25) + (Risk × 0.15)**

| Category            | Weight | Source module                          |
|---------------------|--------|----------------------------------------|
| Technical signals   | 35%    | `app/analysis/technicals.py`           |
| Fundamental signals | 25%    | `app/analysis/fundamentals_analysis.py`|
| News / sentiment    | 25%    | `app/analysis/news_analysis.py`        |
| Risk conditions     | 15%    | `app/analysis/risk_analysis.py`        |

Each sub-score is normalized to 0–100 before weighting.

### Rating Categories and Thresholds

| Score range | Category             |
|-------------|----------------------|
| ≥ 85        | Strong Buy Candidate |
| ≥ 70        | Buy Candidate        |
| ≥ 55        | Watchlist            |
| ≥ 45        | Hold                 |
| ≥ 30        | Avoid                |
| < 30        | Sell / Exit Warning  |

These thresholds are initial estimates defined in `app/analysis/scoring.py`.
See `docs/scoring_rules.md` for the authoritative reference.

---

## Calibration Principles

These principles govern how scoring should be tuned over time.

1. **Keep scoring transparent and rule-based first.** Each signal and threshold
   should have a stated reason. Opaque tuning produces a model that is hard to
   audit or explain.

2. **Prefer documented reasoning over arbitrary tuning.** Every change to a
   weight or threshold should be accompanied by a written example that motivated
   it — not just a number change in code.

3. **Tune slowly and one variable at a time.** Changing multiple weights
   simultaneously makes it impossible to know which change caused an observed
   shift in output.

4. **Do not optimize for short-term price movement without a defined evaluation
   method.** Without a clear definition of what "correct" means (and over what
   time horizon), optimization is guesswork.

5. **Separate scoring calibration from backtesting.** Calibration is a manual
   review process. Backtesting is a separate, later-stage effort with its own
   data requirements and design constraints.

6. **Do not use this model as financial advice.** Scores and categories are
   research indicators only. They do not constitute buy, sell, or hold
   recommendations.

---

## Candidate Evaluation Set

Before changing anything, build a small, manually curated set of tickers that
represents the range of conditions the scoring system should distinguish between.

### Suggested Categories

| Category                   | Purpose                                                |
|----------------------------|--------------------------------------------------------|
| Large-cap tech             | Stable, well-covered; test moderate-to-high scores    |
| Mature dividend companies  | Steady fundamentals, lower growth; test Hold/Watchlist |
| High-growth companies      | High valuations, strong revenue; test category edges  |
| Cyclical companies         | Sensitive to macro; test risk signal behavior         |
| Distressed or weak stocks  | Declining fundamentals; test low-score categories     |
| ETFs (optional)            | Broad-market reference only, not primary subjects     |

**Do not hardcode this list in any source file.** It is a planning aid and will
change as calibration progresses. Store observations in a separate worksheet
or Markdown table (see Calibration Worksheet Fields below).

Aim for 10–20 tickers total across the categories above as a first evaluation
set. Enough to identify obvious miscalibrations; small enough to review manually
in a single session.

---

## Manual Review Workflow

This is the intended workflow for evaluating current scoring behavior before
proposing changes.

1. **Run single-ticker reports.**  
   `python -m app.main TICKER --save-report --save-json --save-markdown`

2. **Export Markdown and JSON reports.**  
   Save to `outputs/reports/` and `outputs/results/` using the standard CLI
   flags. The Markdown report is the most readable format for manual review.

3. **Record current score, category, confidence, and key explanations.**  
   Capture the composite score, rating category, confidence level, and the
   narrative summaries from each signal category.

4. **Manually inspect whether the rating seems too aggressive, too conservative,
   or reasonable.**  
   Ask: Does this category match your prior knowledge of the company's current
   condition? Does the score feel proportionate? Are the key risks and strengths
   plausible?

5. **Document observations before changing scoring rules.**  
   Write down what feels wrong and why — using specific signal names and score
   values, not vague impressions — before touching any code.

6. **Only then propose specific scoring adjustments.**  
   Each proposal should reference: which ticker triggered the observation, which
   signal or threshold appears miscalibrated, and what the proposed new value is
   with its rationale.

---

## Calibration Worksheet Fields

Track observations in the worksheet template at `docs/scoring_calibration_worksheet.md`.
The fields defined there are listed below for reference. The worksheet also includes
a pattern-tracking table and decision rules for when to act on findings.

| Field                     | Notes                                           |
|---------------------------|-------------------------------------------------|
| Ticker                    | e.g. AAPL                                       |
| Company                   | Full name                                       |
| Sector / Industry         | e.g. Technology / Semiconductors                |
| Date reviewed             | ISO date, e.g. 2026-05-26                       |
| Composite score           | 0–100                                           |
| Rating category           | e.g. Watchlist                                  |
| Confidence level          | low / medium / high                             |
| Technical score           | 0–100 sub-score                                 |
| Technical summary         | Narrative from report                           |
| Fundamental score         | 0–100 sub-score                                 |
| Fundamental summary       | Narrative from report                           |
| News score                | 0–100 sub-score                                 |
| News summary              | Narrative from report                           |
| Risk score                | 0–100 sub-score                                 |
| Risk summary              | Narrative from report                           |
| Reviewer judgment         | Reasonable / Too aggressive / Too conservative  |
| Notes                     | Free-form observations                          |
| Proposed change           | Specific change, or "none"                      |

---

## What Can Be Tuned Later

These are the levers available for future calibration, listed from lowest to
highest risk of unintended side effects.

- **Category thresholds** — the score cutoffs that determine which `RatingCategory`
  a score maps to. Low coupling; easy to reason about.
- **Confidence calculation** — the logic in `scoring.py` that assigns
  `ConfidenceLevel.LOW / MEDIUM / HIGH`. Affects explanatory output only.
- **Individual technical signal score_impact values** — the per-signal contribution
  weights in `technicals.py`. Medium coupling; change one at a time.
- **Individual fundamental signal score_impact values** — same as above for
  `fundamentals_analysis.py`.
- **News keyword weights** — the keyword matching logic in `news_analysis.py`.
  Easy to observe but hard to validate without a labeled dataset.
- **Risk penalty severity** — the magnitude of negative score_impact values in
  `risk_analysis.py`. Can significantly compress overall scores if over-tightened.
- **Missing-data penalty logic** — the neutral `Signal` fallback behavior when
  data is absent. Currently uses `confidence=0.30`; may need adjustment.
- **Category-level composite weights** — the 35/25/25/15 split. Highest risk of
  broad unintended effects. Change last, with strong motivation.

---

## What Should Not Be Tuned Yet

- **Do not add backtesting.** Backtesting requires a defined evaluation period,
  clean historical data, and a clear benchmark — none of which are in place.
- **Do not add ML or LLM scoring.** Replacing the rule-based model with a learned
  model is a separate architectural decision requiring explicit approval.
- **Do not add automated buy/sell decisions.** This project is a research tool.
  Recommendations require human judgment.
- **Do not add portfolio sizing.** Position sizing is out of scope for this project.
- **Do not change weights without documented examples.** Weight changes driven by
  intuition alone are not calibration — they are noise.

---

## Future Implementation Ideas

These are candidate follow-on steps, not commitments.

- **Calibration worksheet template** — available at `docs/scoring_calibration_worksheet.md`.
  Contains a ticker review table, pattern-tracking table, and decision rules.
- **Add a CLI command to export calibration rows** — a `--calibration-export` flag
  that prints or saves the worksheet fields for a given ticker in CSV or JSON.
- **Update `docs/scoring_rules.md`** — after calibration decisions are made and
  validated, document the rationale for each changed threshold or weight in
  `scoring_rules.md`.
- **Add regression tests for scoring changes** — only when scoring logic actually
  changes; pin specific input → output expectations to catch accidental drift.

---

## Next Decision Gate

**Before changing any scoring code, we should:**

1. Run the full pipeline across a representative sample of 10–20 tickers.
2. Export and review the Markdown reports.
3. Fill in calibration worksheet rows for each ticker.
4. Identify at least one concrete example of a miscalibration with a specific
   proposed fix and clear reasoning.

No weight, threshold, or signal logic should change without completing step 4.
