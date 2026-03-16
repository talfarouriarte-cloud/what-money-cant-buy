# Football beyond money — v2.0

**Payroll-adjusted performance analysis and prediction**

Interactive bilingual (English/Spanish) dashboard analysing football team performance against budget expectations in La Liga and the Premier League across 13 seasons (2013/14–2025/26), using ordered logistic regression and Monte Carlo simulation.

**Live site:** [footballbeyondmoney.uk](https://footballbeyondmoney.uk)

**Full research paper (PDF):** [What money can't buy](https://footballbeyondmoney.uk/What%20money%20cant%20buy.pdf)

## How it works

A club's annual wage bill is the single best publicly available predictor of league performance. The ordered logistic regression model takes the log₂ ratio of two teams' wages and produces match-level win/draw/loss probabilities. These probabilities drive everything else: expected points per match, Monte Carlo projections of final standings, run significance testing, and multi-season overperformance tracking.

The app updates automatically every day at 08:00 UTC via GitHub Actions, downloading the latest results, recalculating budget forecasts from the current fixture order, and rerunning all simulations.

## Tabs

| Tab | What it does |
|-----|-------------|
| **Home** | Team selector with payroll. 6 summary cards: Season Tracker, Next Matchday (closest & most unbalanced matches), Predictions, Run Evaluator, Head to Head, Overperformance. |
| **Season Tracker** | Game-by-game actual vs expected points with W/D/L coloured dots with halos. MC projection bands (p10–p90). Budget forecast line (deterministic expected, parallel to actual). Tooltip: Home vs Away with crests, payroll, date, probabilities. |
| **Matches** | 20×20 interactive match grid. Teams sorted by payroll. Row = home, column = away. Heatmap shows predicted home win probability. Coloured dots for results. Touch sliding with pin/unpin, connector lines, row/column highlight. Next matchday fixtures highlighted. Legend, counter, top 5 surprises. |
| **Predictions** | Position group probabilities (champion, UCL, Europa, Conference, relegation) from 10,000 joint league simulations. Budget vs updated forecast. |
| **Run Evaluator** | Select any range of games. Compares actual to expected with probability bands. Overlapping windows for season probability. Tooltip: Home vs Away with payroll. |
| **Head to Head** | Two teams, full historical record. Time filter (all/10yr/5yr/3yr). Cumulative chart with per-match win probabilities, payroll per season. |
| **Overperformance** | Cumulative extra points across all seasons. Three metrics (extra pts, normalised, Managerial Score) and three time windows (all/5yr/3yr). Up to 5 teams. |
| **Calculator** | Wage bills in → match probabilities out. Select real teams or set custom values. |
| **Methodology** | Full model description, parameter table, data sources. |
| **Data & Sources** | Wage tables by season, data source cards, coverage summary. |
| **History** | Historical distribution of match results (W/D/L). Compare teams against league average. Filter by venue and time period. |

## Features

- **Bilingual**: Full English/Spanish interface (308 translation keys). Language selectable on first visit and via header dropdown.
- **PWA**: Installable as a mobile app. Service worker with offline support. Install prompt for Android, instructions for iOS.
- **Responsive**: Adapts to mobile, tablet, and desktop. Chart heights, fonts, grid cell sizes, and layout scale across 4 breakpoints.
- **Interactive match grid**: 20×20 heatmap with touch sliding, tap pin/unpin, SVG connector lines, row/column highlight, next matchday markers. Touch-optimised with scroll prevention on data cells only.
- **Payroll everywhere**: All tooltips show Home vs Away format with team crests and payroll comparison.
- **Compact dates**: Match dates shown as day-of-week abbreviation + day/month (e.g. M15/2).
- **Budget forecast**: Deterministic expected line using same match order as actual season, recalculated daily from current fixture calendar.
- **Welcome screen**: First-time visitors choose language, league, and team.
- **Team crests**: 52 team crests loaded from crests.json.
- **Daily updates**: GitHub Actions fetches results, fixture calendar, recalculates budget, reruns MC simulations, and commits automatically.
- **No backend**: All computation happens in the browser and in the daily Python update script.

## Files

| File | Purpose |
|------|---------|
| `index.html` | The app — single-file React + Recharts via CDN (~137KB) |
| `data.json` | Complete dataset: 13 seasons of match-by-match results with dates, MC bands, position probabilities, cumulative overperformance |
| `fixtures.json` | Fixture calendar with dates from football-data.org API |
| `i18n.json` | 308 translation keys (English + Spanish) |
| `crests.json` | Team crest URLs (52 teams across 4 divisions) |
| `manifest.json` | PWA manifest |
| `sw.js` | Service worker (network-first for data, cache-first for assets) |
| `header-bg.jpeg` | Header/footer/welcome background image |
| `og-image.jpeg` | Social media preview image (1200×630) |
| `icon-*.png` | PWA icons (48–512px + maskable) |
| `update.py` | Daily update: results + fixture calendar + MC simulations + budget recalculation + match dates |
| `setup_season.py` | Run once at start of each season |
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
- **Fixture calendar**: [football-data.org](https://www.football-data.org) API — matchdays, dates, played status
- **Wage data**: [Capology](https://www.capology.com) and [FBref](https://fbref.com) — annual gross wage bills, once per season
- **Team crests**: [football-data.org](https://www.football-data.org) API

## Version history

- **v2.0** (Mar 2026): Match grid, responsive layout, PWA, touch interactions, payroll in all tooltips, Home vs Away format, budget deterministic line, match dates, next matchday markers
- **v1.0** (Mar 2026): Initial launch with 9 tabs, bilingual, daily updates

## Operations

See [OPERATIONS.md](OPERATIONS.md) for daily updates, new season setup, wage data collection, and troubleshooting.

## Contact

whatmoneycantbuyfootball@gmail.com
