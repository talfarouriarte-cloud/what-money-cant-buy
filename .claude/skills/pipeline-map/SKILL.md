---
name: pipeline-map
description: Schematic map of this repo's agent pipeline instance. Load at the start of any process-review or pipeline-design session. Update in the SAME commit as any pipeline change.
---

# Pipeline map — what-money-cant-buy

**Synced:** 2026-07-11 (alta Fase C, Architect) · **Framework:** agent-pipeline@v1 (vendored@f100499+dc0161f)

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
