# Football beyond money — v3.1

**Payroll-adjusted performance analysis and prediction across Europe's top 6 leagues**

Interactive bilingual (English/Spanish) dashboard analysing football team performance against budget expectations using ordered logistic regression and Monte Carlo simulation. Covers 6 leagues, 13 seasons (2013/14–2025/26), 201 teams, and 26,810 matches.

**Live site:** [footballbeyondmoney.uk](https://footballbeyondmoney.uk)

**Full research paper (PDF):** [What money can't buy](https://footballbeyondmoney.uk/What%20money%20cant%20buy.pdf)

## How it works

A club's annual wage bill is the single best publicly available predictor of league performance. The ordered logistic regression model takes the log₂ ratio of two teams' wages and produces match-level win/draw/loss probabilities. These drive expected points, Monte Carlo projections, run significance testing, and multi-season overperformance tracking.

The app updates automatically twice daily (06:00 + 08:00 UTC) via GitHub Actions, with dual cron for reliability. Season rollover is fully automatic — the app advances to the new season every August and uses previous-season wages until new ones are uploaded. The only annual manual step is updating `all_wages.json` with new salary data (typically September).

## Features

- **6 European leagues** (La Liga, Premier League, Serie A, Bundesliga, Ligue 1, Eredivisie)
- **11 tabs**: Home, Season Tracker, Matches, Predictions, Run Evaluator, Head to Head, Overperformance, Calculator, Methodology, Data & Sources, History
- **Bilingual** (English/Spanish, 317 translation keys)
- **Narrative Home cards**: each answers a specific question with natural language + badges
- **H2H unified pill-table**: model vs historical record by venue
- **Goal difference tiebreaker** in all rankings
- **Budget line parallelism**: deterministic p50 in both forecast lines
- **PWA**: installable, pull-to-refresh, responsive (4 breakpoints)
- **Touch-optimised**: dismissible Recharts tooltips, swipe-safe charts
- **Zero-config season rollover**: auto-detected from date, wages fall back gracefully

## Data sources

- **Match results**: [football-data.co.uk](https://www.football-data.co.uk)
- **Fixture calendar**: [football-data.org](https://www.football-data.org) API
- **Wage data**: [Capology](https://www.capology.com) — stored in `all_wages.json`
- **Team crests**: [football-data.org](https://www.football-data.org) API

## Annual workflow

1. **August**: Season auto-advances. App processes new matches immediately with previous-season wages as approximation. GitHub Action creates a reminder Issue.
2. **September** (after transfer window): screenshot Capology tables → Claude extracts data → update `all_wages.json` → commit. All data recalculated with accurate wages.
3. Everything else is automatic

## Version history

- **v3.5** (Apr 2026): Tracker Position view redesigned. Three line series: actual rank (strong colour, GW1→now), p50 projection (same hue at 0.45 opacity, now→end), and Final-rank p50 evolution (orange dashed, only shown in single-team view) tracking how the predicted final rank shifted week by week. Backend (`update.py`): `simulate_position_probs` now returns the median rank `p50` per team, used by the frontend for both the projection target and the per-GW evolution series. Bug fix: explicit X-axis ticks on both Points and Position charts so the last gameweek is always shown (previously GW37 of a 38-GW season was hidden by Recharts' auto-spacing). SW v75.
- **v3.4.3** (Apr 2026): Stale-wage detection. Backend (`update.py`): new `detect_wage_status` function compares each season's wages against the previous one — if ≥80% of the team values are identical, the season is flagged `stale` in `data.meta.wage_status[lg][sn]`. Frontend (Data tab): yellow warning banner shown above the wage section when the active league+season is flagged as stale. SW v74.
- **v3.4.2** (Apr 2026): Updated About-this-tab explanations on Tracker and Predictions tabs (EN+ES) to cover the Points/Position toggle, the position-view zones and date-based ranking, and the per-team probability evolution arrow in Predictions. SW v73.
- **v3.4.1** (Apr 2026): Bug fixes. (1) Predictions evolution arrow button: now in flex layout with the team name, right-aligned in the team cell, no longer wraps to a second line on narrow mobile. (2) BadRun and H2H tabs were going blank when the Tracker had multiple teams selected (the comma-separated `sel` hash param was being used directly as a team key); now it correctly takes only the first team. SW v72.
- **v3.4** (Apr 2026): Wage evolution chart in Data tab. Multi-team selector (1-3 teams, like Tracker). Shows annual wage bill across all seasons of the selected league in absolute M€/M£. Lines break when a team is not in the league. League selector promoted to the top of the tab to be shared between chart and table sections. SW v71.
- **v3.3.3** (Apr 2026): Replaced unreadable in-chart labels with a compact horizontal color-coded legend above each evolution chart (1st / UCL / UEL / Conf / Mid / Rel with color swatches in stack order). SW v70.
- **v3.3.2** (Apr 2026): Predictions evolution chart label refinement: white pill background with band-color text (instead of white text + outline). Min height threshold (14px segment) hides labels in too-thin bands. Edge-nudging avoids clipping at first/last GW. SW v69.
- **v3.3.1** (Apr 2026): Predictions evolution chart polish: stack order inverted (Champion at top, Relegation at bottom), inline labels on each band replace the legend (rendered at the GW where each band is widest, hidden if always thin). SW v68.
- **v3.3** (Apr 2026): Probability evolution chart in Predictions (per-team expandable rows). Backend: `pos[lg][sn].hist` array with per-GW probability snapshots (n_sims=2000, gw_step=1). Frontend: stacked-area chart at 100% under each row when expanded. SW v67.
- **v3.2** (Apr 2026): Tracker view toggle (Points / Position). Position view shows team rank trajectory with league-specific zone backgrounds (Champion/UCL/UEL/Conference/relegation). Single-team and multi-team modes. SW v66.
- **v3.1.1** (Apr 2026): Chronological ordering of played matches in Tracker and Run Evaluator (was sorted by official GW, now by actual date). PJ column in Predictions. SW v65.
- **v3.1** (Mar 2026): H2H pill-table, narrative Home cards, Explorer-style Tracker selector, match grid auto-highlight, GD tiebreaker, budget p50 fix, touch fixes, auto season rollover, wages from `all_wages.json`. SW v60.
- **v3.0** (Mar 2026): 6 leagues, 201 teams, narrative templates, per-league European spots, season navigation.
- **v2.0** (Mar 2026): Match grid, responsive layout, PWA, touch interactions, budget line, match dates.
- **v1.0** (Mar 2026): Initial launch.

## Operations

See [OPERATIONS.md](OPERATIONS.md) for daily updates, season setup, wage collection, and troubleshooting.

## Contact

whatmoneycantbuyfootball@gmail.com
