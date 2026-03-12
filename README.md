# Football beyond money

**Payroll-adjusted performance analysis and prediction**

Interactive bilingual (English/Spanish) dashboard analysing football team performance against budget expectations in La Liga and the Premier League across 13 seasons (2013/14–2025/26), using ordered logistic regression and Monte Carlo simulation.

**Live site:** [footballbeyondmoney.uk](https://footballbeyondmoney.uk)

**Full research paper (PDF):** [What money can't buy](https://footballbeyondmoney.uk/What%20money%20cant%20buy.pdf)

## How it works

A club's annual wage bill is the single best publicly available predictor of league performance. The ordered logistic regression model takes the log₂ ratio of two teams' wages and produces match-level win/draw/loss probabilities. These probabilities drive everything else: expected points per match, Monte Carlo projections of final standings, run significance testing, and multi-season overperformance tracking.

The app updates automatically every day at 08:00 UTC via GitHub Actions, downloading the latest results and rerunning all simulations.

## Tabs

| Tab | What it does |
|-----|-------------|
| **Home** | Team selector + 5 summary cards linking to each analysis view |
| **Season Tracker** | Game-by-game actual vs expected points with W/D/L coloured dots. MC projection bands (p10–p90) for current season. Up to 3 teams side by side. |
| **Predictions** | Position group probabilities (champion, UCL, Europa, Conference, relegation) from 10,000 joint league simulations. Budget forecast vs updated forecast. |
| **Run Evaluator** | Select any range of games. Compares actual points to expected with probability bands. Reports how likely this run is within a full season (overlapping windows). |
| **Head to Head** | Two teams, full historical record. Time filter (all, 10yr, 5yr, 3yr). Cumulative chart with per-match win probabilities. Current season W/D/L probabilities. |
| **Overperformance** | Cumulative extra points across all seasons. Three metrics (extra pts, normalised, Managerial Score) and three time windows (all, 5yr, 3yr). Up to 5 teams. |
| **Calculator** | Wage bills in → match probabilities out. Select real teams or set custom values. |
| **Methodology** | Full model description, parameter table, data sources. |
| **Data & Sources** | Wage tables by season, data source cards, coverage summary. |
| **History** | Historical distribution of match results (W/D/L). Compare teams against league average. Filter by venue and time period. |

## Features

- **Bilingual**: Full English/Spanish interface (289 translation keys). Language selectable on first visit and via header dropdown.
- **Welcome screen**: First-time visitors choose language, league, and team. Preferences persist via URL hash.
- **Team crests**: 52 team crests loaded from crests.json, built via football-data.org API with manual fallbacks for historical teams.
- **Mobile-first**: Hamburger navigation below 640px, horizontal tab bar above. Home button on all screens.
- **Daily updates**: GitHub Actions fetches results, fixture calendar, reruns MC simulations, and commits automatically.
- **No backend**: All computation happens in the browser (model parameters embedded) and in the daily Python update script.

## Files

| File | Purpose |
|------|---------|
| `index.html` | The app — single-file React + Recharts via CDN (~103KB) |
| `data.json` | Complete dataset: 13 seasons of match-by-match results, MC bands, position probabilities, cumulative overperformance |
| `fixtures.json` | Fixture calendar with dates from football-data.org API |
| `i18n.json` | 289 translation keys (English + Spanish) |
| `crests.json` | Team crest URLs (52 teams across 4 divisions) |
| `update.py` | Daily update script: results + fixture calendar + MC simulations |
| `setup_season.py` | Run once at start of each season to initialise calendar and pre-season MC |
| `build_crests.py` | Queries football-data.org API to build crest URL mapping |
| `.github/workflows/update.yml` | Daily update at 08:00 UTC |
| `.github/workflows/build-crests.yml` | Manual trigger to regenerate crests |

## Model parameters

| League | β | θ₁ | θ₂ | Matches | Seasons |
|--------|------|--------|--------|---------|---------|
| La Liga | 0.4719 | −1.0404 | 0.2081 | 4,448 | 13 |
| Premier League | 0.6760 | −0.8358 | 0.2422 | 4,560 | 13 |

σ = 1.58 (standard deviation of match points, used for probability bands and Managerial Score).

## Data sources

- **Match results**: [football-data.co.uk](https://www.football-data.co.uk) — CSV downloads, updated daily
- **Fixture calendar**: [football-data.org](https://www.football-data.org) API — official matchdays, dates, played status
- **Wage data**: [Capology](https://www.capology.com) and [FBref](https://fbref.com) — annual gross wage bills per club, collected once per season (August/September after the transfer window closes)
- **Team crests**: [football-data.org](https://www.football-data.org) API — crest URLs for La Liga, Premier League, Segunda División, Championship

## Operations

See [OPERATIONS.md](OPERATIONS.md) for daily updates, new season setup, wage data collection, data format reference, and troubleshooting.

## Contact

whatmoneycantbuyfootball@gmail.com
