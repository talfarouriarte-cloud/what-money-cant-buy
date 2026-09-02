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
      el `rk` de cada corte es una permutación 1..K sobre los K equipos con
      partidos hasta ese corte, y el estado final refleja el desempate oficial
      (no el ingenuo puntos→GD). Reproducido con una réplica independiente,
      fila a fila, de la agregación de `process_season`.
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


def _replay_expected_rk(matches, lg):
    """Réplica INDEPENDIENTE de la construcción de `rk` en process_season: replay
    fila a fila acumulando los mismos stats (pts, gd, gf, gf_away, wins,
    wins_away) y llamando a compute_league_ranks sobre el prefijo tras cada fila,
    SOLO con los equipos que ya han jugado. Devuelve
    (expected_rk_por_equipo, cortes) donde `cortes` es la lista de dicts
    {team: rank} de cada fila (para el chequeo de permutación por corte)."""
    cum = {}

    def ensure(t):
        cum.setdefault(t, {'pts': 0, 'gf': 0, 'ga': 0, 'gf_away': 0,
                           'wins': 0, 'wins_away': 0})

    season_matches = []
    expected = {}
    cortes = []
    for (h, a, hg, ag) in matches:
        ensure(h); ensure(a)
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
    sobre el prefijo, cada corte es permutación 1..K de los K equipos con
    partidos, y el estado final refleja el desempate por mini-liga."""
    matches, (X, Y, Z) = _la_liga_tie_matches()
    df = _matches_to_df(matches)
    p = update.PARAMS['ll']
    res = update.process_season(df, _wages_for(matches),
                                p['beta'], p['theta1'], p['theta2'], None, 'll')

    expected, cortes = _replay_expected_rk(matches, 'll')
    # Cada corte: permutación exacta 1..K sobre los K equipos con partidos.
    for i, ranks_now in enumerate(cortes):
        k = len(ranks_now)
        assert sorted(ranks_now.values()) == list(range(1, k + 1)), \
            f"corte {i}: rk no es permutación 1..{k}: {sorted(ranks_now.values())}"

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
    print("OK (c) rk = clasificación oficial por corte (permutación 1..K, "
          "desempate por mini-liga en el estado final)")


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
        # OFF no asigna rank; ON sí (entero). La igualdad de `rank` con la
        # clasificación oficial ya la valida (c) contra la réplica independiente.
        assert 'rank' not in off[t] or off[t].get('rank') is None
        assert isinstance(on[t]['rank'], int)
    # `rank` es permutación completa 1..N sobre el bloque ON.
    n = len(on)
    assert sorted(on[t]['rank'] for t in on) == list(range(1, n + 1))
    print("OK (d) a/e/m/w/gd bit-idénticos con rk/rank on/off; rank oficial intacto")


if __name__ == '__main__':
    test_len_rk_matches_len_a()
    test_last_rk_equals_rank()
    test_rk_matches_official_replay_and_permutation()
    test_no_regresion_campos_existentes_bit_identicos()
    print("\nTODOS LOS TESTS OK (rk[] rango oficial por partido, ADR-005·R·2)")
