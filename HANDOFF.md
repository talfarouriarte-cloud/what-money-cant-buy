# Football beyond money — Redesign HANDOFF
_Para continuar en un chat nuevo. Actualizado: 2026-07-13_

6. ✅ HECHO (2026-07-13) Paridad final con original: (a) drag-scrub táctil en Matches (touchmove con preventDefault vía listener no-pasivo en wrap, tooltip sigue el dedo, lift fija; isTouchDev suprime handlers de mouse); (b) auto-highlight + pin del próximo partido del equipo seleccionado al montar Matches (outline ámbar, data-cell="h|a" para localizar celda); (c) StaleBanner (primitives.jsx, meta.wage_status) en Matches y Data; (d) THTip tap-tooltips (primitives.jsx, uno abierto a la vez) en cabeceras de Predictions y tabla de Tracker, claves tip_*; (e) GoatCounter en dev.html + build. Todo pendiente de prueba en despliegue real (dominio footballbeyondmoney.uk).

## OJO — regenerar index.html tras editar src/
`index.html` es un build (pre-transpilado). Tras cualquier edición en `src/*.jsx` / `styles.css` / `data.js`, REGENERAR con el run_script de build (Babel standalone, preset react, wrap IIFE + Object.assign(window, fns), inline styles+data). `dev.html` es la shell modular para desarrollo. `original-reference.html` = app original de GitHub (referencia, no tocar). CUIDADO: `github_copy_files` de `index.html` PISA el build (ya pasó una vez).

## Qué es esto
Rediseño de la app real (repo `talfarouriarte-cloud/what-money-cant-buy`). Dirección visual aprobada: **Stadium Paper** (papel cálido, acento terracota `#C2492F`, display Bricolage Grotesque, mono JetBrains, UI system stack). Nav reagrupada en 5 destinos: **Club / Season / Form / Legacy / Model** con sub-vistas segmentadas. Mapea los `tab=` antiguos (incl. `explorer`→overperformance) para que los enlaces no rompan.

## Arquitectura de archivos
- `index.html` — shell: carga React 18.3.1 + Recharts UMD + Babel, luego `data.js`, `styles.css`, y los `.jsx` en orden.
- `data.js` — capa de datos + i18n. **Hace fetch en runtime del data.json REAL** (`footballbeyondmoney.uk/data.json`, fallback GitHub raw). NO hay síntesis. Expone `window.__FBM.data`, `FBM_LEAGUES`, `FBM_ZONES`, `FBM_probs` (ordered-logit real), `FBM_I18N`, `_t`/`_tf`/`_lang`/`FBM_setLang`.
- `src/app.jsx` — Header (pickers lg/team/sn + LangToggle), TabStrip/BottomBar (nav 5 grupos, `GROUPS`), routing por hash, Footer.
- `src/primitives.jsx` — Crest (imágenes reales de crests.json + fallback monograma), LeagueSelector, SeasonStepper, FormDots, ZoneBar, InfoNote, **AboutTab** (acordeón "About this tab"), MatchScoreCell.
- `src/Home.jsx` — 5 tarjetas narrativas.
- `src/Tracker.jsx` — Points + Position views.
- `src/tabs.jsx` — Predictions, Matches, H2H, BadRun, Overperformance, Calculator, Methodology, Data, History.

## Forma REAL de data.json (verificado, crítico)
- `m[]` = `[opp, isHome(1/0), ptsActual, ptsExp, gw, "YYYY-MM-DD"]` — **NO hay marcador ni goles** (solo `gd` por temporada). Solo partidos jugados.
- `r[]` (próximos) = `[opp, isHome, pW, pD, pL, gw, date]`.
- Claves top-level: `seasons, bands, pre, pos, cumulative, model, meta, narratives, currentSeason`.
- `bands[lg][team]` = updated forecast `{p10,p50,p90}` (arrays por GW). `pre[lg][team]` = budget forecast igual.
- `pos[lg][sn]` = `{cur, pre, hist}`; probs con claves `1st, ucl(cumulativo, incluye 1st), uel, ucol(=Conference), mid, rel`. `hist[i]={gw, probs{team:{...,p50}}}`.
- `cumulative[lg][team]` = `[?, ?, ?, seasonsArray]` donde cada entrada `[season, ?, expPts, actPts]`.
- `model[lg]` = `{beta, theta1, theta2}`. `meta.wage_status[lg][sn]` = "stale" → banner en Data.
- `narratives[lg][team]` = `{en, es}`.
- Zonas de gráfico Position: constante `FBM_ZONES[lg]` (champion/ucl/uel/conf/rel), NO derivar de LEAGUES.

## HECHO (todas las vistas corren sobre data.json real)
- Nav 5 grupos + mapeo tab= antiguos; crests reales; tema Stadium Paper en styles.css.
- Home (5 cards, arregla 38→totalRounds para ligas de 18).
- Tracker Points (lee `pre`/`bands` reales, dots por resultado) + Position (rank por GW + `pos.hist` p50 + zonas).
- Predictions: lee `pos` precomputado (SIN Monte Carlo en navegador), partición 1st/UCL(2-4)/UEL/Conf/Mid/Rel, budget expandible, drop de evolución desde `pos.hist`.
- Matches: matriz por wage, dot resultado / % sombreado, contorno próxima jornada, tooltip inspección (hover+pin).
- H2H: `FBM_probs` real, pill table model vs histórico, chart acumulado.
- Run Evaluator: funnel acumulado (±0.674σ/±1.88σ, σ=1.58), veredicto "1 en N", controles ventana, tabla.
- Overperformance: 3 métricas reales (extra pts / normalized / Management Score) desde `cumulative`, ventanas 10/5/3, sidebar + charts.
- Calculator: sliders wage (max por liga) + pick club + swap, `FBM_probs`, exp pts, ratio log2.
- History: distribución W/D/L vs media liga, filtros venue + periodo.
- Methodology: tabla params por liga (β/θ₁/θ₂ reales), ecuación, métricas, paper+contacto.
- Data: banner stale desde `meta.wage_status` + wage evolution chart.
- i18n EN/ES: `_t`/`_tf` sobre i18n.json, LangToggle (header+footer, reload-based), AboutTab bilingüe en las 11 vistas, nav bilingüe (`GROUPS` con claves `tab_*` + `GROUP_LABELS`).

## PENDIENTE (en orden) — ver todo list
1. ✅ HECHO (2026-07-13): microlabels revertidos al copy original vía `_t()`/`_tf()` en las 11 vistas + header/footer/bootloader. Cambios estructurales asociados: Home cards ahora usan `card_howis/card_next(→h2h)/card_mgmt/card_run(last5/last10)/card_matches/card_ahead(→predictions, badges de zona ≥5% desde pos.cur)`; Methodology reescrita con `meth_*` completos; Data usa `wage_stale_*`, `data_*`; BadRun usa `actual_vs_expected`+`run_verdict_short`+`roughly_1_in_n`. Textos inventados sin clave original: eliminados. Nota: quedan funciones muertas en tabs.jsx (ProjectedTable/ProbPill/MatchRow, no renderizadas) — borrar en la consolidación final.
2. Re-verificar EN/ES en todas las vistas contra claves reales (recorrer con `lang=es`). ✅ HECHO: claves usadas (216) todas presentes con ES; placeholders EN/ES idénticos; vistas verificadas en ES. **Bugfix**: regex de routing aceptaba solo `[a-z]` → `#tab=h2h` caía en Home; corregido a `[a-z0-9]`.
2c. Auditoría móvil ✅ CERRADA (2026-07-13): todas las 12 tabs miden docW=390 a 390px (incl. Overperformance y H2H, re-verificado tras resize). Harness `mobile-test.html` BORRADO.
3. Welcome screen (hash vacío) ✅ HECHO: `Welcome` en app.jsx (pickers lang/league/team + hero `header-bg.jpeg` con overlay navy, claves `select_language/league/team/start`), estilos `.welcome*` en styles.css. Persistencia hash: helpers `hashGet`/`hashSet` (merge, pushState); `lg/sel/sn` se leen del hash al cargar y se escriben al cambiar; `setTab` ya no pisa los demás params; `lang` se conserva.
3b. ✅ Feedback usuario (2026-07-13): restaurada semántica ORIGINAL de inspección: (a) Matches — heatmap de probabilidad en TODAS las celdas (fórmula original rgba verde/rojo/ámbar por prob del modelo, dot encima en jugados, % home-win en no jugados) — antes solo se tintaban no jugados y con la 25/26 completa no se veía nada; (b) MatchTip = original (equipos+crests, salarios, fecha, W/D/L% del modelo siempre, y en jugados `actual_vs + pts (exp x.x)`, border-left por resultado); (c) tooltip Tracker Points (`ptsTip`) = original (fixture+GW+letra resultado, salarios, fecha, actual/projected_final/range/expected/budget_forecast, W/D/L desde r[] o recomputado, línea `game: Xpts (exp, ±)`; multi-equipo: `Team: pts | Proj | rango`); (d) tooltip Run Evaluator (`runTip`) = original (fixture, salarios, acumulado actual/expected/±, resultado + W/D/L% del modelo). CSS `.charttip` añadido. (e) Tracker Position = original: línea de proyección p50 restaurada (interpolación lineal rank actual → `pos.cur[team].p50`, seed en último GW jugado para conectar con la línea real, mismo tono al 45%); línea de evolución final-p50 ahora naranja discontinua y SOLO single-team; línea actual en color de equipo; tooltip `posTip` original (`Position: 4th | p50 projection | Final p50`, ordinales st/nd/rd/th o º en ES).
3. Welcome screen (hash vacío): pickers lang/league/team + hero `header-bg.jpeg`; persistencia hash lg/sel/sn/lang.
4. ✅ HECHO (2026-07-13) Comportamientos globales, semántica copiada del original (index.html l.1638-1703 + sw.js):
   - Swipe entre sub-vistas del grupo activo (umbral |dx|≥120, dt≤400, |dy|≤0.35|dx|; ignora recharts-surface/chart-wrap/TABLE/SELECT/INPUT; anim slide-left/right + vibrate 15ms). En app.jsx.
   - Pull-to-refresh (damping 0.5, cap 60px, umbral 60 → location.reload(); `.ptr-bar` con pull_refresh/release_refresh). En app.jsx + styles.css.
   - PWA: `sw.js` (adaptado del original: rutas relativas, network-first json/html/jsx/data.js, cache-first resto), registro en index.html, manifest.json saneado (start_url/scope `./`, solo iconos existentes 192/512, theme_color #C2492F), metas apple/theme-color.
   - Install prompt: botón en Footer si !standalone && (beforeinstallprompt || iOS); iOS → alert(ios_install_alert); claves install_app.
   - Hash params br/ex/h2a/h2b/om/ow: ya estaban cubiertos (verificado). console.log de debug en Overperformance eliminados.
   NOTA: sw/manifest no comprobables en el preview (iframe); probar en despliegue real.
5. ✅ HECHO (2026-07-13) Consolidación final: `index.html` ahora es un solo archivo pre-transpilado (sin Babel runtime): styles.css + data.js + los 6 .jsx transpilados inline (Babel standalone en build, preset react). `test.html` descartado por decisión del usuario. La shell modular vive en `dev.html` (carga src/*.jsx con Babel) — **editar siempre src/*.jsx / styles.css / data.js y regenerar index.html** (transpilar con Babel preset react e inline, ver run_script del 2026-07-13). Funciones muertas (ProjectedTable/ProbPill/MatchRow) borradas de tabs.jsx. sw.js → fbm-v2, ASSETS sin los archivos ya inlined.

## Reglas del proyecto (del usuario/arquitecto)
- NO tocar principios de diseño del original que no se pidió cambiar (sombras por probabilidad + dot en Matches, tooltips de inspección, etc.).
- NO cambiar copys; usar los de i18n.json/data.json.
- CSS custom (no Tailwind). i18n con tags/claves.
- data.json real siempre; nunca síntesis.

## Deliverables Fase 1 (referencia, no tocar)
`Phase 1 - Inventory.html` (inventario completo + claves i18n por vista), `Phase 1 - Directions.html`, `Phase 1 - Stadium Home.html`. `PLAN-RESTANTE.md` histórico.
