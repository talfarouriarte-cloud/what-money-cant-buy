# decisions.md — índice de ADRs

<!-- Formato verificado por scripts/adr-lint.mjs con adr-lint.config.json
(volumen único = este fichero, reglas estrictas desde ADR-001). -->

- [ADR-001](#adr-001-2026-07-11--fundación-proyecto-existente-entra-en-desarrollo-agéntico) — Fundación: proyecto existente entra en desarrollo agéntico
- [ADR-002](#adr-002-2026-07-11--estructura-de-ramas-developmain) — Estructura de ramas develop/main
- [ADR-003](#adr-003-2026-07-11--ci-qué-materializa-ci-verde) — CI: qué materializa `ci-verde`
- [ADR-004](#adr-004-2026-07-11--coexistencia-de-workflows-de-producto-y-de-pipeline) — Coexistencia de workflows de producto y de pipeline
- [ADR-005](#adr-005-2026-07-11--criterios-de-desempate-de-la-clasificación-real) — Criterios de desempate de la clasificación real
- [ADR-006](#adr-006-2026-07-11--desempate-del-forecast-puntos-simulados--rank-oficial-actual) — Desempate del forecast: puntos simulados → rank oficial actual
- [ADR-007](#adr-007-2026-07-12--reloj-único-de-temporada-fetch-de-calendario-por-temporada-explícita) — Reloj único de temporada: fetch de calendario por temporada explícita
- [ADR-008](#adr-008-2026-07-12--cambio-de-temporada-el-15-de-julio) — Cambio de temporada el 15 de julio
- [ADR-009](#adr-009-2026-07-12--mapa-de-nombres-único-con-capa-de-display) — Mapa de nombres único con capa de display
- [ADR-010](#adr-010-2026-07-12--build-crests-encadenado-a-update-por-workflow_run) — build-crests encadenado a update por workflow_run

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

## ADR-005 (2026-07-11) — Criterios de desempate de la clasificación real

### Contexto

La clasificación real usa un desempate uniforme "puntos → diferencia general" en todo el producto. Los reglamentos reales difieren por liga e incluyen el enfrentamiento particular. Origen, decisión del propietario, verbatim:

> la clasificación real (final de temporada) no está bien, porque no tiene en cuenta de forma fina la diferencia de goles participar y la general. Podemos corregir eso.

### Decisión

El desempate fino aplica **solo a la clasificación real** (partidos jugados); las proyecciones siguen con puntos→diferencia general (no hay modelo de goles). Se calcula en el **backend** (`update.py`), que emite el ranking oficial resuelto en `data.json`; el frontend lo consume sin ordenar. **Backfill total**: las 13 temporadas × 6 ligas se recalculan con las reglas **vigentes** de cada liga aplicadas uniformemente al histórico. Cadena tras puntos, cerrada por el propietario:

| Liga | Desempate tras puntos |
|---|---|
| La Liga | particular puntos → particular GD → general GD → goles marcados |
| Serie A | particular puntos → particular GD → general GD → goles marcados |
| Premier League | general GD → goles marcados → particular puntos → particular goles fuera |
| Bundesliga | general GD → goles marcados → particular (agregado) → particular goles fuera → goles fuera general |
| Ligue 1 | general GD → particular puntos → particular GD → goles marcados → victorias → victorias fuera |
| Eredivisie | general GD → goles marcados → particular |

Reglas de contorno: (a) los criterios particulares solo aplican si los empatados han completado sus enfrentamientos reglamentarios; si no, la cadena salta a los criterios generales; (b) colas inmodelables (playoff de Serie A desde 2022/23, disciplina, sorteo) mantienen el orden estable previo; (c) todo lo anterior se documenta en Methodology (EN/ES), incluido el descargo del histórico recalculado con reglas vigentes.

**Ubicación y mantenimiento.** La tabla es normativa **en este ADR**; su única implementación es una constante `TIEBREAKERS` por liga en `update.py`, con comentario que ancla a ADR-005 (zona de rigor spec §3.1 — el Creator no la modifica sin mandato). La explicación pública vive en la pestaña Methodology vía claves de `i18n.json`. Cuando una liga cambie su reglamento: decisión del propietario → ADR que rectifica este → actualización de `TIEBREAKERS`, Methodology (EN/ES) y recálculo del histórico **en el mismo cambio** — las tres copias (ADR, constante, Methodology) nunca divergen porque solo se tocan juntas.

### Razón

Fact-based (spec §2.1): la tabla mostrada debe coincidir con la oficial. Backend porque los marcadores partido a partido viven ahí y la lógica es una y testeable.

### Alternativas descartadas

- Regla vigente **por temporada**: coste de arqueología reglamentaria alto, fuentes flojas en años viejos, beneficio marginal para un dashboard divulgativo (§2.2).
- Cálculo en frontend: exigiría meter todos los cruces en `data.json` y duplicar lógica en ~6 puntos de ordenación.

### Coste de revertir

Medio: revertir la emisión de `rank` en `data.json` y devolver los sorts al frontend es medio día; el compromiso real es el contrato de datos (`rank` oficial en `data.json`) que el frontend pasará a asumir.

## ADR-006 (2026-07-11) — Desempate del forecast: puntos simulados → rank oficial actual

### Contexto

El forecast (MC de `simulate_position_probs`) resuelve empates a puntos con dos reglas incorrectas: en simulación, ruido aleatorio (`+noise*0.001` — moneda al aire, ajeno a las reglas de la liga); con temporada completa (`n_matches == 0`), `argsort(-pts)` estable — el orden de índice del array decide, determinista y arbitrario, con certeza 100%. Artefacto visible: Osasuna 25/26 con `Rel 100%` en la previsión de última jornada pese a salvarse (triple empate a 42 resuelto por índice en todas las ramas). ADR-005 acaba de construir `compute_league_ranks` (cadena oficial de desempate por liga sobre datos reales con goles).

### Decisión

Bloque de decisión del propietario (verbatim, sesión 2026-07-11):

> Habría que cambiar el forecast (la parte mecánica) para que desempate con goles…mira la previsión de última jornada de Osasuna. eso es un bug

> No hace falta simular marcadores. Basta con la posición actual en cada momento en desempate

Regla única para todo el forecast: **orden por (puntos simulados desc, rank oficial actual asc)**. El «rank oficial actual» es la salida de `compute_league_ranks` sobre el estado REAL en el instante de referencia de la simulación (en `compute_position_history`, el estado real hasta la jornada g). La rama de temporada completa es el caso degenerado de la misma regla (0 partidos pendientes ⇒ puntos = finales, rank actual = rank oficial) y sustituye al `argsort`. Se elimina el ruido.

Caso frontera cerrado: **pretemporada** (0 partidos jugados) no tiene rank oficial — el desempate secundario permanece aleatorio (ruido actual), que es insesgado y refleja la ignorancia real.

Sin umbral: el propietario planteó activar el desempate con diferenciales < 0,5 puntos; descartado tras discusión («Ok convencido»). Razón: el sort ocurre dentro de cada simulación con puntos ENTEROS (los empates exactos son frecuentes; el Rk mostrado es la mediana de ranks simulados, no un orden de esperanzas fraccionales), y la igualdad-por-umbral no es transitiva (los grupos de empate no quedan bien definidos) además de sesgar hacia el statu quo dentro de la banda de ruido.

### Razón

La posición oficial actual condensa GD y particulares de lo ya jugado: es el proxy natural del desempate final sin simular marcadores ni tocar el modelo probabilístico (que emite solo 1X2). Elimina los `100%` falsos por desempate arbitrario y unifica las dos ramas en una regla.

### Alternativas descartadas

- **Simular marcadores** (Poisson condicionado a `ph/pd`): correcto en el límite pero toca el modelo probabilístico entero; coste desproporcionado para el sesgo que corrige.
- **Umbral de medio punto sobre esperanzas fraccionales**: no transitivo; y el punto de aplicación real (sort intra-simulación) opera sobre enteros donde el problema no existe.
- **Mantener ruido y arreglar solo la rama de temporada completa**: corrige el artefacto visible pero deja el desempate simulado fuera de las reglas; el coste de la regla unificada es el mismo.

### Coste de revertir

Trivial (una clave de sort y un precómputo); el test de regresión de Osasuna quedará como guardia del comportamiento.

## ADR-007 (2026-07-12) — Reloj único de temporada: fetch de calendario por temporada explícita

### Contexto

`CURRENT_SEASON` se deriva de la fecha (`update.py:43`, agosto+ = temporada nueva; spec §3bis.5), pero `fetch_fixtures_from_api` pide `GET /competitions/{code}/matches` sin parámetro de temporada (`update.py:325`) y almacena la respuesta bajo `fixtures[lg][CURRENT_SEASON]`. La API de football-data.org cambia su temporada "actual" al publicarse los calendarios (julio), semanas antes que el reloj de fecha. Incidente verificado el 2026-07-12 en producción: el cron guardó el calendario 26/27 (380 fixtures, 0 jugados, con ascendidos sin mapear) bajo la clave `25/26`, inyectó fixtures fantasma como `r` en `data.json` y re-simuló el forecast de una temporada terminada (`pos.cur` de La Liga 25/26 degenerado).

### Decisión

Dos piezas, ambas en `fetch_fixtures_from_api`:

1. **Petición explícita**: la llamada a `/matches` lleva `?season=<año>` donde el año se deriva de `CURRENT_SEASON` (p. ej. `25/26` → `2025`). La fecha sigue siendo el reloj único del sistema; la API deja de imponer el suyo.
2. **Guardia de coherencia**: antes de escribir `fixtures[lg][CURRENT_SEASON]`, se deriva la clave de temporada del propio payload (`matches[0].season.startDate`) y se compara con `CURRENT_SEASON`; si no coinciden, se descarta el calendario de esa liga con warning en el log y no se escribe nada. La guardia protege contra cualquier comportamiento inesperado del parámetro (tier gratuito, temporadas no disponibles).

Remediación del incidente: el propio cron autorrepara al promocionar el fix a `main` — la petición explícita de `25/26` devuelve el calendario real (todo jugado), reconstruye `fixtures.json` y recalcula `data.json`. Debe ocurrir antes del cambio de temporada (2026-07-15, ADR-008): a partir de ahí `25/26` deja de ser `CURRENT_SEASON` y el registro corrupto quedaría congelado como histórico. Si el tier gratuito rechazara la petición de la temporada saliente, la guardia evita re-corrupción y la restauración de `fixtures.json` es humana (git history de `main`).

### Razón

Mantiene un solo reloj (spec §3bis.5) con el cambio mínimo; autorrepara producción sin intervención manual (spec §2.3); la guardia convierte la clase de fallo "dos relojes" en imposible por construcción, no solo en improbable.

### Alternativas descartadas

- **Derivar la clave de almacenamiento de la respuesta de la API**: pre-carga el calendario nuevo antes de agosto (beneficio nulo — llegaría igual en el primer cron de agosto), no autorrepara la clave `25/26` corrupta sin re-fetch adicional, y rompe la unicidad del reloj.
- **Solo guardia, sin parámetro**: evita re-corrupción pero no autorrepara ni entrega el calendario nuevo hasta que la fecha alcance a la API — pierde frescura en la ventana de julio sin ganar nada.

### Coste de revertir

Trivial (un parámetro de query y un bloque de guardia); el compromiso real es el contrato de que `fixtures[lg][sn]` contiene siempre la temporada `sn` — el frontend y `get_remaining_fixtures` ya lo asumen hoy.

## ADR-008 (2026-07-12) — Cambio de temporada el 15 de julio

### Contexto

`CURRENT_SEASON` cambia el 1 de agosto (`update.py:43`, `month >= 8`; espejo en `test_season_transition.py:18` y spec §3bis.5). Los calendarios de las 6 ligas se publican a lo largo de junio/julio y la API los sirve desde entonces; con el umbral en agosto, la app muestra durante semanas una temporada terminada como actual y desaprovecha el calendario nuevo ya disponible (bandas de pretemporada, plantilla de ascensos).

### Decisión

Decisión del propietario, verbatim:

> Vamos a acelerar el setup de la nueva temporada al 15 de julio (así también a futuro)

La regla de derivación pasa a: temporada nueva desde el **15 de julio** inclusive (`(month, day) >= (7, 15)`), permanente, en los tres puntos: `update.py:43`, `test_season_transition.py:18` y el texto de spec §3bis.5 — las tres copias se tocan en el mismo cambio y nunca divergen. La derivación se extrae a función pura testeable. Entre el 15 de julio y el arranque real (~mediados de agosto) la temporada actual muestra 0 partidos jugados: calendario y bandas de pretemporada con salarios de fallback (cadena de spec §3bis.2) son el contenido. Si el calendario de alguna liga aún no está en la API, la guardia de ADR-007 lo descarta y esa liga queda sin calendario hasta que aparezca — el cron diario lo recoge solo.

### Razón

El producto gana un mes de contenido nuevo (calendario, pretemporada, ascendidos) en el periodo de mayor apetito informativo del aficionado; el coste es adelantar el archivado de la temporada terminada, cuyo registro queda intacto como histórico.

### Alternativas descartadas

- **Umbral variable "cuando la API cambie"**: devolvería el reloj a la API (la causa raíz del incidente de ADR-007) y haría el cambio no determinista y no testeable.
- **Mantener agosto**: statu quo; desperdicia un mes de calendario disponible sin ganar robustez — la ventana de dos relojes ya la cierra ADR-007.

### Coste de revertir

Trivial: una tupla en la función de derivación y el texto de spec; ninguna estructura de datos depende del valor del umbral.

## ADR-009 (2026-07-12) — Mapa de nombres único con capa de display

### Contexto

El mapeo API→interno vive duplicado (`API_NAME_MAP` en `update.py`, 181 entradas, y en `build_crests.py`, 291; sin conflictos de valor pero con 138 entradas no compartidas). Además el nombre interno — clave de cruce entre CSV de football-data.co.uk, API y `all_wages.json` — se muestra tal cual en la UI, exhibiendo la convención ASCII/abreviada de la fuente de datos ("Espanol", "At Madrid", "Koln", "Nottm Forest"). Los 3 ascendidos de La Liga 26/27 y 8 más de otras ligas no tienen entrada API y aparecerían con nombre crudo el 15 de julio.

### Decisión

Un fichero `name_map.json` en raíz, fuente única con dos secciones:

1. **`api_to_internal`**: unión de las dos copias existentes (si aparece una clave con valores distintos, se aborta y escala — hoy no hay ninguna) más las entradas de los ascendidos 26/27. `update.py` y `build_crests.py` cargan de aquí y sus dicts inline se eliminan. La lógica de `api_name_to_internal` no cambia.
2. **`display`**: mapeo interno→nombre de presentación. El nombre interno queda como clave inmutable de datos (13 temporadas, salarios, escudos); el frontend aplica un helper `dn(n)` en todo texto visible de equipo. Las claves de objetos, el cruce de escudos y los joins de datos siguen en interno. El display es único para EN y ES (los nombres de club no se traducen). La tabla de display es normativa en este ADR; decisión del propietario, verbatim para España:

> Todo. Para España atlético madrid, Athletic club, real sociedad, deportivo, racing

| Interno | Display |
|---|---|
| Alaves | Alavés |
| Almeria | Almería |
| At Madrid | Atlético Madrid |
| Ath Bilbao | Athletic Club |
| Cadiz | Cádiz |
| Cordoba | Córdoba |
| Espanol | Espanyol |
| La Coruna | Deportivo |
| Leganes | Leganés |
| Malaga | Málaga |
| Sociedad | Real Sociedad |
| Sp Gijon | Sporting Gijón |
| Vallecano | Rayo Vallecano |
| Santander | Racing |
| Koln | Köln |
| Monchengladbach | M'gladbach |
| Dusseldorf | Düsseldorf |
| Furth | Greuther Fürth |
| Nurnberg | Nürnberg |
| Braunschweiger | Braunschweig |
| St Pauli | St. Pauli |
| St-Etienne | Saint-Étienne |
| Nimes | Nîmes |
| Nottm Forest | Nottingham Forest |

Los 177 nombres internos restantes se muestran sin cambio. La zona de rigor de spec §3.3 (mapeo de nombres) se extiende a `name_map.json`: prohibido el replace global; toda entrada nueva es mandato explícito de issue o edición humana.

### Razón

Una copia divergente de mapa es la misma enfermedad que las tres copias de ADR-005 evitan; y separar clave de presentación corrige la UI sin tocar 13 temporadas de claves de datos ni `all_wages.json` (legibilidad divulgativa, spec §2.2, con coste cero en el pipeline numérico).

### Alternativas descartadas

- **Renombrar los internos a los nombres de display**: rompe el cruce con el histórico, los CSV y los salarios; migración de 201 claves en cadena para un problema de presentación.
- **Display por idioma (EN/ES separados)**: los nombres de club no se traducen; duplicaría 201 entradas sin valor.
- **`build_crests.py` importando el mapa desde `update.py`**: acopla su workflow a pandas/numpy/scipy sin necesidad; el JSON compartido es el patrón del repo.

### Coste de revertir

Bajo: los dicts inline pueden restaurarse desde `name_map.json`; retirar `dn()` devuelve los internos a pantalla. El compromiso real es la zona de rigor extendida al fichero nuevo.

## ADR-010 (2026-07-12) — build-crests encadenado a update por workflow_run

### Contexto

`build-crests.yml` es `workflow_dispatch` puro: recoge escudos solo cuando un humano lo lanza. Los escudos de equipos ascendidos solo pueden obtenerse una vez que el calendario de la temporada nueva existe en `fixtures.json`, lo que ocurre en el primer cron tras el cambio de temporada (15 de julio, ADR-008) — un instante no conocido de antemano (depende de cuándo publique cada liga). Verificado el 2026-07-12: un dispatch manual antes del cambio no puede completar los 4 escudos de los ascendidos 26/27 porque su calendario aún no existe. Depender de que alguien lance el workflow el día justo es intervención manual recurrente (spec §2.3).

### Decisión

`build-crests.yml` gana un disparador `on: workflow_run` sobre "Update match data" con `types: [completed]` y guard `if: github.event.workflow_run.conclusion == 'success'`. Se conserva `workflow_dispatch`. `update.yml` no se toca. El encadenado es **incondicional**: build-crests corre tras cada update exitoso, sin lógica de detección de equipos nuevos en `update.py`. Es seguro y barato porque `build_crests.py` es idempotente (solo añade los nombres de `needed` ausentes de `crests.json`; sin cambios ⇒ commit no-op) y su conjunto de necesidad ya incluye el calendario de la temporada actual (correctivo #25). Coste: ~90 s de runner por día en que update commitee, la mayoría sin cambio de escudos.

### Razón

Elimina el único paso manual que quedaba del rollover con la superficie mínima (un fichero de workflow, cero Python, cero fecha hardcodeada) y sin añadir estado nuevo. El invariante que sostiene la decisión — "build_crests es idempotente" — es más robusto y verificable que su alternativa ("update.py detecta correctamente los equipos nuevos"), que exigiría una señal de salida en zona 1 (spec §3) para ahorrar un run barato.

### Alternativas descartadas

- **Detección en `update.py` + disparo condicional**: mete una señal de "equipos nuevos" en el núcleo del pipeline (zona 1, más rigor) para ahorrar un run idempotente diario; más superficie, mismo resultado.
- **`schedule` anual el 15 de julio en build-crests**: fecha hardcodeada y frágil (si una liga publica su calendario más tarde, ese día aún no existe y no hay reintento hasta el año siguiente); contradice "temporada derivada, nunca hardcodeada" (spec §3bis.5).
- **`workflow_call` desde update.yml**: acopla ambos workflows, duplica el job de crests bajo el gate de secrets de update y obliga a editar `update.yml`; `workflow_run` desacopla sin tocarlo.

### Coste de revertir

Trivial: eliminar el bloque `workflow_run` devuelve build-crests a dispatch puro; ninguna otra pieza depende del encadenado.
