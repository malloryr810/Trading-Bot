# Prompt: Scoring Engine

_Placeholder — to be written when implementing `app/analysis/scoring.py`._

## Intended scope

- Accept signal lists from all four analysis modules
- Apply weighted formula: Technical 35%, Fundamental 25%, News 25%, Risk 15%
- Apply risk override / blocking logic
- Return a `Rating` model with composite score and sub-score breakdown
