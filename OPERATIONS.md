# Operations Guide — Football beyond money v3.1

## 1. Daily updates (automatic)

GitHub Actions runs `update.py` twice daily at 06:00 and 08:00 UTC (dual cron for reliability — GitHub may skip scheduled runs on free-tier repos).

### What it does
1. Detects current season from date (Aug+ = new season, always advances)
2. Loads wages from `all_wages.json` (missing teams filled from previous season; promoted teams get league minimum)
3. Fetches fixture calendar + match results from football-data.org API (real-time, minutes after final whistle)
4. Downloads match results CSVs from football-data.co.uk as fallback (1-2 day delay)
5. Computes expected points, MC bands, budget forecast, position probabilities, narratives
6. Runs diagnostic checks (budget line parallelism)
7. Commits updated `data.json` and `fixtures.json`

### Data source priority
1. **football-data.org API** (primary): scores available minutes after matches. 6 API calls, well within free tier limit (10/min).
2. **football-data.co.uk CSV** (fallback): updated Sunday/Wednesday nights. Used if API key missing or API fails.

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
- `update.py` always advances to the new season in August (derived from date)
- CSV URLs derived automatically from season
- Wages for returning teams filled from previous season until new wages uploaded
- Promoted teams get league minimum wage until new wages uploaded
- Frontend reads latest season from `data.json`

### What's manual (once per year)
1. **August 1st**: GitHub Action creates reminder Issue with checklist
2. **August**: App already processes new season matches with approximate wages (previous season + league min for promoted teams). Results and rankings work but expected points are approximate.
3. **September** (after transfer window closes): Update `all_wages.json` with accurate wage data:
   - Screenshot Capology tables for each league
   - Give to Claude to extract into JSON
   - Update the relevant season key in `all_wages.json`
   - Commit to repo
   - All data recalculated automatically with accurate wages on next daily run
4. Check promoted/relegated teams: name mapping in `update.py`, crests
5. Run `build-crests.yml` workflow for new team crests

### Testing season transition
```bash
python test_season_transition.py --month 8 --year 2026
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
| Season shows wrong year | Hardcoded season | Fixed: auto-derived from date |
| No wages for new season | `all_wages.json` not updated | Update file, commit |
| 0 remaining fixtures | Name mapping mismatch | Add to NAME_MAP in update.py |
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
