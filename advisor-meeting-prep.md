# Advisor Meeting Prep — Premier League 25/26 Prediction Thesis

## Project Overview
**Working title:** Predicting the Premier League 25/26 Season using Machine Learning and Data Visualization

**Core idea:** Rather than predicting the final table directly, predict individual match outcomes (win/draw/loss) with ML classifiers, then simulate the remainder of the season many times (Monte Carlo-style) to generate a projected final table — along with probability distributions (e.g. title odds, relegation odds, top-4 odds) rather than a single fixed prediction.

## Required Project Outcomes (from syllabus)
- Design and implement a relational SQL database for sports analytics data
- Collect, clean, and preprocess large datasets using Python
- Apply feature engineering for predictive modeling
- Develop and evaluate ML models for match outcome prediction
- Compare model performance (accuracy, precision, recall, F1-score)
- Build interactive dashboards in Power BI
- Integrate SQL + ML + visualization into a complete pipeline
- Document project planning and iterative development

## Proposed Approach

### Target & Method
- **Primary target:** Match outcome (win/draw/loss) via classification
- **Derived output:** Full 25/26 table via season simulation using predicted match probabilities
- **Why this fits the requirements:** Match-level classification maps directly onto accuracy/precision/recall/F1, while the season simulation produces the "final table" prediction plus much richer supplementary output than a single static ranking

### Models to Compare (2-3 required by advisor)
1. **Logistic Regression** — interpretable baseline
2. **Random Forest** — captures non-linear feature interactions, gives feature importance
3. **XGBoost (Gradient Boosting)** — typically top-performing model in similar sports-prediction work; good "advanced" comparison point against Random Forest
   - *Optional 4th/alternate:* Poisson regression on goals scored (classic soccer-analytics approach), deriving win/draw/loss from predicted scorelines

### "Extra Information" Beyond Win/Loss — Options to Discuss
1. **Predicted probabilities** per outcome (e.g. 62% home win / 24% draw / 14% away win) instead of a single label — needed for the season simulation anyway
2. **Predicted scorelines** via regression/Poisson model, not just the result
3. **Feature importance / explainability** (e.g. via SHAP) — which factors drove a given prediction (form, home advantage, injuries, xG differential)
4. **Model confidence/uncertainty** — flagging matches the model is unsure about vs. highly confident

*Leaning toward combining probabilities (for simulation) + feature importance (for explainability), but open to advisor's input.*

## Candidate Data Sources
- **football-data.co.uk** — free historical match results/odds CSVs, easy SQL import
- **FBref / Understat** — advanced stats (xG, shots, possession) for richer features
- **API-Football / Football-Data.org** — API access for ongoing/live data through the season
- **Kaggle** — pre-scraped PL datasets for early prototyping

## Draft Milestone Calendar
| Date | Milestone |
|---|---|
| 8/20 | Project scope & technical planning |
| 8/27 | Finalize project scope and technical goals |
| 9/3 | SQL database implementation begins |
| 9/24 | Data cleaning pipeline completion |
| 10/8 | Initial predictive models operational |
| 10/29 | Interactive analytics dashboard |
| 11/12 | End-to-end system functional |
| 12/2 | Final technical presentation |

## Questions for Advisor
1. Does predicting match outcomes → simulating the season satisfy the "predict the final table" goal, or is a more direct table-prediction approach expected?
2. Is the 3-model comparison (Logistic Regression, Random Forest, XGBoost) the right scope, or should a domain-specific model (e.g. Poisson) replace one of them?
3. Which "extra information" direction is most valuable for the thesis — probabilities, scorelines, explainability, or a combination?
4. Any preferred data source, or department infrastructure/preferences for SQL setup (e.g. Postgres vs. MySQL)?
5. Is multiple seasons of historical training data expected, or is a single prior season sufficient?
