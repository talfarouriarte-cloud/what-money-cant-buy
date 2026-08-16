# Operations Guide — Football beyond money

## 0. Branches & data flow

- **`main`** = producción (GitHub Pages, footballbeyondmoney.uk). Recibe: (a) promociones `develop→main` con gate humano (promoción = deploy), (b) los commits diarios de datos de `update.yml` y (c) los commits de `crests.json` de `build-crests.yml`. Los workflows de producto operan sobre `main` (ADR-002, ADR-004) aunque el schedule corra desde `develop` por ser la rama default: el checkout lleva `ref: main` explícito.
- **`develop`** = rama de trabajo y default. Todo el pipeline de agentes opera solo aquí. Al arrancar cada épica se hace merge `main→develop` para partir de la realidad actual, datos incluidos (ADR-002).

## 1. Daily updates (automatic)

GitHub Actions runs `update.py` four times daily — crons at 00:00, 00:02, 06:01 and 08:00 UTC (redundant slots because GitHub may skip scheduled runs on free-tier repos). Commits land on `main`.

### What it does
1. Detects current season from date: **July 15+ = new season** (ADR-008; single derivation in `derive_season()`, `update.py`)
2. Loads wages from `all_wages.json` (missing teams filled from previous season; promoted teams get league minimum)
3. Fetches fixture calendar + match results from football-data.org API (real-time, minutes after final whistle). Guard (ADR-007): if a league's calendar payload doesn't match `CURRENT_SEASON`, that league is discarded and picked up by a later cron once published.
4. Downloads match results CSVs from football-data.co.uk as fallback (1-2 day delay). Guard (issue #79, twin of ADR-007 on the CSV path): the request uses `allow_redirects=False` and any status ≠ 200 discards the league; the body is then validated (`validate_csv_content`) so its `Div` column matches the requested league and the first `Date` falls in `CURRENT_SEASON`. This blocks football-data.co.uk's fuzzy-redirect to the "closest" file of another league and its HTML 300 bodies when the season's CSV doesn't exist yet. A discarded league logs one of two literals depending on the branch: `FAILED: status <n> (url <url>) — redirect/HTML rechazado` when status ≠ 200 (the 3xx fuzzy-redirect and the HTML 300), or `WARNING: contenido inválido para <lg> ... descartado` when a 200 body fails the league/season validation. In both cases the league is picked up by a later cron once the real CSV is published.
5. Computes expected points, MC bands, budget forecast, position probabilities, narratives
6. Runs diagnostic checks (budget line parallelism)
7. Commits updated `data.json` and `fixtures.json` to `main`

After every successful run, `build-crests.yml` is triggered automatically via `workflow_run` (ADR-010): `build_crests.py` is idempotent — it only fetches crests for teams in `data.json` ∪ current-season calendar that are missing from `crests.json`; no changes ⇒ no-op commit.

### Data source priority
1. **football-data.org API** (primary): scores available minutes after matches. 6 API calls, well within free tier limit (10/min).
2. **football-data.co.uk CSV** (fallback): updated Sunday/Wednesday nights. Used if API key missing or API fails **and** the downloaded CSV passes the league+season validation above (issue #79); otherwise the league is discarded, not ingested.

### Budget forecast
Both updated and budget p50 use deterministic expected value (`pw×3 + pd`). MC only for p10/p90 bands. Guarantees parallel projected lines.

### Monitoring
```
ll: 20 wages (from all_wages.json), min=14M
  MC: Alaves p10/p50/p90 = 34/39.1/44
  DIAG Alaves: played=28, MC slope=11.1, Budget slope=11.1, step mismatches=0
```

## 2. Season rollover (automatic + one manual step)

### What's automatic
- `update.py` advances to the new season on **July 15** (ADR-008; derived from date, never hardcoded)
- CSV URLs derived automatically from season
- Wages for returning teams filled from previous season until new wages uploaded
- Promoted teams get league minimum wage until new wages uploaded
- Leagues whose new calendar isn't published yet are skipped safely (ADR-007 guard) and picked up by the daily cron when they appear
- Crests for promoted teams: fetched automatically by the `workflow_run` chain (ADR-010) on the first update that sees the new calendar
- Frontend reads latest season from `data.json`

### What's manual (once per year)
1. **August 1st**: GitHub Action (`new-season.yml`) creates reminder Issue with wage checklist
2. **July 15 → September**: App already processes the new season with approximate wages (previous season + league min for promoted teams). Between July 15 and the real kickoff (~mid-August) the current season shows 0 played matches: calendar and pre-season bands are the content.
3. **September** (after transfer window closes): Update `all_wages.json` with accurate wage data:
   - Screenshot Capology tables for each league
   - Give to Claude to extract into JSON
   - Update the relevant season key in `all_wages.json`
   - Commit to repo (`main`)
   - All data recalculated automatically with accurate wages on next daily run
4. Check promoted/relegated teams: API→internal mapping in `name_map.json` (single source for name mapping and display names, ADR-009)

### Testing season transition
```bash
python test_season_transition.py --month 7 --year 2026
python test_season_transition.py --month 9 --year 2026
```

### Fallback chain for wages
1. Team wage in `all_wages.json` for current season
2. Team wage from previous season (auto-filled for missing teams)
3. League minimum wage (`_min`)
4. 20M (absolute last resort)

## 3. Wage data

### Source
`all_wages.json` — single source of truth. Structure:
```json
{
  "la_liga": {
    "25/26": {"Barcelona": 220, "Real Madrid": 288, ...},
    "24/25": {...}
  },
  "premier_league": {...},
  "serie_a": {...},
  "bundesliga": {...},
  "ligue_1": {...},
  "eredivisie": {...}
}
```

Units: €M for all leagues except £M for Premier League. Collected once per season from Capology.

### Adding new season
Add a new key to each league in `all_wages.json`:
```json
"26/27": {"Barcelona": 230, "Real Madrid": 295, ...}
```

## 4. Data format reference

### Match entry (m array)
```
[opponent, isHome(0/1), actualPts, expectedPts, officialGW, matchDate]
```

### Team season data
```
{
  "a": [cumulative pts array],
  "e": [cumulative expected array],
  "m": [match array],
  "w": wage (€M),
  "gd": goal difference,
  "r": [remaining fixtures with probabilities]  // current season only
}
```

### Budget bands (pre) and Current bands
p50 = deterministic, p10/p90 = MC percentile.

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Budget & updated lines not parallel | p50 methods differed | Fixed: both deterministic |
| DIAG shows step mismatches | MC vs deterministic rounding | ±1 per step is normal |
| Wrong team order at same points | No GD tiebreaker | Fixed: GD from FTHG/FTAG |
| Season shows wrong year | Hardcoded season | Fixed: auto-derived from date (`derive_season`, ADR-008) |
| No wages for new season | `all_wages.json` not updated | Update file, commit |
| 0 remaining fixtures | Name mapping mismatch | Add to `api_to_internal` in `name_map.json` |
| Production data stale but crons green | Cron committing to wrong branch | `update.yml` checkout must carry `ref: main` (ADR-002); schedule runs from default branch (`develop`) |
| A league missing after July 15 | Its new calendar not published yet | Normal (ADR-007 guard); daily cron picks it up when the API serves it |
| `FAILED: status <n> (url <url>) — redirect/HTML rechazado` in cron log | football-data.co.uk served a 3xx fuzzy-redirect (to another league's file) or an HTML 300 instead of the season's CSV (not published yet) | Normal (issue #79 guard, status ≠ 200 branch); daily cron picks it up when the real CSV appears |
| `WARNING: contenido inválido para <lg> ... descartado` in cron log | football-data.co.uk returned a 200 body that failed validation: another league's `Div` or a past-season date | Normal (issue #79 guard, body-rejected branch); daily cron picks it up when the real CSV appears |
| Tooltips stuck on iPad | Recharts pointer-events | Fixed: global touch handler |
| Results not updating | API key missing or expired | Check `FOOTBALL_DATA_API_KEY` secret in repo |
| GW X -> X (no new matches) | Source not updated yet | API: minutes; CSV: Sun/Wed night |
| "Using CSV (API unavailable)" | API failed or no key | Check Action logs for API error |

## 6. Staging / preview de develop (Vercel)

**Qué es**: `main` la sirve GitHub Pages (producción). Para probar `develop` en un dispositivo real ANTES de promover, se despliega un snapshot a Vercel — dominio distinto, así el service worker de producción no interfiere con la prueba.

- **Proyecto Vercel**: `wmcb-develop-preview` (id `prj_U84Z35xAWuzORYBAy50fGyzLHiAU`).
- **URL estable de pruebas**: `https://wmcb-develop-preview.vercel.app`
- **Token**: `VERCEL_TOKEN` en el fichero `Credenciales_` del proyecto de claude.ai (nunca en el repo).
- **Sin vínculo git**: cada deploy es una subida directa de ficheros por API. La URL estable solo se actualiza si el deploy va con `"target": "production"`; sin ese campo se genera una URL efímera de preview.

**Qué se sube**: los ficheros estáticos de la raíz de `develop` que consume el frontend (`index.html`, `sw.js`, `i18n.json`, `crests.json`, `manifest.json`, iconos, `header-bg.jpeg`). **`data.json` NO se sube**: el `index.html` tiene fallback a `https://footballbeyondmoney.uk/data.json` y carga datos reales de producción.

**Deploy por API** (lo ejecuta el Architect desde sesión, con OK del humano):

```bash
# Para cada fichero: {"file": "<nombre>", "data": "<base64>", "encoding": "base64"}
curl -s -X POST "https://api.vercel.com/v13/deployments" \
  -H "Authorization: Bearer $VERCEL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "wmcb-develop-preview",
       "project": "wmcb-develop-preview",
       "target": "production",
       "files": [ ...ficheros en base64... ]}'
```

**Cómo probar en iPad**: abrir la URL estable en Safari. Si una versión anterior de la preview se queda cacheada por su propio SW, abrir en pestaña privada o borrar datos del sitio `vercel.app` — el SW de la preview tiene scope solo en ese dominio y no toca footballbeyondmoney.uk.

**Verificación rápida de qué versión sirve la preview**: `curl -s https://wmcb-develop-preview.vercel.app/sw.js | head -1` → debe mostrar el `CACHE_NAME` del snapshot subido.
