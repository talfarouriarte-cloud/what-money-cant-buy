#!/usr/bin/env python3
"""
Tests de la trayectoria p50 de posición por jornada (ADR-011).

La vista Position dibujaba el tramo futuro de la línea p50 como una
interpolación lineal en el frontend. ADR-011 sustituye ese artefacto por la
salida real del modelo: `simulate_position_probs` corta la clasificación de
cada réplica tras cada jornada restante y emite `traj = [[g, p50_g], ...]`.

Ejecutable standalone con exit code (asserts):
    python3 test_position_traj.py

Requiere numpy (lo usa simulate_position_probs). NO requiere red. Los datos
salen de `data.json` + `fixtures.json` del repo.

Cubre (issue #110):
  1. match_gws=None ⇒ ningún result[team] tiene clave `traj` (compatibilidad).
  2. match_gws completo (todas jornadas conocidas) sobre La Liga 26/27 real:
     para todo equipo traj[-1][1] == p50; len(traj) == nº de jornadas distintas
     con partidos simulados; cada p50_g ∈ [1, n_teams]; jornadas crecientes.
  3. n_matches == 0 ⇒ traj == [] y categorías idénticas al caso actual.
  4. Determinismo del tally (2 equipos, current_ranks dado, partido único de
     jornada 5 con ph=1.0): traj == [[5, p50]] con el ganador en rango 1 en el
     100% de las réplicas.
  5. Imprime el tiempo de simulate_position_probs con y sin match_gws (§5).
"""
import json
import sys
import time

try:
    import numpy as np
except ImportError:  # pragma: no cover
    print("FALLO: numpy no disponible (requerido por simulate_position_probs). "
          "Instala con: pip install numpy")
    sys.exit(1)

from update import (simulate_position_probs, build_match_list,
                    get_remaining_fixtures, _current_ranks_from_season,
                    load_wages, PARAMS, CURRENT_SEASON)

LG = 'll'


def _liga_real():
    """Prepara los insumos reales de La Liga temporada en curso: teams,
    current_pts, current_ranks, match_list y match_gws (con jornadas)."""
    with open('data.json') as f:
        data = json.load(f)
    with open('fixtures.json') as f:
        fixtures = json.load(f)
    sd = data['seasons'][LG][CURRENT_SEASON]
    teams = list(sd.keys())
    wages = load_wages(LG, CURRENT_SEASON)
    wages['_min'] = min(v for v in wages.values())
    p = PARAMS[LG]
    remaining = get_remaining_fixtures(sd, fixtures, LG)
    match_list, match_gws = build_match_list(teams, wages, remaining,
                                             p['beta'], p['theta1'], p['theta2'],
                                             with_gw=True)
    current_pts = np.array([sd[t]['a'][-1] if sd[t]['a'] else 0 for t in teams])
    current_ranks = _current_ranks_from_season(sd, teams)
    return teams, current_pts, current_ranks, match_list, match_gws


# ---------------------------------------------------------------------------
# (1) Compatibilidad: match_gws=None ⇒ sin clave `traj`
# ---------------------------------------------------------------------------
def test_none_has_no_traj():
    teams, current_pts, current_ranks, match_list, _ = _liga_real()
    res = simulate_position_probs(teams, current_pts, match_list, n_sims=1000,
                                  lg=LG, current_ranks=current_ranks)
    for t in teams:
        assert 'traj' not in res[t], f"{t}: no debería haber `traj` con match_gws=None"
    print("OK (1) compatibilidad: match_gws=None no emite `traj`")


# ---------------------------------------------------------------------------
# (2) Trayectoria completa sobre datos reales: invariante y forma
# ---------------------------------------------------------------------------
def test_full_trajectory_invariant():
    teams, current_pts, current_ranks, match_list, match_gws = _liga_real()
    n_teams = len(teams)
    # Precondición del invariante fuerte: TODAS las jornadas conocidas (>0).
    assert all(g for g in match_gws), \
        "precondición: todos los partidos restantes con jornada conocida"
    distinct_gws = sorted({g for g in match_gws})

    res = simulate_position_probs(teams, current_pts, match_list, n_sims=10000,
                                  lg=LG, current_ranks=current_ranks,
                                  match_gws=match_gws)
    for t in teams:
        traj = res[t]['traj']
        # Invariante ADR-011: el corte de la última jornada ES el tally final.
        assert traj[-1][1] == res[t]['p50'], \
            f"{t}: traj[-1][1]={traj[-1][1]} != p50={res[t]['p50']}"
        # Una entrada por jornada distinta con partidos simulados.
        assert len(traj) == len(distinct_gws), \
            f"{t}: len(traj)={len(traj)} != jornadas distintas {len(distinct_gws)}"
        gws_seen = [g for g, _ in traj]
        assert gws_seen == distinct_gws, f"{t}: jornadas del traj != jornadas simuladas"
        # Estrictamente crecientes.
        assert all(gws_seen[i] < gws_seen[i + 1] for i in range(len(gws_seen) - 1)), \
            f"{t}: jornadas del traj no estrictamente crecientes"
        # Cada mediana es un rango válido.
        for g, p50_g in traj:
            assert 1 <= p50_g <= n_teams, f"{t} gw{g}: p50_g={p50_g} fuera de [1,{n_teams}]"
    print(f"OK (2) trayectoria real: invariante traj[-1]==p50 para {n_teams} equipos; "
          f"{len(distinct_gws)} jornadas ({distinct_gws[0]}..{distinct_gws[-1]}); "
          "medianas en rango; jornadas crecientes")


# ---------------------------------------------------------------------------
# (3) n_matches == 0 ⇒ traj == [] y categorías intactas
# ---------------------------------------------------------------------------
def test_no_matches_empty_traj():
    teams, current_pts, current_ranks, _, _ = _liga_real()
    # match_list vacío ⇒ rama de temporada completa (n_matches == 0).
    res_traj = simulate_position_probs(teams, current_pts, [], n_sims=1000, lg=LG,
                                       current_ranks=current_ranks, match_gws=[])
    res_base = simulate_position_probs(teams, current_pts, [], n_sims=1000, lg=LG,
                                       current_ranks=current_ranks)
    for t in teams:
        assert res_traj[t]['traj'] == [], f"{t}: traj debería ser [] con 0 partidos"
        # Categorías y p50 idénticos al caso sin match_gws (mismo orden oficial).
        for k in ('1st', 'ucl', 'uel', 'ucol', 'mid', 'rel', 'p50'):
            assert res_traj[t][k] == res_base[t][k], \
                f"{t}: categoría {k} difiere con/sin match_gws en n_matches==0"
    print("OK (3) n_matches==0: traj==[] y categorías idénticas (mismo orden oficial)")


# ---------------------------------------------------------------------------
# (4) Determinismo del tally: partido único ph=1.0 en jornada 5
# ---------------------------------------------------------------------------
def test_deterministic_single_match():
    teams = ['A', 'B']
    current_pts = np.array([0, 0])
    # Un único partido A(local) vs B en jornada 5, con ph=1.0 (A gana siempre).
    match_list = [(0, 1, 1.0, 0.0)]
    match_gws = [5]
    ranks = {'A': 1, 'B': 2}  # current_ranks dado ⇒ rama lexsort determinista
    res = simulate_position_probs(teams, current_pts, match_list, n_sims=1000,
                                  lg=LG, current_ranks=ranks, match_gws=match_gws)
    # A gana en el 100% de réplicas ⇒ rango 1 siempre; B rango 2 siempre.
    assert res['A']['traj'] == [[5, 1]], f"A: traj={res['A']['traj']} (esperado [[5,1]])"
    assert res['B']['traj'] == [[5, 2]], f"B: traj={res['B']['traj']} (esperado [[5,2]])"
    assert res['A']['1st'] == 1.0, f"A debería ser 1º siempre, 1st={res['A']['1st']}"
    assert res['A']['p50'] == 1 and res['B']['p50'] == 2
    assert res['A']['traj'][-1][1] == res['A']['p50']  # invariante
    print("OK (4) determinismo: partido único jornada 5 ph=1.0 ⇒ traj==[[5,p50]], ganador rango 1")


# ---------------------------------------------------------------------------
# (5) Coste medido: tiempo con y sin match_gws (§5 del issue)
# ---------------------------------------------------------------------------
def test_report_timing():
    teams, current_pts, current_ranks, match_list, match_gws = _liga_real()
    n_sims = 10000
    t0 = time.time()
    simulate_position_probs(teams, current_pts, match_list, n_sims=n_sims, lg=LG,
                            current_ranks=current_ranks, match_gws=match_gws)
    t_with = time.time() - t0
    t0 = time.time()
    simulate_position_probs(teams, current_pts, match_list, n_sims=n_sims, lg=LG,
                            current_ranks=current_ranks, match_gws=None)
    t_without = time.time() - t0
    print(f"TIMING (La Liga {CURRENT_SEASON} real, n_sims={n_sims}, "
          f"{len(match_list)} partidos): "
          f"con match_gws={t_with:.2f}s · sin match_gws={t_without:.2f}s")


if __name__ == '__main__':
    test_none_has_no_traj()
    test_full_trajectory_invariant()
    test_no_matches_empty_traj()
    test_deterministic_single_match()
    test_report_timing()
    print("\nTODOS LOS TESTS OK (ADR-011)")
