# What money can't buy

**A football performance measurement framework**

Interactive dashboard analysing wage bill vs performance in La Liga and the Premier League across 13 seasons (2013/14–2025/26), using ordered logistic regression and Monte Carlo simulation.

🔗 **[Live site](https://YOURUSERNAME.github.io/what-money-cant-buy/)**

## Features

| Tab | Description |
|-----|-------------|
| **Season Tracker** | Browse any season. Matchweek-by-matchweek actual vs expected points. Select up to 3 teams. Current season includes Monte Carlo projection bands (p10/p50/p90). |
| **Bad Run Checker** | Pick a team and slide through their last X matches. See actual vs expected for each specific opponent with venue context. |
| **Head to Head** | Select two teams. Full historical record with cumulative points chart and match-by-match table showing actual vs model expectation. |
| **Explorer** | 12-season cumulative overperformance. Compare up to 5 teams with season-by-season bars and cumulative lines. |
| **Calculator** | Enter two wage bills, get match outcome probabilities from the ordered logit model. |

## Model

- **Method**: Ordered logistic regression — P(home win), P(draw), P(away win) as a function of log₂(wage ratio)
- **Parameters**: La Liga β = 0.4719, Premier League β = 0.676
- **Simulation**: 10,000 Monte Carlo iterations per team for current season projections
- **Data**: 9,008 matches from [football-data.co.uk](https://www.football-data.co.uk/) (results) and [Capology](https://www.capology.com/) (wages)

## Setup

No build step required. Just a static site.

### Run locally

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

### Update with latest results

```bash
pip install pandas numpy scipy requests
python update.py
git add data.json
git commit -m "Update results $(date +%Y-%m-%d)"
git push
```

The update script downloads the latest match results from football-data.co.uk and regenerates `data.json`. GitHub Pages will redeploy automatically.

## Project structure

```
index.html    — Full interactive app (React + Recharts via CDN)
data.json     — Complete dataset (13 seasons × 2 leagues × 20 teams)
update.py     — Weekly data refresh script
README.md     — This file
```

## Based on

Full research paper: *"What money can't buy — A football performance measurement framework"* (80+ pages with methodology, case studies and data appendices).

📧 whatmoneycantbuyfootball@gmail.com
