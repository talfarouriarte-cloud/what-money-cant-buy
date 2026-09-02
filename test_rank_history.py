#!/usr/bin/env python3
"""
Tests del rango oficial por partido jugado (`rk[]`) — ADR-005·R·2, issue #102.

`process_season` emite, junto a `a[]`, una serie `rk[]` alineada con ella:
`rk[i]` es el rango OFICIAL (cadena `TIEBREAKERS[lg]`) del equipo inmediatamente
después de su partido i-ésimo, calculado sobre el prefijo de partidos en el
orden que ya define `m`; `rk[-1]` se fija al `rank` vigente (invariante).

Cubre:
  (a) `len(rk) == len(a)` por equipo (una entrada por partido jugado).
  (b) `rk[-1] == rank` para todo equipo con partidos.
  (c) Fixture sintético de La Liga con empate a puntos resuelto por mini-liga:
      el `rk` de cada corte es una permutación 1..N sobre el UNIVERSO COMPLETO de
      la liga (equipos con 0 partidos incluidos, en el grupo de empate a 0), y el
      estado final refleja el desempate oficial (no el ingenuo puntos→GD).
      Oráculo derivado de la definición del ADR (tabla oficial sobre el prefijo,
      universo completo), no de la implementación.
  (c') Corte inicial: en una liga sembrada de N equipos, tras un único partido el
      perdedor recibe `rk[0] == N` (último), no 2 — el universo del corte es la
      liga entera, no el subconjunto {ganador, perdedor}. Ancla anti-regresión del
      🔴 del universo reducido.
  (d) No-regresión: activar/desactivar la maquinaria de rk/rank (pertenencia a
      TIEBREAKERS) deja `a/e/m/w/gd` bit-idénticos, y `rank` coincide con la
      clasificación oficial — el campo aditivo no perturba nada existente.

Requiere pandas + numpy + scipy (los usa process_season). NO requiere red ni
data.json: todo el escenario es sintético. Como
`test_process_season_calendar_seed.py`:
    python3 test_rank_history.py
"""
import sys

try:
    import numpy as np
    import pandas as pd
except ImportError:  # pragma: no cover
    print("FALLO: numpy/pandas no disponibles (requeridos por process_season). "
          "Instala con: pip install numpy pandas")
    sys.exit(1)

import update

if update.expit is None:  # pragma: no cover
    print("FALLO: scipy no disponible (expit requerido por el motor). "
          "Instala con: pip install scipy")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers de fixture sintético
# ---------------------------------------------------------------------------
def _matches_to_df(matches):
    """Convierte una lista de partidos (home, away, home_goals, away_goals) en el
    DataFrame que consume process_season (formato API con goles). El orden de
    filas se preserva: es el eje de `m`/`rk`."""
    rows = {'HomeTeam': [], 'AwayTeam': [], 'FTHG': [], 'FTAG': [], 'FTR': []}
    for (h, a, hg, ag) in matches:
        rows['HomeTeam'].append(h)
        rows['AwayTeam'].append(a)
        rows['FTHG'].append(hg)
        rows['FTAG'].append(ag)
        rows['FTR'].append('H' if hg > ag else ('A' if ag > hg else 'D'))
    return pd.DataFrame(rows)


def _wages_for(matches, base=100):
    """Salarios deterministas para todos los equipos que aparecen en `matches`,
    más `_min` (último eslabón de fallback)."""
    teams = sorted({h for h, _, _, _ in matches} | {a for _, a, _, _ in matches})
    w = {t: base - i for i, t in enumerate(teams)}
    w['_min'] = min(w.values())
    return w


def _final_standings(matches):
    """Totales de temporada {team: {pts,gd,gf,gf_away,wins,wins_away}} calculados
    INDEPENDIENTEMENTE de update.py (espejo de la agregación de process_season).
    Reconstruye el `stats` que compute_league_ranks recibe en attach_ranks."""
    st = {}

    def ensure(t):
        st.setdefault(t, {'pts': 0, 'gd': 0, 'gf': 0, 'gf_away': 0,
                          'wins': 0, 'wins_away': 0})

    for (h, a, hg, ag) in matches:
        ensure(h); ensure(a)
        st[h]['gf'] += hg; st[h]['gd'] += hg - ag
        st[a]['gf'] += ag; st[a]['gd'] += ag - hg; st[a]['gf_away'] += ag
        if hg > ag:
            st[h]['pts'] += 3; st[h]['wins'] += 1
        elif ag > hg:
            st[a]['pts'] += 3; st[a]['wins'] += 1; st[a]['wins_away'] += 1
        else:
            st[h]['pts'] += 1; st[a]['pts'] += 1
    return st


def _replay_expected_rk(matches, lg, universe):
    """Oráculo derivado de la DEFINICIÓN del ADR (no de la implementación): para
    cada corte, la tabla OFICIAL de la liga sobre TODO el `universo` de equipos con
    los puntos/goles del prefijo — un equipo con 0 partidos está en la tabla con 0
    puntos y GD 0, no fuera de ella. `cum` se siembra con el universo completo
    ANTES del bucle (igual que `td` en process_season, que se construye desde
    todas las filas de `df` ∪ calendario), de modo que cada corte es permutación
    1..N con N = len(universe) FIJO, no una fracción que crece con las filas.
    Devuelve (expected_rk_por_equipo, cortes)."""
    cum = {t: {'pts': 0, 'gf': 0, 'ga': 0, 'gf_away': 0, 'wins': 0, 'wins_away': 0}
           for t in universe}
    season_matches = []
    expected = {}
    cortes = []
    for (h, a, hg, ag) in matches:
        cum[h]['gf'] += hg; cum[h]['ga'] += ag
        cum[a]['gf'] += ag; cum[a]['ga'] += hg
        cum[a]['gf_away'] += ag
        if hg > ag:
            cum[h]['pts'] += 3; cum[h]['wins'] += 1
        elif ag > hg:
            cum[a]['pts'] += 3; cum[a]['wins'] += 1; cum[a]['wins_away'] += 1
        else:
            cum[h]['pts'] += 1; cum[a]['pts'] += 1
        season_matches.append((h, a, hg, ag))
        stats_now = {t: {'pts': c['pts'], 'gd': c['gf'] - c['ga'], 'gf': c['gf'],
                         'gf_away': c['gf_away'], 'wins': c['wins'],
                         'wins_away': c['wins_away']}
                     for t, c in cum.items()}
        ranks_now = update.compute_league_ranks(stats_now, season_matches, lg)
        cortes.append(ranks_now)
        expected.setdefault(h, []).append(ranks_now[h])
        expected.setdefault(a, []).append(ranks_now[a])
    return expected, cortes


# Fixture La Liga: triple empate (X, Y, Z) a 12 puntos resuelto por PUNTOS de la
# mini-liga (X > Y > Z), portado de test_tiebreakers. Rellenos únicos (T9x) que
# juegan un solo partido, nunca empatan con los contendientes.
def _la_liga_tie_matches():
    X, Y, Z = 'T00', 'T01', 'T02'
    m = [
        (X, Y, 2, 0), (Y, X, 0, 1),   # X gana ambos vs Y
        (X, Z, 1, 1), (Z, X, 0, 0),   # X y Z empatan ambos
        (Y, Z, 3, 0), (Z, Y, 1, 2),   # Y gana ambos vs Z
    ]
    # h2h puntos: X=8, Y=6, Z=2. Igualamos totales a 12 con relleno controlado.
    fill = 90

    def top_up(team, n_wins, n_draws):
        nonlocal fill
        for _ in range(n_wins):
            m.append((team, f'T{fill}', 2, 0)); fill += 1
        for _ in range(n_draws):
            m.append((team, f'T{fill}', 1, 1)); fill += 1

    top_up(X, 1, 1)   # +4 -> 12
    top_up(Y, 2, 0)   # +6 -> 12
    top_up(Z, 3, 1)   # +10 -> 12
    return m, (X, Y, Z)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_len_rk_matches_len_a():
    """(a) `rk` tiene una entrada por partido jugado: len(rk) == len(a)."""
    matches, _ = _la_liga_tie_matches()
    df = _matches_to_df(matches)
    p = update.PARAMS['ll']
    res = update.process_season(df, _wages_for(matches),
                                p['beta'], p['theta1'], p['theta2'], None, 'll')
    for t, b in res.items():
        assert len(b['rk']) == len(b['a']), \
            f"{t}: len(rk)={len(b['rk'])} != len(a)={len(b['a'])}"
    print("OK (a) len(rk) == len(a) por equipo")


def test_last_rk_equals_rank():
    """(b) `rk[-1] == rank` para todo equipo con partidos."""
    matches, _ = _la_liga_tie_matches()
    df = _matches_to_df(matches)
    p = update.PARAMS['ll']
    res = update.process_season(df, _wages_for(matches),
                                p['beta'], p['theta1'], p['theta2'], None, 'll')
    for t, b in res.items():
        if b['rk']:
            assert b['rk'][-1] == b['rank'], \
                f"{t}: rk[-1]={b['rk'][-1]} != rank={b['rank']}"
    print("OK (b) rk[-1] == rank (invariante)")


def test_rk_matches_official_replay_and_permutation():
    """(c) `rk` coincide fila a fila con la clasificación oficial recalculada
    sobre el prefijo con el UNIVERSO COMPLETO de la liga (definición del ADR),
    cada corte es permutación 1..N sobre los N equipos de la liga, y el estado
    final refleja el desempate por mini-liga."""
    matches, (X, Y, Z) = _la_liga_tie_matches()
    df = _matches_to_df(matches)
    # Universo = todos los equipos que aparecen en df (mismo criterio que `td` en
    # process_season, que se construye desde todas las filas). Fijo, no crece.
    universe = sorted({h for h, _, _, _ in matches} | {a for _, a, _, _ in matches})
    N = len(universe)
    p = update.PARAMS['ll']
    res = update.process_season(df, _wages_for(matches),
                                p['beta'], p['theta1'], p['theta2'], None, 'll')

    expected, cortes = _replay_expected_rk(matches, 'll', universe)
    # Cada corte: permutación exacta 1..N sobre TODA la liga (universo fijo). Un
    # equipo con 0 partidos ocupa su sitio en el grupo de empate a 0 puntos; el
    # corte NO es un rango dentro del subconjunto que ya jugó.
    for i, ranks_now in enumerate(cortes):
        assert len(ranks_now) == N, \
            f"corte {i}: universo {len(ranks_now)} != N={N} (debe ser fijo)"
        assert sorted(ranks_now.values()) == list(range(1, N + 1)), \
            f"corte {i}: rk no es permutación 1..{N}: {sorted(ranks_now.values())}"

    # attach_ranks fija rk[-1] al rank oficial de fin de temporada; la réplica
    # debe aplicar el mismo cierre para comparar (todos los equipos han jugado,
    # sin sembrado: el rank final == compute sobre los equipos con partidos).
    final = res  # rank ya es la clasificación oficial completa
    for t in expected:
        expected[t][-1] = final[t]['rank']
        assert res[t]['rk'] == expected[t], \
            f"{t}: rk={res[t]['rk']} != esperado {expected[t]}"

    # El desempate a puntos (12) se resuelve por mini-liga: X < Y < Z en rango.
    assert res[X]['a'][-1] == res[Y]['a'][-1] == res[Z]['a'][-1], \
        "X, Y, Z deben estar empatados a puntos totales"
    assert res[X]['rank'] < res[Y]['rank'] < res[Z]['rank'], \
        (f"desempate por mini-liga esperado X<Y<Z, got "
         f"{res[X]['rank']},{res[Y]['rank']},{res[Z]['rank']}")
    print("OK (c) rk = clasificación oficial por corte sobre el universo completo "
          "(permutación 1..N, desempate por mini-liga en el estado final)")


def test_first_cut_is_full_league_table():
    """(c') Universo del corte = liga entera. Siembra una liga de N=6 equipos por
    calendario y procesa UN solo partido decisivo (h gana). La tabla oficial en
    ese instante: ganador 1º (3 pts); los 4 equipos sin jugar, empatados a 0 pts y
    GD 0, en el medio; perdedor ÚLTIMO (0 pts, GD negativo). Por tanto el perdedor
    recibe `rk[0] == N` y el ganador `rk[0] == 1`. Con el universo reducido del
    🔴 el perdedor recibía `rk[0] == 2` (rango dentro de {ganador, perdedor})."""
    teams = [f'T{i:02d}' for i in range(6)]
    N = len(teams)
    # Calendario que siembra los 6 equipos (3 emparejamientos); solo se juega el
    # primero. process_season construye `td` con los 6 desde el arranque.
    cal = [{'gw': 1,
            'matches': [[teams[0], teams[1]], [teams[2], teams[3]], [teams[4], teams[5]]],
            'dates': ['2026-08-15T17:00:00Z', '2026-08-15T17:00:00Z', '2026-08-15T17:00:00Z']}]
    fixtures_cal = {'ll': {update.CURRENT_SEASON: {'calendar': cal}}}
    # df con un único partido: T00 (local) gana 2-0 a T01.
    df = _matches_to_df([(teams[0], teams[1], 2, 0)])
    wages = {t: 100 - i for i, t in enumerate(teams)}
    wages['_min'] = min(wages.values())
    p = update.PARAMS['ll']
    res = update.process_season(df, wages, p['beta'], p['theta1'], p['theta2'],
                                fixtures_cal, 'll')

    assert len(res[teams[0]]['rk']) == 1 and len(res[teams[1]]['rk']) == 1
    # attach_ranks fija rk[-1]==rank; con un solo partido rk[0] es también el
    # último corte, así que rk[0] == rank (universo completo en ambos).
    assert res[teams[1]]['rk'][0] == N, \
        f"perdedor: rk[0]={res[teams[1]]['rk'][0]} != N={N} (universo reducido?)"
    assert res[teams[0]]['rk'][0] == 1, \
        f"ganador: rk[0]={res[teams[0]]['rk'][0]} != 1"
    # Los 4 equipos sembrados sin jugar quedan con rk=[] (0 partidos) pero sí
    # pueblan la tabla del corte: ocupan los rangos 2..5.
    seeded_ranks = sorted(res[t]['rank'] for t in teams[2:])
    assert seeded_ranks == [2, 3, 4, 5], \
        f"sembrados sin jugar deben ocupar 2..5, got {seeded_ranks}"
    print("OK (c') corte inicial sobre liga entera: perdedor rk[0]==N, no 2")


def test_no_regresion_campos_existentes_bit_identicos():
    """(d) Activar/desactivar la maquinaria de rk/rank (pertenencia a
    TIEBREAKERS) deja a/e/m/w/gd bit-idénticos; `rank` coincide con la
    clasificación oficial. El campo aditivo no perturba nada existente."""
    matches, _ = _la_liga_tie_matches()
    df = _matches_to_df(matches)
    wages = _wages_for(matches)
    p = update.PARAMS['ll']

    # OFF: sin 'll' en TIEBREAKERS, el branch de rk se salta y attach_ranks es
    # no-op (no asigna rank ni toca rk). Es el comportamiento del código PREVIO
    # sobre los campos existentes para esta misma df.
    saved = update.TIEBREAKERS.pop('ll')
    try:
        off = update.process_season(df.copy(), wages,
                                    p['beta'], p['theta1'], p['theta2'], None, 'll')
    finally:
        update.TIEBREAKERS['ll'] = saved
    # ON: maquinaria activa.
    on = update.process_season(df.copy(), wages,
                               p['beta'], p['theta1'], p['theta2'], None, 'll')

    assert set(on.keys()) == set(off.keys())
    for t in off:
        for field in ('a', 'e', 'm', 'w', 'gd'):
            assert on[t][field] == off[t][field], \
                (f"{t}.{field} cambió al activar rk/rank: "
                 f"on={on[t][field]!r} off={off[t][field]!r}")
        assert 'rank' not in off[t] or off[t].get('rank') is None
        assert isinstance(on[t]['rank'], int)
    # `rank` bit-idéntico al código previo: el rank que emite el código previo es
    # compute_league_ranks(stats_totales, matches, lg) — reconstruido aquí desde
    # cero (compute_league_ranks y TIEBREAKERS quedan intactos en este PR).
    official = update.compute_league_ranks(_final_standings(matches), matches, 'll')
    for t in on:
        assert on[t]['rank'] == official[t], \
            f"{t}: rank={on[t]['rank']} != clasificación oficial {official[t]}"
    # …y permutación completa 1..N sobre el bloque ON.
    n = len(on)
    assert sorted(on[t]['rank'] for t in on) == list(range(1, n + 1))
    print("OK (d) a/e/m/w/gd bit-idénticos con rk/rank on/off; rank == oficial")


def test_preseason_block_emits_empty_rk():
    """Equipos sin partidos (build_preseason_block) llevan `rk: []` (contrato
    punto 4): mantiene el invariante len(rk)==len(a) con a=[] y no rompe el
    consumo del frontend en la rama pre-season."""
    teams = [f'T{i:02d}' for i in range(6)]
    cal = [{'gw': i + 1, 'matches': [[teams[2 * (i % 3)], teams[2 * (i % 3) + 1]]],
            'dates': ['2026-08-15T17:00:00Z']} for i in range(6)]
    fx = {'ll': {update.CURRENT_SEASON: {'calendar': cal}}}
    wages = {t: 100 - i for i, t in enumerate(teams)}
    wages['_min'] = min(wages.values())

    block = update.build_preseason_block(fx, wages, 'll')
    assert block, "el bloque pre-season no debe estar vacío"
    for t, b in block.items():
        assert b['rk'] == [], f"{t}: pre-season debe emitir rk=[], got {b.get('rk')!r}"
        assert b['a'] == [] and len(b['rk']) == len(b['a'])
    print("OK (pre-season) build_preseason_block emite rk=[] (len(rk)==len(a))")


if __name__ == '__main__':
    test_len_rk_matches_len_a()
    test_last_rk_equals_rank()
    test_rk_matches_official_replay_and_permutation()
    test_first_cut_is_full_league_table()
    test_no_regresion_campos_existentes_bit_identicos()
    test_preseason_block_emits_empty_rk()
    print("\nTODOS LOS TESTS OK (rk[] rango oficial por partido, ADR-005·R·2)")
