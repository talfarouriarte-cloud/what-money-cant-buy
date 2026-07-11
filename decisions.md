# decisions.md — índice de ADRs

<!-- Formato verificado por scripts/adr-lint.mjs con adr-lint.config.json
(volumen único = este fichero, reglas estrictas desde ADR-001). -->

- [ADR-001](#adr-001-2026-07-11--fundación-proyecto-existente-entra-en-desarrollo-agéntico) — Fundación: proyecto existente entra en desarrollo agéntico
- [ADR-002](#adr-002-2026-07-11--estructura-de-ramas-developmain) — Estructura de ramas develop/main
- [ADR-003](#adr-003-2026-07-11--ci-qué-materializa-ci-verde) — CI: qué materializa `ci-verde`
- [ADR-004](#adr-004-2026-07-11--coexistencia-de-workflows-de-producto-y-de-pipeline) — Coexistencia de workflows de producto y de pipeline

## ADR-001 (2026-07-11) — Fundación: proyecto existente entra en desarrollo agéntico

### Contexto

`what-money-cant-buy` (Football beyond money, `footballbeyondmoney.uk`) existe y está en producción desde marzo de 2026 (v1.0→v3.5.3), desarrollado hasta hoy de forma manual/conversacional, sin spec formal ni registro de decisiones. Este ADR marca el cambio de régimen.

### Decisión

Decisión del propietario, verbatim:

> ADR 1 es que el proyecto fue creado según el spec y que empezamos ahora una nueva fase con desarrollo agenrico con las decisiones que estamos tomando (formalizar spec, crear adr, etc)

Se formaliza: (1) la app existente queda descrita retroactivamente por `spec.md` (commit `99727a5`), que pasa a ser la fuente canónica de visión, principios, stack, zonas de rigor y fronteras; (2) desde este ADR el desarrollo se realiza bajo el pipeline de agentes (`agent-pipeline`), con spec citable, ADRs en este fichero verificados por `adr-lint`, e issues como contratos cerrados.

### Razón

El desarrollo manual funcionó para construir el producto pero no deja rastro citable: ninguna decisión previa a este ADR es derivable por un agente. Formalizar spec+ADRs es el prerequisito del contrato de consumidor del pipeline.

### Alternativas descartadas

Reconstruir retroactivamente ADRs de las decisiones históricas (modelo, stack, PWA…): coste alto, valor bajo — la spec ya captura el estado resultante, y las decisiones vivas se registrarán cuando se toquen.

### Coste de revertir

Trivial en lo documental; el compromiso real es de proceso: abandonar el pipeline devolvería el repo al régimen manual sin pérdida de código.

## ADR-002 (2026-07-11) — Estructura de ramas develop/main

### Contexto

Hasta hoy el repo opera con `main` única, servida en producción por GitHub Pages. El pipeline de agentes exige una rama de trabajo default separada de producción (MIGRATION.md A0). Además, `update.yml` commitea `data.json`/`fixtures.json` a `main` varias veces al día — el diseño debe evitar que esos commits diverjan las ramas de forma conflictiva.

### Decisión

`develop` es la rama de trabajo y default: todo el pipeline (issues, PRs de agentes, CI, merges) opera solo ahí. `main` es producción: la sirve Pages y solo recibe (a) promociones `develop→main` por merge con gate humano — promoción = deploy — y (b) los commits de datos de `update.yml`, que sigue apuntando a `main` para que el sitio vivo tenga datos frescos. Los agentes no tocan `data.json`/`fixtures.json` (spec §3), de modo que los commits de datos en `main` no pueden colisionar con el trabajo en `develop`. Al arrancar cada épica se hace merge `main→develop` para que los agentes partan de la realidad actual (datos incluidos). Con esta estructura operativa, `test.html` se elimina (spec §3bis, nota) y la regla de entrega dual muere.

### Razón

Es el mecanismo de staging con coste cero: sin servidor, sin entorno duplicado — la promoción es el deploy. Mantener los datos en `main` preserva la frescura del sitio sin acoplar el cron al trabajo de agentes.

### Alternativas descartadas

- `update.yml` commiteando a ambas ramas: duplica escrituras y crea dos historias de datos.
- Datos commiteados a `develop` y promocionados: el sitio vivo tendría datos con días de retraso — inaceptable para un dashboard que presume de resultados en minutos.
- Mantener `test.html` como staging: no da historia, ni CI, ni rollback; era el sucedáneo de esto.

### Coste de revertir

Trivial en git (borrar rama, revertir default); el coste real sería re-acoplar los workflows del pipeline si ya están anclados a `develop` — media hora de stubs.

## ADR-003 (2026-07-11) — CI: qué materializa `ci-verde`

### Contexto

El repo no tiene suite de tests (`test_season_transition.py` es un simulador diagnóstico sin asserts). El gate de merge del pipeline exige un hecho verde materializado (MIGRATION.md A3). Hay que decidir qué verifica ese verde.

### Decisión

CI único (`ci.yml`, job `gate`) sobre `develop` con cinco checks, todos derivados de ley de spec:

1. **JSONs válidos**: todo `*.json` de raíz parsea (protege los generados y `all_wages.json`).
2. **Sintaxis Python**: `py_compile` de los cuatro scripts.
3. **Completitud i18n**: toda clave de `i18n.json` es un par `[en, es]` con ambos no vacíos (mecaniza spec §2.5 / §3bis.6).
4. **Sintaxis JS**: los `<script>` inline de `index.html` pasan `node --check` (la app es `React.createElement` puro, sin JSX ni build — es chequeable).
5. **Guardia de SW** (solo en PRs): si el diff toca `index.html`, debe tocar también `CACHE_NAME` en `sw.js` (mecaniza §3bis.1).

En verde, el job materializa `ci-verde`. La suite crecerá bajo el roadmap §5 (debugging de cálculos) con probes numéricos; este ADR fija el suelo, no el techo.

### Razón

Cada check convierte una regla de spec en hecho mecánico; un verde que no comprueba nada sería peor que no tener gate.

### Alternativas descartadas

- Typecheck-only literal (A3): no hay TypeScript; sería un verde vacío.
- Reescribir `test_season_transition.py` como suite ahora: trabajo de diseño numérico que pertenece al roadmap §5, no al alta.

### Coste de revertir

Trivial (editar `ci.yml`); lo que se fija es el nombre del job `gate`, que los stubs referencian.

## ADR-004 (2026-07-11) — Coexistencia de workflows de producto y de pipeline

### Contexto

El repo tiene tres workflows de producto anteriores al pipeline: `update.yml` (datos, varias veces al día, commitea a `main`), `new-season.yml` (issue-recordatorio anual el 1 de agosto) y `build-crests.yml` (manual). El pipeline añadirá los suyos (stubs + heartbeat). El watchdog vigila workflows por nombre y hay que decidir qué ve.

### Decisión

Los tres workflows de producto quedan **fuera de la supervisión del pipeline**: no se listan en `extra_pipeline_workflows` ni en ninguna lista de nombres del watchdog. Operan sobre `main` (ADR-002) mientras el pipeline opera sobre `develop` — dominios disjuntos. Siguen siendo, como todo yml, de mantenimiento humano-execute. El issue anual de `new-season.yml` no arma al Creator: lo crea el bot de Actions sin mención `@claude` y no pasa el gate de `author_association` como colaborador con intención — si algún año se quiere pipeline-izar la actualización de salarios, será decisión nueva.

### Razón

Un fallo de `update.yml` es incidente de producto (datos rancios), no stall de pipeline; mezclarlos haría al watchdog diagnosticar lo que no gobierna.

### Alternativas descartadas

Listar `update.yml` en `extra_pipeline_workflows` para que el watchdog avise de datos rancios: tentador, pero el watchdog re-arma y diagnostica cadenas de issues — no tiene acción válida sobre un cron de datos. La detección de datos rancios ya existe en el producto (`detect_wage_status`, banner de staleness).

### Coste de revertir

Trivial: añadir el nombre a un input de stub.
