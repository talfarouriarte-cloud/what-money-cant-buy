# What money can't buy

**A football performance measurement framework**

Interactive dashboard analysing wage bill vs performance in La Liga and the Premier League across 13 seasons (2013/14–2025/26), using ordered logistic regression and Monte Carlo simulation.

## Features

| Tab | Description |
|-----|-------------|
| **Season Tracker** | Browse any season. Matchweek-by-matchweek actual vs expected. MC projection bands for current season. |
| **Bad Run Checker** | Pick a team, slide through last X matches. Actual vs expected per opponent. |
| **Head to Head** | Two teams, full historical record with cumulative chart. |
| **Explorer** | 12-season cumulative overperformance, up to 5 teams. |
| **Calculator** | Wage bills in, match probabilities out. |

## Files

| File | Purpose |
|------|---------|
| `index.html` | The interactive app (React + Recharts via CDN) |
| `data.json` | Complete dataset (13 seasons, matchweek by matchweek) |
| `fixtures.json` | Full fixture calendar for MC simulation ordering |
| `update.py` | Daily update script (results + MC re-simulation) |
| `setup_season.py` | Run once at start of each season to set up calendar |

## Daily updates

Automatic via GitHub Actions — every day at 8am UTC:
1. Downloads latest results from football-data.co.uk
2. Recomputes expected points for all matches
3. Re-runs 10,000 Monte Carlo simulations using the actual fixture calendar
4. Commits updated data.json

## New season setup

At the start of each season:
```bash
python setup_season.py --season 26/27 --ll LaLiga.csv --pl EPL.csv
```
The CSV should contain the full fixture calendar with HomeTeam, AwayTeam, and Round columns.

## Model

- Ordered logistic regression: P(win), P(draw), P(loss) from log2(wage ratio)
- La Liga beta = 0.4719, Premier League beta = 0.676
- 9,008 matches, 480 team-seasons
