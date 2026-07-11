# Anexo de rol — Creator (what-money-cant-buy)

<!-- Contrato repo-específico. Se carga JUNTO al mandato genérico vendorizado
(docs/agents/creator.md). Reglas de cierre: las de la spec. -->

1. **Rama base**: `develop` (única donde trabajas). Prefijo de ramas de agente: `claude/`.
2. **Comandos de verificación local**: estático = `python3 -m py_compile <script>` sobre los `.py` que toques + `node --check` sobre el JS que extraigas de `index.html` si lo tocas. Tests: fichero a fichero, `python3 <ruta>` — no existe suite; NUNCA inventes ni ejecutes un runner global.
3. **Ficheros intocables**: `.github/workflows/*`, `data.json`, `fixtures.json`, `all_wages.json`, `CNAME`, `What money cant buy.pdf`. Si tu issue parece exigir tocarlos, el issue está mal: escala.
4. **Entrega**: `index.html` solo (sin `test.html`, ADR-002) + bump obligatorio de `CACHE_NAME` en `sw.js` en el mismo PR (el CI lo bloquea si falta).
5. **Strings de UI**: siempre clave nueva en `i18n.json` con par `[en, es]` completo. Un placeholder en un solo idioma = PR incompleto.
6. **Sin transpilación**: `React.createElement` puro (spec §3bis.7).
7. **Zona de rigor `update.py`**: prohibido alterar resultados numéricos salvo mandato explícito y literal del issue; ante ambigüedad numérica, escala — no interpretes.
8. **Presupuesto**: sesiones dimensionadas a 100 turns; si el issue no cabe, es defecto de tamaño del issue — escala, no comprimas.
