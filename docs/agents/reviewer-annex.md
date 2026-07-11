# Anexo de rol — Reviewer (what-money-cant-buy)

<!-- Contrato repo-específico. Se carga JUNTO al mandato genérico vendorizado
(docs/agents/reviewer.md). -->

Rama base: `develop`. En TODO PR, verificar además del mandato genérico:

1. Si el diff toca `index.html` → bump de `CACHE_NAME` en `sw.js` presente en el mismo PR (el CI también lo bloquea; tu veredicto no depende de él).
2. Claves nuevas de `i18n.json` → par `[en, es]` completo y no vacío.
3. Cero sintaxis JSX o que exija transpilación (spec §3bis.7).
4. El diff NO toca: `.github/workflows/*`, `data.json`, `fixtures.json`, `all_wages.json`, `CNAME`, `What money cant buy.pdf`. Si los toca → REVIEW, sin excepciones.
5. Cambios en `update.py` que alteren resultados numéricos → exigir el mandato explícito del issue y la justificación numérica (spec §3, zona de rigor 1); sin ella → REVIEW.
