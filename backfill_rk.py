#!/usr/bin/env python3
"""
Backfill del rango oficial por partido jugado (`rk[]`) y del `rank` de fin de
temporada en las temporadas HISTÓRICAS de data.json (13/14–25/26).

Contexto (ADR-005·R·2, issues #102/#103): update.py emite `rk[]` (rango oficial
por partido, cadena TIEBREAKERS) SOLO para CURRENT_SEASON; las temporadas
históricas se leen tal cual de data.json y carecen de `rk` (y las anteriores a
25/26 también de `rank`), por lo que el gráfico de posición cae al fallback
aproximado del frontend. Este script reconstruye `rk[]` y `rank` a partir del CSV
oficial de football-data.co.uk, verificándolo contra los puntos acumulados ya
almacenados (`a[]`) antes de escribir nada.

NO toca update.py, index.html ni el motor numérico. La ÚNICA mutación posible de
data.json es AÑADIR `rk` y `rank` a cada equipo de un bloque histórico; ningún
otro campo (`a`, `e`, `m`, `w`, `gd`) de ningún equipo se modifica jamás. La
escritura es todo-o-nada: solo si TODAS las temporadas procesadas pasan la
verificación de consistencia.

Uso:
    python3 backfill_rk.py [--check] [--data data.json] [--league ll] [--season 13/14]

  --check   No escribe nada; solo reporta OK/SKIPPED por temporada.
  --data    Ruta al data.json (por defecto, el de junto al script).
  --league  Restringe a una liga (ll|pl|sa|bl|l1|ed).
  --season  Restringe a una temporada ('YY/NN', p.ej. 24/25).

Sin filtros procesa toda temporada != CURRENT_SEASON de las ligas de TIEBREAKERS
cuyo bloque no tenga `rk` en todos sus equipos.

data.json es intocable para agentes: este script NO se ejecuta contra el
data.json del repo en el PR. Lo ejecuta el propietario/Architect con OK explícito
y commit humano a main y develop.
"""
import argparse
import copy
import csv
import io
import json
import os
import sys

from update import (
    TIEBREAKERS,
    compute_league_ranks,
    fix_name,
    validate_csv_content,
    EXPECTED_DIV,
    CURRENT_SEASON,
)

try:
    import requests
except ImportError:  # pragma: no cover - solo relevante en descarga real
    requests = None

# Código `Div`/fichero por liga (firma de update.py:182, misma tabla que URLS):
# ll→SP1, pl→E0, sa→I1, bl→D1, l1→F1, ed→N1.
CSV_CODE = {'ll': 'SP1', 'pl': 'E0', 'sa': 'I1', 'bl': 'D1', 'l1': 'F1', 'ed': 'N1'}

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA = os.path.join(DATA_DIR, 'data.json')


# ---------------------------------------------------------------------------
# Descarga y parseo del CSV oficial
# ---------------------------------------------------------------------------
def download_csv(lg, sn):
    """Descarga el CSV de la temporada `sn` para la liga `lg`.

    URL: https://www.football-data.co.uk/mmz4281/{YYNN}/{code}.csv
    Con allow_redirects=False (un 3xx = fuzzy-redirect a otra liga NO se sigue),
    status 200 obligatorio y validate_csv_content (issue #79) — mismo blindaje
    que download_current_season en update.py.

    Devuelve (text, None) si válido, o (None, motivo) si falla.
    """
    if requests is None:
        return None, "requests no disponible"
    yynn = sn.replace('/', '')
    code = CSV_CODE[lg]
    url = f'https://www.football-data.co.uk/mmz4281/{yynn}/{code}.csv'
    try:
        r = requests.get(url, timeout=30, allow_redirects=False)
    except Exception as e:  # pragma: no cover - red
        return None, f"descarga falló: {e}"
    if r.status_code != 200:
        return None, f"status {r.status_code} (url {url}) — redirect/HTML rechazado"
    ok, reason = validate_csv_content(r.text, EXPECTED_DIV[lg], sn)
    if not ok:
        return None, f"CSV inválido (esperaba Div={EXPECTED_DIV[lg]}): {reason}"
    return r.text, None


def parse_csv_matches(text):
    """Extrae la lista ORDENADA de partidos válidos del CSV, en orden de filas.

    Cada partido es (home, away, ftr, hg, ag) con home/away pasados por fix_name
    (mismo universo/orden que definió `a[]`/`m[]` históricos). Se ignoran las
    filas sin FTR (∉ {H,D,A}) o sin FTHG/FTAG numéricos, y las que carezcan de
    equipo local o visitante (espeja el dropna de process_season).
    """
    matches = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        home = (row.get('HomeTeam') or '').strip()
        away = (row.get('AwayTeam') or '').strip()
        ftr = (row.get('FTR') or '').strip()
        if not home or not away or ftr not in ('H', 'D', 'A'):
            continue
        try:
            hg = int(float(row['FTHG']))
            ag = int(float(row['FTAG']))
        except (TypeError, ValueError, KeyError):
            continue
        matches.append((fix_name(home), fix_name(away), ftr, hg, ag))
    return matches


# ---------------------------------------------------------------------------
# Reconstrucción de rk[] y rank (misma mecánica que process_season, L537-576)
# ---------------------------------------------------------------------------
def compute_rk_and_ranks(matches, lg):
    """Replica la mecánica de process_season post-R·2 sobre `matches`.

    Universo = todos los equipos del CSV, sembrado en orden de aparición (mismo
    universo completo que usa el `stats` de fin de temporada). Tras cada partido:
    actualiza pts/gd/gf/gf_away/wins/wins_away de local y visitante, computa
    `stats_now` sobre TODO el universo y `compute_league_ranks(stats_now, prefijo,
    lg)`, y anota el rango de local y visitante en su `rk[]`. Los puntos por
    partido (para `pts`/`a[]` y `wins`) se derivan del FTR (idéntico a
    process_season); gd/gf/gf_away se derivan de los goles.

    Devuelve (td, final_ranks) donde:
      td[t] = {'pts': [acumulado por partido del equipo], 'rk': [rango por partido]}
      final_ranks = compute_league_ranks(stats_final, todos, lg)
    """
    teams = []
    seen = set()
    for h, a, _ftr, _hg, _ag in matches:
        for t in (h, a):
            if t not in seen:
                seen.add(t)
                teams.append(t)
    td = {t: {'cp': 0, 'gf': 0, 'ga': 0, 'gf_away': 0, 'wins': 0, 'wins_away': 0,
              'pts': [], 'rk': []} for t in teams}
    season_matches = []  # (home, away, hg, ag) para los criterios de desempate
    for h, a, ftr, hg, ag in matches:
        td[h]['gf'] += hg
        td[h]['ga'] += ag
        td[a]['gf'] += ag
        td[a]['ga'] += hg
        td[a]['gf_away'] += ag
        if ftr == 'H':
            hp, ap = 3, 0
            td[h]['wins'] += 1
        elif ftr == 'A':
            hp, ap = 0, 3
            td[a]['wins'] += 1
            td[a]['wins_away'] += 1
        else:
            hp, ap = 1, 1
        td[h]['cp'] += hp
        td[a]['cp'] += ap
        td[h]['pts'].append(td[h]['cp'])
        td[a]['pts'].append(td[a]['cp'])
        season_matches.append((h, a, hg, ag))
        stats_now = {t: {'pts': d['cp'], 'gd': d['gf'] - d['ga'], 'gf': d['gf'],
                         'gf_away': d['gf_away'], 'wins': d['wins'],
                         'wins_away': d['wins_away']}
                     for t, d in td.items()}
        ranks_now = compute_league_ranks(stats_now, season_matches, lg)
        td[h]['rk'].append(ranks_now[h])
        td[a]['rk'].append(ranks_now[a])
    stats_final = {t: {'pts': d['cp'], 'gd': d['gf'] - d['ga'], 'gf': d['gf'],
                       'gf_away': d['gf_away'], 'wins': d['wins'],
                       'wins_away': d['wins_away']}
                   for t, d in td.items()}
    final_ranks = compute_league_ranks(stats_final, season_matches, lg)
    return td, final_ranks


# ---------------------------------------------------------------------------
# Verificación de consistencia + construcción del bloque (SIN mutar el original)
# ---------------------------------------------------------------------------
def build_block(block, td, final_ranks, lg, sn):
    """Verifica el CSV reconstruido contra el bloque de data.json y, si todo
    cuadra, devuelve un bloque NUEVO con `rk`/`rank` añadidos.

    Verificación bloqueante (cualquier discrepancia ⇒ SKIPPED y el bloque de
    entrada queda intacto — no se muta):
      1. conjunto de equipos del CSV === conjunto de claves del bloque;
      2. para cada equipo, la secuencia de puntos acumulados derivada del CSV
         (`td[t]['pts']`) === `a[]` almacenado, elemento a elemento;
      3. si el bloque ya trae `rank`, debe coincidir con `final_ranks[t]`.

    Escritura (solo si 1-3 pasan): sobre una COPIA profunda del bloque, para cada
    equipo `rk = td[t]['rk']` con `rk[-1] = final_ranks[t]` y `rank =
    final_ranks[t]`. Invariantes: `len(rk) == len(a)` y `rk[-1] == rank`.

    Devuelve (new_block, None) en éxito, o (None, "SKIPPED: …") en fallo.
    """
    csv_teams = set(td.keys())
    block_teams = set(block.keys())
    if csv_teams != block_teams:
        only_csv = sorted(csv_teams - block_teams)
        only_data = sorted(block_teams - csv_teams)
        return None, (f"SKIPPED: {lg} {sn} conjunto de equipos difiere "
                      f"(solo CSV={only_csv} solo data={only_data})")

    for t in block:
        rec = td[t]['pts']
        stored = block[t]['a']
        if len(rec) != len(stored):
            return None, (f"SKIPPED: {lg} {sn} {t} len(a) csv={len(rec)} "
                          f"data={len(stored)}")
        for i in range(len(rec)):
            if rec[i] != stored[i]:
                return None, (f"SKIPPED: {lg} {sn} {t} {i} "
                              f"csv={rec[i]} data={stored[i]}")

    for t in block:
        if 'rank' in block[t] and block[t]['rank'] != final_ranks[t]:
            return None, (f"SKIPPED: {lg} {sn} {t} rank data={block[t]['rank']} "
                          f"csv={final_ranks[t]}")

    new_block = copy.deepcopy(block)
    for t in new_block:
        rk = list(td[t]['rk'])
        if rk:
            rk[-1] = final_ranks[t]
        new_block[t]['rk'] = rk
        new_block[t]['rank'] = final_ranks[t]
        assert len(new_block[t]['rk']) == len(new_block[t]['a']), (lg, sn, t)
        if rk:
            assert new_block[t]['rk'][-1] == new_block[t]['rank'], (lg, sn, t)
    return new_block, None


# ---------------------------------------------------------------------------
# Selección de temporadas y escritura
# ---------------------------------------------------------------------------
def block_has_full_rk(block):
    """True si el bloque no está vacío y TODOS sus equipos ya traen `rk`
    (idempotencia: no reprocesar lo ya backfilleado)."""
    return bool(block) and all('rk' in entry for entry in block.values())


def select_seasons(data, league_filter, season_filter):
    """Lista ordenada de (lg, sn) a procesar: ligas de TIEBREAKERS, temporada
    != CURRENT_SEASON, bloque sin `rk` completo, filtrada por --league/--season."""
    out = []
    seasons = data.get('seasons', {})
    for lg in TIEBREAKERS:
        if league_filter and lg != league_filter:
            continue
        for sn in seasons.get(lg, {}):
            if sn == CURRENT_SEASON:
                continue
            if season_filter and sn != season_filter:
                continue
            if block_has_full_rk(seasons[lg][sn]):
                continue
            out.append((lg, sn))
    return out


def write_data(data, path):
    """Serializa data.json con el MISMO contrato que update.py (separators
    compactos, ensure_ascii=False, SAFE_REPLACE) — las regiones no tocadas salen
    byte-idénticas; el único delta son las claves `rk`/`rank` añadidas."""
    out = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    SAFE_REPLACE = {"Nott'm Forest": "Nottm Forest", "Ath Madrid": "At Madrid"}
    for old, new in SAFE_REPLACE.items():
        out = out.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)


# ---------------------------------------------------------------------------
# Orquestación / CLI
# ---------------------------------------------------------------------------
def run(check=False, data_path=None, league=None, season=None):
    """Procesa las temporadas seleccionadas. Devuelve el exit code
    (0 si SKIPPED==0, 1 en caso contrario). Escribe solo si no hay SKIPPED,
    no es --check y hay algo que escribir."""
    data_path = data_path or DEFAULT_DATA
    if league and league not in TIEBREAKERS:
        print(f"Liga desconocida: {league!r} (esperada una de {list(TIEBREAKERS)})")
        return 1
    with open(data_path, encoding='utf-8') as f:
        data = json.load(f)

    targets = select_seasons(data, league, season)
    ok = 0
    skipped = 0
    new_blocks = {}
    lines = []
    for lg, sn in targets:
        block = data['seasons'][lg][sn]
        text, err = download_csv(lg, sn)
        if err:
            lines.append(f"SKIPPED: {lg} {sn} {err}")
            skipped += 1
            continue
        matches = parse_csv_matches(text)
        td, final_ranks = compute_rk_and_ranks(matches, lg)
        new_block, reason = build_block(block, td, final_ranks, lg, sn)
        if reason:
            lines.append(reason)
            skipped += 1
            continue
        new_blocks[(lg, sn)] = new_block
        lines.append(f"OK {lg} {sn} ({len(td)} equipos, {len(matches)} partidos)")
        ok += 1

    for ln in lines:
        print(ln)
    print(f"OK={ok} SKIPPED={skipped}")

    if skipped == 0 and not check and new_blocks:
        for (lg, sn), nb in new_blocks.items():
            data['seasons'][lg][sn] = nb
        write_data(data, data_path)
        print(f"WRITE {data_path} ({len(new_blocks)} temporada(s))")

    return 0 if skipped == 0 else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check', action='store_true',
                   help='No escribe; solo reporta OK/SKIPPED por temporada.')
    p.add_argument('--data', default=None, help='Ruta al data.json.')
    p.add_argument('--league', default=None, help='Restringe a una liga.')
    p.add_argument('--season', default=None, help="Restringe a una temporada 'YY/NN'.")
    args = p.parse_args(argv)
    return run(check=args.check, data_path=args.data,
               league=args.league, season=args.season)


if __name__ == '__main__':
    sys.exit(main())
