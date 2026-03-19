# Operations Guide — Football beyond money v3.0

## Table of contents

1. [Daily updates (automatic)](#1-daily-updates-automatic)
2. [New season setup](#2-new-season-setup)
3. [Wage data collection](#3-wage-data-collection)
4. [Crest management](#4-crest-management)
5. [Translation (i18n)](#5-translation-i18n)
6. [Custom domain & social sharing](#6-custom-domain--social-sharing)
7. [PWA and service worker](#7-pwa-and-service-worker)
8. [Data format reference](#8-data-format-reference)
9. [External dependencies](#9-external-dependencies)
10. [Name mapping](#10-name-mapping)
11. [Narrative system](#11-narrative-system)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Daily updates (automatic)

GitHub Actions runs `update.py` every day at 08:00 UTC. Trigger manually from Actions tab.

### What it does

1. Fetches fixture calendar from football-data.org API for all 6 leagues
2. Downloads latest match results CSV from football-data.co.uk (6 CSV files)
3. Recomputes expected points for all played matches using per-league ordered logit
4. Stores match dates from fixture calendar in each match entry (m[5])
5. Runs 10,000 MC simulations for remaining fixtures → p10/p50/p90 bands
6. Recalculates budget forecast using same match order as actual season
7. Computes position probabilities with per-league UCL/UEL/Conference/relegation spots
8. Generates bilingual narrative sentences per team (template system)
9. Builds remaining fixture list per team with W/D/L probabilities, matchday, date
10. Updates cumulative overperformance
11. Saves data.json and fixtures.json, commits if changed

### Budget forecast

The budget line uses deterministic expected points (pw×3 + pd per match), not MC median. Match order follows actual play order for played matches, calendar order for remaining.

### Secrets

| Secret | Where | Value |
|--------|-------|-------|
| `FOOTBALL_DATA_API_KEY` | Repo > Settings > Secrets | Token from football-data.org |

### League CSV codes

| League | Code | URL pattern |
|--------|------|------------|
| La Liga | SP1 | mmz4281/{YYNN}/SP1.csv |
| Premier League | E0 | mmz4281/{YYNN}/E0.csv |
| Serie A | I1 | mmz4281/{YYNN}/I1.csv |
| Bundesliga | D1 | mmz4281/{YYNN}/D1.csv |
| Ligue 1 | F1 | mmz4281/{YYNN}/F1.csv |
| Eredivisie | N1 | mmz4281/{YYNN}/N1.csv |

### Monitoring

Look for in the Action logs:
```
Processing ll (La Liga) 25/26...
  MC: Barcelona p10/p50/p90 = XX/XX/XX
  Added remaining fixtures: 16 per team
  ll: 20 narratives
```

---

## 2. New season setup

At each season start (August):

1. **Collect wages** (section 3) for all 6 leagues — once, after summer window closes
2. **Update CSV URLs** in update.py for each league
3. **Add wages** to data.json `w` field for all teams per league
4. **Check promoted/relegated** teams: name mapping, wages, crests
5. **Regenerate crests**: run `build-crests.yml` workflow
6. **Update European spots** if UEFA coefficients changed (LEAGUE_SPOTS in update.py + LEAGUES in index.html)
7. **Verify**: all teams have wages, fixtures found, probabilities sum correctly

---

## 3. Wage data collection

Collected **once per season** after summer window (early September). Not updated mid-season.

Sources: Capology (capology.com) or FBref (fbref.com). Units: €M for all leagues except £M for Premier League.

Coverage: 13 seasons (2013/14–2025/26). Three gaps: Espanyol 13/14–14/15, Deportivo 14/15.

---

## 4. Crest management

`crests.json` built by `build_crests.py`. Queries 12 competitions from football-data.org (7 work on free tier). 76 manual crests for historical teams. Run `build-crests.yml` workflow at season start. For missing crests: add to `MANUAL_CRESTS` dict in build_crests.py.

201 teams covered across La Liga, Segunda, Premier League, Championship, Serie A, Serie B, Bundesliga, 2. Bundesliga, Ligue 1, Ligue 2, Eredivisie, Eerste Divisie.

---

## 5. Translation (i18n)

332 keys in `i18n.json`. Each value: `[english, spanish]`. Use `_t("key")` or `_tf("key", {var:val})`.

Conventions:
- "Football beyond money" and "Managerial Score" stay English in both languages
- Hyphenated: "sobre-rendimiento"/"infra-rendimiento"
- Zone names: "Champions League" same in both; "Mid-table" → "Mitad de tabla"; "Relegation" → "Descenso"

---

## 6. Custom domain & social sharing

Domain: `footballbeyondmoney.uk` on GitHub Pages. DNS: 4 A records + CNAME www.

OG meta tags for WhatsApp/Twitter/LinkedIn. Preview image: `og-image.jpeg` (1200×630).

---

## 7. PWA and service worker

manifest.json + sw.js + icons 48–512px. Install button in footer and hamburger menu.

Service worker strategy:
- **Network-first**: all `.html` files, `data.json`, `fixtures.json`, `crests.json`, `i18n.json`
- **Cache-first**: images, icons, manifest (static assets)

This ensures HTML and data updates apply immediately without manual cache clearing.

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
pre.{lg}.TeamName = {
  p10: [int, ...],       // MC 10th percentile
  p50: [float, ...],     // Deterministic cumulative expected pts
  p90: [int, ...]        // MC 90th percentile
}
```

### Current bands
```
bands.{lg}.TeamName = {p10, p50, p90}  // MC-based, actual + simulated remaining
```

### Position probabilities
```
pos.{lg}.{season}.pre.TeamName = {1st, ucl, uel, ucol, mid, rel}
pos.{lg}.{season}.cur.TeamName = {1st, ucl, uel, ucol, mid, rel}
```
Note: `ucl` includes positions 1 through N_UCL (cumulative). Frontend subtracts `1st` for display.

### Narratives
```
narratives.{lg}.TeamName = {en: "...", es: "..."}
```

### fixtures.json
```
{lg: {season: {calendar: [{gw, matches, played, dates}, ...]}}}
```

---

## 9. External dependencies

| Service | What for | Auth | Cost |
|---------|----------|------|------|
| football-data.co.uk | Match CSVs (6 leagues) | None | Free |
| football-data.org | Calendar + crests | API key | Free tier |
| Capology/FBref | Wages | Manual | Free |

Python: pandas, numpy, scipy, requests. Frontend CDN: React 18.2.0, Recharts 2.12.7, Tailwind CSS.

---

## 10. Name mapping

`NAME_MAP` (CSV→internal) and `API_NAME_MAP` (API→internal) in update.py. Also `SAFE_REPLACE` for targeted replacements and `fix_name()` applied at DataFrame load.

Key mappings:
- Inter → Inter Milan, Milan → AC Milan, Verona → Hellas Verona
- Dortmund → Borussia Dortmund, M'gladbach → Monchengladbach
- Paris SG → PSG, PSV Eindhoven → PSV
- Nott'm Forest → Nottm Forest

**Critical**: Global string replace (`.replace()`) must never be used — it corrupts compound names (e.g. "Inter Milan" → "Inter AC Milan AC Milan"). Use `fix_name()` on the DataFrame instead.

---

## 11. Narrative system

`generate_narratives_all()` in update.py produces one bilingual sentence per team for the current season. Stored in `data.json` as `narratives.{lg}.{team}.{en|es}`.

### Template logic

Each narrative has two parts:

**Part 1 — Position statement** (6 variants by zone):
- Champion: "Projected 1st with a 65% chance of the title."
- UCL: "Projected 4th, in Champions League places (90% to qualify)."
- UEL/Conference/Mid-table/Relegation: similar patterns

**Part 2 — Context** (8 variants, pick most interesting):
1. Big rise across zones (≥3 positions + different zone)
2. Big fall across zones
3. Punching above weight (budget rank ≥5 lower than position)
4. Underperforming budget (budget rank ≥5 higher)
5. Moderate zone improvement
6. Moderate zone decline
7. Moderate budget over/underperformance (≥3)
8. In line with budget (default)

### Frontend

Home card reads `D.narratives[lg][team][_lang]`. Falls back to probability badges if narrative unavailable.

---

## 12. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Probabilities sum >100% | UCL includes champion | Fixed: display subtracts 1st from UCL |
| Team stuck on "not in league" | No selector in that view | Fixed: all not-in-league views have team dropdown |
| Old version showing on mobile | SW cache-first for HTML | Fixed: SW now network-first for .html |
| 0 remaining fixtures | Name mapping mismatch | Add to NAME_MAP/API_NAME_MAP in update.py |
| Flat MC bands (p10=p50=p90) | Same | Fix name mapping |
| Wrong relegation probabilities | Hardcoded 20-team slicing | Fixed: per-league LEAGUE_SPOTS in simulate_position_probs |
| Narratives missing | update.py not run after code update | Re-trigger GitHub Action |
| PSG vs Nantes as "closest match" | Filtering by single GW | Fixed: next 10 matches by date |
| Scroll stuck on team list (iPad) | Div scroll capture | Tracker uses native `<select>`; Overperformance uses scrollable div (works) |
| Welcome screen reappearing | Hash cleared | Check redirects |
