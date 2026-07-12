---
name: pipeline-map
description: Schematic map of this repo's agent pipeline instance. Load at the start of any process-review or pipeline-design session. Update in the SAME commit as any pipeline change.
---

# Pipeline map — what-money-cant-buy

**Synced:** 2026-07-12 (Architect) · **Framework:** agent-pipeline@main (modo mono-operador — los 5 stubs pinean `@main`; la subida humana al central es el despliegue; tags = hitos documentados con release notes, cortados tras rodaje real, ADR-219·R·2 finplan)

Cambios de framework 2026-07-12 (process-proposals del repo de origen, vía vendored sync + workflows @main): Reviewer jamás da LGTM sobre CI completado en rojo (#1269); Creator recupera literales must-copy del body RAW y publica huella `pre-reviewer:` en cada PR (#1278/#1259); Auditor aterriza el archivo de epic-context directamente en la rama por defecto (#1277); Watchdog con fast-path de CI rojo atribuible, marcador `watchdog-ci-attributable` (#1268); process-reviewer publica-antes-de-commitear con chequeo de integridad y señal determinista de fallo (#1258).

## Instance parameters

| Input | Valor |
|---|---|
| default_branch | `develop` |
| ci_workflow_name | `CI` (job `gate`, ADR-003) |
| epic_label | `epica` |
| runner | `ubuntu-latest` (repo público: GitHub-hosted gratis; elimina la clase de fallo billing-silencioso de MIGRATION §5) |
| modelos (creator/reviewer/resolve/process) | defaults del stub (opus-4-8 / opus-4-8 / opus-4-8 / fable-5) |
| caps (bot comments / ronda / vida) | creator_max_turns **100** (talla consciente, no default); bot_comment_cap 8; partial caps default (3/6) |

## Repo-specific additions

- Workflows de PRODUCTO fuera de supervisión del pipeline: `update.yml`, `new-season.yml`, `build-crests.yml` (ADR-004). Corren sobre `main`.
- CI propio de cinco checks (ADR-003): JSONs válidos, py_compile, completitud i18n, node --check del JS inline, guardia de SW en PRs.
- Producción = `main` servida por GitHub Pages; promoción develop→main = deploy (ADR-002). Merge main→develop al arrancar cada épica.
- Sin skills de capa 3 aún; nacerán del rodaje.

## Known local failure classes

Las del central aplican; ninguna local todavía.
