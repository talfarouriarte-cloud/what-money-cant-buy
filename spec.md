# spec.md — Football beyond money

<!-- Spec canónica del proyecto. resolver-protocol define las decisiones
DERIVABLES como las respaldadas por cita VERBATIM de ADR/spec. Cada sección
responde «¿debe X comportarse como Y?» con cita literal. -->

## §1 Visión

Football beyond money es un dashboard web público, interactivo y bilingüe (inglés/español) que analiza y predice el rendimiento de clubes de fútbol de las 6 grandes ligas europeas ajustado por su masa salarial. El modelo central es una regresión logística ordenada sobre el log₂ del ratio de salarios entre dos equipos, que produce probabilidades de victoria/empate/derrota a nivel de partido; sobre ella se construyen puntos esperados, proyecciones Monte Carlo, evaluación de rachas y seguimiento multi-temporada de sobrerrendimiento. La app se actualiza automáticamente varias veces al día mediante crons redundantes y su audiencia es el público general aficionado: ante un empate de diseño, prima la legibilidad divulgativa sobre la densidad analítica.

El producto es la web app. El paper *What money can't buy* es fundacional — origen del modelo — pero la app lo ha superado: la implementación viva es la fuente de verdad y un cambio de modelo no exige actualizar el paper, que se conserva como artefacto fundacional.

Qué NO es: no es una herramienta de apuestas; no hay análisis a nivel de jugador (la unidad es el club); no hay monetización ni cuentas de usuario.

## §2 Principios

1. **Fact-based** — la app afirma solo lo que los datos y el modelo sostienen; nada de opinión editorial ni especulación narrativa. Todo texto visible (narrativa, badge, card) debe poder rastrearse a un número calculado.
2. **Legibilidad divulgativa** — ante un empate de diseño, gana la opción que entiende un aficionado sin formación estadística.
3. **Automatización total** — la operación manual se limita a la actualización anual de salarios; cualquier otra intervención manual recurrente es un defecto de diseño.
4. **Touch-first** — toda la UI debe funcionar en dispositivo táctil (iPad como referencia).
5. **Bilingüe siempre** — ninguna feature sale en un solo idioma; EN y ES llegan en el mismo cambio.

## §3 Stack y estructura

**Stack.** Frontend: React 18.2 + Recharts 2.12.7 en un único fichero `index.html` (sin build step), PWA con service worker `sw.js`. Backend de datos: scripts Python (`update.py` diario, `setup_season.py`, `build_crests.py`, `test_season_transition.py`). Datos en JSON planos en la raíz del repo. Hosting: GitHub Pages con dominio `footballbeyondmoney.uk`; automatización vía GitHub Actions (`update.yml` 2×/día, `new-season.yml` anual, `build-crests.yml` manual).

**Dónde vive cada cosa.** `index.html` y `test.html` son la app (idénticos; toda entrega incluye ambos). `data.json` y `fixtures.json` son generados — solo los escribe `update.py`, nunca a mano. `all_wages.json` es la fuente única de salarios. `i18n.json` contiene todas las claves de traducción EN/ES. `crests.json` mapea escudos.

**Zonas de rigor especial:**

1. **Núcleo de modelo en `update.py`** (regresión logística ordenada, Monte Carlo, puntos esperados, probabilidades de posición): ningún cambio puede alterar resultados numéricos salvo que el issue lo pida explícitamente; todo cambio de modelo exige justificación numérica.
2. **`all_wages.json`**: edición exclusivamente humana o por proceso explícitamente acordado; ningún agente lo modifica como efecto lateral.
3. **Mapeo de nombres de equipo**: prohibido el replace global sobre nombres; todo mapeo pasa por las tablas de correspondencia existentes en `update.py`.

## §3bis Decisiones estructurales vigentes

1. **Bump de service worker**: todo cambio de la app incrementa la versión de caché en `sw.js` (`CACHE_NAME`). Sin bump, los usuarios no reciben el cambio.
2. **Cadena de fallback de salarios**: salario de la temporada actual en `all_wages.json` → temporada anterior → mínimo de liga (`_min`). Equipos ascendidos entran con el mínimo.
3. **Prioridad de fuentes**: API de football-data.org como primaria (resultados en minutos); CSV de football-data.co.uk como fallback (1–2 días de retraso).
4. **p50 determinista**: tanto la línea actualizada como la de presupuesto usan valor esperado determinista (`pw×3 + pd`) para el p50; Monte Carlo solo para bandas p10/p90. Garantiza líneas de proyección paralelas.
5. **Temporada derivada, nunca hardcodeada**: `CURRENT_SEASON` se deriva de la fecha (agosto+ = temporada nueva) en `update.py`; el frontend deriva `CUR_SN` de la última clave de `data.json`. Cero strings de temporada hardcodeados.
6. **Sin strings de UI hardcodeados**: todo texto visible pasa por clave de `i18n.json` (mecaniza el principio §2.5).
7. **Sin transpilación**: la app es `React.createElement` puro dentro de `index.html`; queda prohibida sintaxis que exija JSX, build o transpilado.

Nota: la entrega dual `index.html`+`test.html` idénticos queda superada por la estructura de ramas `develop`/`main` (ADR pendiente en F2); `test.html` se eliminará cuando esa estructura esté operativa.

## §4 Fronteras

Fuera del alcance del producto y del repo:

1. **Apuestas**: la app no da consejo de apuestas ni se integra con casas o cuotas (§1).
2. **Nivel jugador**: la unidad de análisis es el club; nada de datos ni métricas individuales (§1).
3. **Monetización y cuentas de usuario**: no hay pagos, suscripciones, login ni estado por usuario (§1).
4. **Backend con servidor**: el producto es estático (GitHub Pages) + GitHub Actions por definición; queda fuera cualquier solución que exija servidor propio, base de datos alojada o proceso persistente.

No son fronteras (diseño legítimo si algún día se plantea): añadir ligas u otras competiciones; usar fuentes de datos de pago.

## §5 Roadmap de alto nivel

Dos líneas estables, sin plazos comprometidos:

1. **Mejora del diseño visual** — refinamiento estético e interaccional de la app existente, sin ampliar alcance funcional.
2. **Debugging de cálculos** — verificación y corrección del pipeline numérico (`update.py` → `data.json` → frontend); las correcciones que alteren resultados se justifican numéricamente conforme a §3 zona de rigor 1.

El estado vivo (qué se está haciendo ahora) vive en la skill de capa 3, no en esta spec.
