## Dominio de este repo


- **Qué es**: dashboard público de rendimiento futbolístico ajustado por masa salarial (Football beyond money) — visión, principios y ley estructural en `spec.md`; decisiones en `decisions.md`.
- **Rama base**: `develop`. **Rama de producción**: `main` (la sirve GitHub Pages; solo promoción humana y datos del cron — ADR-002).
- **Comandos**: chequeo estático `python3 -m py_compile <script>` + `node --check` sobre JS extraído; no hay suite de tests todavía (ADR-003 fija el suelo del CI; los tests que crees los corres fichero a fichero con `python3 <ruta>`).
- **Zonas de rigor especial** (espejo de spec §3): núcleo de modelo en `update.py` (nada altera resultados numéricos salvo mandato explícito del issue); `all_wages.json` (jamás lo modifica un agente); mapeo de nombres de equipo (prohibido replace global — tablas de `update.py`).
- **Ficheros que NUNCA toca un agente**: `.github/workflows/*` (human-execute, siempre), `data.json`, `fixtures.json`, `all_wages.json`, `CNAME`, `What money cant buy.pdf`.
- **Reglas de supervivencia**:
  1. Todo cambio de `index.html` exige bump de `CACHE_NAME` en `sw.js` — sin bump, los usuarios no reciben nada (el CI lo bloquea).
  2. Todo string visible nuevo entra como clave de `i18n.json` con par `[en, es]` completo — nunca hardcodeado.
  3. La app es `React.createElement` puro, sin JSX ni build: no introduzcas sintaxis que exija transpilación.
  4. Temporadas siempre derivadas, jamás hardcodeadas (spec §3bis.5).
