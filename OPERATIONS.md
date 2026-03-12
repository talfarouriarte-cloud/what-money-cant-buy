# Operations Guide — Football beyond money

## Table of contents

1. [Daily updates (automatic)](#1-daily-updates-automatic)
2. [New season setup](#2-new-season-setup)
3. [Wage data collection](#3-wage-data-collection)
4. [Crest management](#4-crest-management)
5. [Translation (i18n)](#5-translation-i18n)
6. [Custom domain](#6-custom-domain)
7. [Data format reference](#7-data-format-reference)
8. [External dependencies](#8-external-dependencies)
9. [Name mapping](#9-name-mapping)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Daily updates (automatic)

GitHub Actions runs `update.py` every day at 08:00 UTC. It can also be triggered manually from the Actions tab.

### What it does (in order)

1. Loads existing `data.json` and `fixtures.json`
2. Fetches fixture calendar from football-data.org API for both leagues (La Liga = PD, Premier League = PL)
3. Updates `fixtures.json` with current matchday dates and played/scheduled status
4. Downloads latest match results CSV from football-data.co.uk (La Liga = SP1.csv, Premier League = E0.csv)
5. Recomputes expected points for all played matches using the ordered logit model
6. Looks up official matchday (GW) for each played match from the fixture calendar
7. Runs 10,000 Monte Carlo simulations for remaining fixtures to produce updated p10/p50/p90 bands
8. Computes position probabilities (champion, UCL, Europa, Conference, mid-table, relegation) for both budget and updated forecasts
9. Builds remaining fixture list per team with W/D/L probabilities, official matchday, and date
10. Updates cumulative overperformance with current season partial data
11. Saves updated `data.json` and `fixtures.json`
12. Commits and pushes if anything changed

### Secrets required

| Secret | Where to set | Value |
|--------|-------------|-------|
| `FOOTBALL_DATA_API_KEY` | Repo > Settings > Secrets | Token from football-data.org (free tier, 10 req/min) |

### Monitoring

Check the Actions tab for run logs. Key lines to look for:

```
Fetching ll fixtures from football-data.org (PD)...
    Got 380 matches
    Calendar: 38 matchdays, 380 fixtures, 270 played
ll: 20 teams, GW 27 -> 27
Running MC simulation...
    MC: Alaves p10/p50/p90 = 42/48/54
    Added remaining fixtures: 16 per team
```

If "Added remaining fixtures: 0 per team" appears, there is a name mapping problem (see section 9).

---

## 2. New season setup

At the start of each season (typically August), the following steps are needed.

### Step A: Collect wage data

See section 3 below. This is the most manual step and must be done before anything else. Wage data is collected once per season, after the summer transfer window closes (typically early September). It is not updated mid-season.

### Step B: Update season URLs

In `update.py`, update the URLs dict to point to the new season CSVs:

```python
URLS = {
    'll': 'https://www.football-data.co.uk/mmz4281/2627/SP1.csv',
    'pl': 'https://www.football-data.co.uk/mmz4281/2627/E0.csv'
}
```

The URL pattern is `mmz4281/{YYNN}/{code}.csv` where YY and NN are the two-digit start/end year codes.

### Step C: Add wages to data.json

Once the first matchday results are available and update.py has created the season entries, add the `w` field for each team. This can be done by editing data.json directly or by temporarily hardcoding wages in update.py.

### Step D: Check promoted/relegated teams

Each season, 3 teams are promoted and 3 relegated in each league. The new team names must:
1. Match football-data.co.uk naming (what appears in their CSV)
2. Have entries in `API_NAME_MAP` if the football-data.org API uses a different name
3. Have wage data
4. Have crests (run the crest workflow — see section 4)

For newly promoted teams without Capology data, use estimates based on similar teams until official data appears.

### Step E: Run setup_season.py (optional)

```bash
python setup_season.py --season 26/27
```

This builds the fixture calendar and runs pre-season Monte Carlo simulations. If the daily update runs first, it will handle the fixture calendar automatically via the API.

### Step F: Verify

After the first daily run with the new season:
- Check that all 20 teams in each league have wage data (no "WARNING: only N wages" in logs)
- Check that remaining fixtures are found ("Added remaining fixtures: ~35 per team")
- Check that position probabilities look reasonable
- Check the live site to confirm the new season appears in dropdowns

---

## 3. Wage data collection

### Timing and frequency

Wage data is collected **once per season**, after the summer transfer window closes (early September). The model uses a single annual wage bill per team per season — this matches how the ordered logit was estimated. Mid-season updates are not needed: January transfers rarely move a club's total payroll by more than 5–10%, and the model is not sensitive to changes of that magnitude.

The only exception: if a newly promoted team had no Capology data at the start of the season and it becomes available later, the estimate can be replaced with the real figure.

### Sources

| Source | URL | Coverage | Notes |
|--------|-----|----------|-------|
| Capology | capology.com | Best for current + recent seasons | Annual gross wages by club. No CSV export; read from website. |
| FBref | fbref.com | Good historical coverage | Sources from Capology. Sometimes different aggregation. |

### Process

1. Navigate to Capology for each league:
   - La Liga: `capology.com/la-liga/payrolls/{season}/`
   - Premier League: `capology.com/premier-league/payrolls/{season}/`
2. Screenshot or copy the payroll table showing annual gross wages by club
3. Extract the data — manually transcribe or use Claude to read the screenshot
4. Units: La Liga in EUR millions, Premier League in GBP millions
5. Update the `w` field for each team in `data.json`

This takes approximately 20 minutes per league.

### What the `w` field represents

The annual gross wage bill for the entire first-team squad, in millions of the league's local currency (€M for La Liga, £M for Premier League). Base salary only. This is the figure Capology reports as the club's total annual payroll.

### Historical coverage

The dataset contains wage data for 13 seasons (2013/14–2025/26). Three team-seasons lack data: Espanyol 13/14, Espanyol 14/15, and Deportivo 14/15 — these are excluded from model estimation.

---

## 4. Crest management

Team crests are loaded from `crests.json`, built by `build_crests.py` which queries the football-data.org API.

### How it works

`build_crests.py` queries four competitions (La Liga PD, Segunda División SD, Premier League PL, Championship ELC) and maps team names to crest URLs. For historical teams no longer in these leagues, manual fallback URLs are hardcoded in `MANUAL_CRESTS`.

### Regenerating crests

Trigger the GitHub Actions workflow `build-crests.yml` manually from the Actions tab. It runs `build_crests.py`, which:
1. Queries the API for current team crests
2. Applies manual fallbacks for relegated/historical teams
3. Writes `crests.json`
4. Commits and pushes

Run this at the start of each season after promotion/relegation is confirmed.

### Adding a missing crest

If a team has no crest, add it to the `MANUAL_CRESTS` dict in `build_crests.py` with a direct URL to the crest image, then re-run the workflow.

---

## 5. Translation (i18n)

The app is fully bilingual (English/Spanish). All user-facing text is stored in `i18n.json` as key-value pairs where each value is `[english, spanish]`.

### Editing translations

`i18n.json` contains 289 keys. To edit:
1. Export to Excel for review (or edit JSON directly)
2. Update the values
3. Deploy with the updated `i18n.json`

### Adding new keys

When adding new features that require text:
1. Add the key to `i18n.json` with both language values
2. Reference it in the app code using `_t("key_name")`
3. For templates with variables, use `_tf("key_name", {var: value})`

### Conventions

- "Managerial Score" stays in English in both languages (it's a term of art)
- Hyphenated forms: "sobre-rendimiento" / "infra-rendimiento"
- The `_t()` function must never be used inside data access expressions (e.g. `p["1st"]` must use literal keys)

---

## 6. Custom domain

The site is hosted on GitHub Pages with the custom domain `footballbeyondmoney.uk`.

### DNS configuration

Four A records pointing to GitHub's servers plus a CNAME for www:

```
A     185.199.108.153
A     185.199.109.153
A     185.199.110.153
A     185.199.111.153
CNAME www → talfarouriarte-cloud.github.io
```

### GitHub Pages settings

- Repository: Settings > Pages > Custom domain: `footballbeyondmoney.uk`
- Enforce HTTPS: enabled (after SSL certificate is provisioned, usually within 1 hour of DNS setup)
- A `CNAME` file in the repo root may be needed if GitHub doesn't maintain it automatically

---

## 7. Data format reference

### data.json top-level structure

```json
{
  "model": {
    "laliga": {"beta": 0.4719, "theta1": -1.0404, "theta2": 0.2081},
    "pl":     {"beta": 0.676,  "theta1": -0.8358, "theta2": 0.2422}
  },
  "seasons":    {"ll": {...}, "pl": {...}},
  "bands":      {"ll": {...}, "pl": {...}},
  "pre":        {"ll": {...}, "pl": {...}},
  "cumulative": {"ll": {...}, "pl": {...}},
  "pos":        {"ll": {...}, "pl": {...}}
}
```

### seasons

```
seasons.ll["25/26"]["Barcelona"] = {
  "a": [3, 6, 9, ...],              // cumulative actual points after each game
  "e": [2.1, 4.3, 6.5, ...],        // cumulative expected points after each game
  "m": [                             // match-by-match detail
    ["Real Madrid", 1, 3, 2.1, 15], // [opponent, isHome, actualPts, expectedPts, officialGW]
    ...
  ],
  "w": 250,                          // annual wage bill (€M for ll, £M for pl)
  "r": [                             // remaining fixtures (current season only)
    ["Getafe", 1, 0.72, 0.18, 0.10, 28, "2026-03-15"],
    // [opponent, isHome, pWin, pDraw, pLoss, officialGW, date]
    ...
  ]
}
```

### bands and pre

```
bands.ll["Barcelona"] = {
  "p10": [2, 4, 7, ...],   // 10th percentile cumulative points per game
  "p50": [3, 6, 9, ...],   // median
  "p90": [3, 7, 11, ...]   // 90th percentile
}
```

`pre` has the same format but is computed from wages alone (pre-season, no actual results).

### cumulative

```
cumulative.ll["Barcelona"] = [
  76.1,                           // total extra points across all seasons
  13,                             // number of seasons
  0.155,                          // normalised overperformance
  [                               // season-by-season detail
    ["13/14", 200, 75.2, 87],    // [season, wage, expectedPts, actualPts]
    ...
  ]
]
```

### pos (position probabilities)

```
pos.ll["25/26"] = {
  "pre": {"Barcelona": {"1st": 0.66, "ucl": 0.99, "uel": 0.01, "ucol": 0, "mid": 0, "rel": 0}, ...},
  "cur": {"Barcelona": {"1st": 1.00, "ucl": 1.00, ...}, ...}
}
```

### fixtures.json

```json
{
  "ll": {
    "25/26": {
      "calendar": [
        {"gw": 1, "matches": [["Barcelona","Betis"], ...], "played": [true, ...], "dates": ["2025-08-16", ...]},
        ...
      ],
      "teams": ["Alaves", "At Madrid", ...]
    }
  },
  "pl": {...}
}
```

### i18n.json

```json
{
  "app_title": ["Football beyond money", "Fútbol más allá del dinero"],
  "tab_tracker": ["Season Tracker", "Seguimiento de temporada"],
  ...
}
```

### crests.json

```json
{
  "Barcelona": "https://crests.football-data.org/81.png",
  "Real Madrid": "https://crests.football-data.org/86.png",
  ...
}
```

---

## 8. External dependencies

### APIs and data feeds

| Service | What for | Auth | Rate limit | Cost |
|---------|----------|------|------------|------|
| football-data.co.uk | Match result CSVs | None | None | Free |
| football-data.org | Fixture calendar + crests | API key | 10 req/min | Free tier |
| Capology / FBref | Wage data | None (manual) | N/A | Free (website) |

### football-data.org API

- Endpoint: `GET https://api.football-data.org/v4/competitions/{code}/matches`
- La Liga: `PD`, Premier League: `PL`
- Auth: `X-Auth-Token: {key}` header
- Register: https://www.football-data.org/client/register

### Python dependencies (update.py, setup_season.py)

```
pandas numpy scipy requests
```

### Frontend CDN dependencies (index.html)

```
React 18.2.0
ReactDOM 18.2.0
PropTypes 15.8.1
Recharts 2.12.7
Tailwind CSS (cdn.tailwindcss.com)
```

---

## 9. Name mapping

Team names differ across three systems: football-data.co.uk (CSVs), football-data.org (API), and the app's internal names. Two dicts in `update.py` handle this:

- `NAME_MAP`: CSV name → internal name (e.g. "Nott'm Forest" → "Nottm Forest")
- `API_NAME_MAP`: API shortName → internal name

If a new team appears with an unmapped name, symptoms are: zero remaining fixtures in the logs, flat MC bands (p10=p50=p90), wrong "next match" on Home.

Fix: check the Action log for the actual name the API returned, add the mapping, re-run.

### Current internal names (25/26)

**La Liga**: Alaves, At Madrid, Ath Bilbao, Barcelona, Betis, Celta, Elche, Espanol, Getafe, Girona, Levante, Mallorca, Osasuna, Oviedo, Real Madrid, Sevilla, Sociedad, Valencia, Vallecano, Villarreal

**Premier League**: Arsenal, Aston Villa, Bournemouth, Brentford, Brighton, Burnley, Chelsea, Crystal Palace, Everton, Fulham, Leeds, Liverpool, Man City, Man United, Newcastle, Nottm Forest, Sunderland, Tottenham, West Ham, Wolves

---

## 10. Troubleshooting

### "Added remaining fixtures: 0 per team"
Name mapping problem. See section 9.

### MC simulation shows no variance (p10 = p50 = p90)
Same cause: remaining fixtures not found. Fix name mapping.

### "WARNING: only N wages for {league}"
The season entry doesn't have wage data for enough teams. Add `w` values for all 20 teams.

### Action fails with "API rate limit"
Free tier allows 10 requests per minute. The script makes 2 (one per league). Only a problem if running repeatedly in quick succession.

### Wrong "next match" on Home card
The `r` field is ordered by fixture calendar. Postponements or rescheduling may cause the wrong fixture to appear first. Re-running the Action fetches the latest calendar.

### football-data.co.uk CSV not available
At the very start of a season, the CSV may not exist. The Action logs "FAILED" and skips that league. Works once the first matchday results are published.

### Welcome screen keeps appearing
The welcome screen shows when the URL hash is empty. If it reappears unexpectedly, check that the hash is being preserved (e.g. not stripped by a redirect).

### Crests not loading
Check `crests.json` in the repo. If empty or corrupt, re-run the `build-crests.yml` workflow. The app degrades gracefully — missing crests are simply not shown.

### Translation missing
If a key shows as the raw key name (e.g. "tab_history"), it's missing from `i18n.json`. Add the key with both language values and redeploy.
