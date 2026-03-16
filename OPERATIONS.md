# Operations Guide — Football beyond money v2.0

## Table of contents

1. [Daily updates (automatic)](#1-daily-updates-automatic)
2. [New season setup](#2-new-season-setup)
3. [Wage data collection](#3-wage-data-collection)
4. [Crest management](#4-crest-management)
5. [Translation (i18n)](#5-translation-i18n)
6. [Custom domain & social sharing](#6-custom-domain--social-sharing)
7. [PWA and app installation](#7-pwa-and-app-installation)
8. [Data format reference](#8-data-format-reference)
9. [External dependencies](#9-external-dependencies)
10. [Name mapping](#10-name-mapping)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Daily updates (automatic)

GitHub Actions runs `update.py` every day at 08:00 UTC. Trigger manually from Actions tab.

### What it does

1. Fetches fixture calendar from football-data.org API (dates, matchdays, played status)
2. Downloads latest match results CSV from football-data.co.uk
3. Recomputes expected points for all played matches using ordered logit
4. Stores match dates from fixture calendar in each match entry (m[5])
5. Runs 10,000 MC simulations for remaining fixtures → p10/p50/p90 bands
6. Recalculates budget forecast: deterministic expected points using same match order as actual season (played matches first, then remaining in calendar order)
7. Computes position probabilities for budget and updated forecasts
8. Builds remaining fixture list per team with W/D/L probabilities, matchday, date
9. Updates cumulative overperformance
10. Saves data.json and fixtures.json, commits if changed

### Budget forecast

The budget line uses deterministic expected points (pw×3 + pd per match), not MC median. This makes it visually parallel to the actual expected line — both zigzag the same way based on opponent strength. The p10/p90 bands remain MC-based. Match order follows actual play order for played matches, calendar order for remaining.

### Secrets

| Secret | Where | Value |
|--------|-------|-------|
| `FOOTBALL_DATA_API_KEY` | Repo > Settings > Secrets | Token from football-data.org |

### Monitoring

Look for in the Action logs:
```
Recalculating budget bands with current calendar...
Budget: Barcelona p10/p50/p90 = XX/XX/XX
Added remaining fixtures: 16 per team
```

---

## 2. New season setup

At each season start (August):

1. **Collect wages** (section 3) — once, after summer window closes
2. **Update URLs** in update.py: `mmz4281/{YYNN}/SP1.csv` and `E0.csv`
3. **Add wages** to data.json `w` field for all 20 teams per league
4. **Check promoted/relegated** teams: name mapping, wages, crests
5. **Regenerate crests**: run `build-crests.yml` workflow
6. **Verify**: all teams have wages, fixtures found, probabilities reasonable

---

## 3. Wage data collection

Collected **once per season** after summer window (early September). Not updated mid-season.

Sources: Capology (capology.com) or FBref (fbref.com). Navigate to payroll page, screenshot or copy table. Units: €M (La Liga), £M (Premier League).

13 seasons in dataset (2013/14–2025/26). Three gaps: Espanyol 13/14–14/15, Deportivo 14/15.

---

## 4. Crest management

`crests.json` built by `build_crests.py`. Run `build-crests.yml` workflow at season start. For missing crests: add to `MANUAL_CRESTS` dict.

---

## 5. Translation (i18n)

308 keys in `i18n.json`. Each value: `[english, spanish]`. Use `_t("key")` or `_tf("key", {var:val})`.

Conventions: "Football beyond money" and "Managerial Score" stay English in both languages. Hyphenated: "sobre-rendimiento"/"infra-rendimiento".

---

## 6. Custom domain & social sharing

Domain: `footballbeyondmoney.uk` on GitHub Pages. DNS: 4 A records + CNAME www.

OG meta tags for WhatsApp/Twitter/LinkedIn. Preview image: `og-image.jpeg` (1200×630). If preview doesn't show, use Facebook debugger to scrape again.

---

## 7. PWA and app installation

manifest.json + sw.js + icons 48–512px. Install button in footer and hamburger menu.

- **Android**: native install prompt or browser menu
- **iOS**: shows instructions (Share → Add to Home Screen)
- **Desktop**: browser address bar prompt

Service worker: network-first for data.json/fixtures.json, cache-first for everything else.

---

## 8. Data format reference

### Match entry (m array)
```
[opponent, isHome(0/1), actualPts, expectedPts, officialGW, matchDate]
```

### Remaining fixtures (r array)
```
[opponent, isHome(0/1), pWin, pDraw, pLoss, officialGW, matchDate]
```

### Budget bands (pre)
```
pre.ll.TeamName = {
  p10: [int, ...],       // MC 10th percentile (38 values)
  p50: [float, ...],     // Deterministic cumulative expected pts
  p90: [int, ...]        // MC 90th percentile
}
```

### Current bands
```
bands.ll.TeamName = {p10, p50, p90}  // MC-based, actual results + simulated remaining
```

### fixtures.json
```
{lg: {season: {calendar: [{gw, matches, played, dates}, ...]}}}
```

---

## 9. External dependencies

| Service | What for | Auth | Cost |
|---------|----------|------|------|
| football-data.co.uk | Match CSVs | None | Free |
| football-data.org | Calendar + crests | API key | Free tier |
| Capology/FBref | Wages | Manual | Free |

Python: pandas, numpy, scipy, requests. Frontend CDN: React 18.2.0, Recharts 2.12.7, Tailwind CSS.

---

## 10. Name mapping

`NAME_MAP` (CSV→internal) and `API_NAME_MAP` (API→internal) in update.py.

**La Liga 25/26**: Alaves, At Madrid, Ath Bilbao, Barcelona, Betis, Celta, Elche, Espanol, Getafe, Girona, Levante, Mallorca, Osasuna, Oviedo, Real Madrid, Sevilla, Sociedad, Valencia, Vallecano, Villarreal

**Premier League 25/26**: Arsenal, Aston Villa, Bournemouth, Brentford, Brighton, Burnley, Chelsea, Crystal Palace, Everton, Fulham, Leeds, Liverpool, Man City, Man United, Newcastle, Nottm Forest, Sunderland, Tottenham, West Ham, Wolves

---

## 11. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 0 remaining fixtures | Name mapping | Add to API_NAME_MAP in update.py |
| Flat MC bands (p10=p50=p90) | Same | Fix name mapping |
| No dates in tooltips | update.py without date_lookup | Deploy latest update.py, run Action |
| Budget line not parallel | Old update.py | Deploy version with det_cum in recalculate_budget_bands |
| Match grid freezing | Hover causing re-renders | Fixed in v2.0 (hover only updates tooltip) |
| Touch not working | Synthetic mouse events | Fixed in v2.0 (isTouchDev guard) |
| Scroll stuck on grid | preventDefault too broad | Fixed in v2.0 (only on .grid-cell elements) |
| Welcome screen reappearing | Hash cleared | Check redirects |
| Install button not showing | Browser-dependent | Android: multiple visits. iOS: instructions shown instead. |
