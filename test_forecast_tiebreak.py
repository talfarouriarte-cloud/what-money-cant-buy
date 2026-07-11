#!/usr/bin/env python3
"""
Tests de regresión del desempate del forecast (ADR-006).

Regla única del forecast: orden por (puntos simulados desc, rank oficial
actual asc). Sustituye al ruido aleatorio intra-simulación y al argsort por
índice de la rama de temporada completa. La pretemporada (sin rank) conserva
el ruido.

Ejecutable standalone con exit code (asserts):
    python3 test_forecast_tiebreak.py

Requiere numpy (lo usa simulate_position_probs). NO requiere red ni
pandas/scipy/requests: el import de update.py es resiliente por dependencia
(ADR-006) y esta prueba construye los match_list a mano. Los datos salen de
`data.json` del repo.

Cubre:
  (a) Rama de temporada completa (n_matches == 0) sobre `ll` 25/26: las
      categorías emitidas coinciden EXACTAMENTE con el rank oficial
      (compute_league_ranks / ADR-005) — Osasuna `rel == 0.0` (rank 17/20,
      se salva) y los tres descendidos reales `rel == 1.0`. Imprime
      `osasuna_rel=0.0` para el invariante 2 de la épica.
  (b) Rama simulada: dos equipos empatados en puntos en TODAS las ramas; el
      de mejor `current_ranks` queda delante en el 100% de las sims (el
      desempate ya no es moneda) — verificado en ambos sentidos del rank.
  (c) Pretemporada (current_ranks=None): el motor conserva el ruido — no
      colapsa determinista a un único orden.
"""
import json
import sys

try:
    import numpy as np
except ImportError:  # pragma: no cover
    print("FALLO: numpy no disponible (requerido por simulate_position_probs). "
          "Instala con: pip install numpy")
    sys.exit(1)

from update import simulate_position_probs


# ---------------------------------------------------------------------------
# (a) Rama de temporada completa sobre datos reales — regresión Osasuna 25/26
# ---------------------------------------------------------------------------
def test_full_branch_matches_official_ranks():
    with open('data.json') as f:
        data = json.load(f)
    sd = data['seasons']['ll']['25/26']
    teams = list(sd.keys())
    # Todos los equipos deben tener rank oficial (ADR-005) en data.json.
    assert all(sd[t].get('rank') for t in teams), "faltan ranks oficiales en ll 25/26"

    current_pts = np.array([sd[t]['a'][-1] if sd[t]['a'] else 0 for t in teams])
    current_ranks = {t: sd[t]['rank'] for t in teams}

    # match_list vacío ⇒ rama de temporada completa (n_matches == 0).
    res = simulate_position_probs(teams, current_pts, [], n_sims=1000, lg='ll',
                                  current_ranks=current_ranks)

    n_teams = len(teams)
    n_rel = 3  # La Liga: 3 descensos (LEAGUE_SPOTS['ll']['rel'])

    # El p50 emitido debe ser EXACTAMENTE el rank oficial de cada equipo, y la
    # categoría rel debe encender solo para los últimos n_rel del rank oficial.
    for t in teams:
        rank = sd[t]['rank']
        assert res[t]['p50'] == rank, \
            f"{t}: p50={res[t]['p50']} != rank oficial {rank}"
        expected_rel = 1.0 if rank >= n_teams - n_rel + 1 else 0.0
        assert res[t]['rel'] == expected_rel, \
            f"{t} (rank {rank}): rel={res[t]['rel']} esperado {expected_rel}"

    # Regresión concreta: Osasuna (rank 17/20) se salva pese al triple empate
    # a 42 puntos que el bug resolvía por índice del array (Rel 100% falso).
    osasuna_rel = res['Osasuna']['rel']
    assert osasuna_rel == 0.0, f"Osasuna rel={osasuna_rel} (esperado 0.0)"
    assert sd['Osasuna']['rank'] == 17, "precondición: Osasuna rank 17"

    # Los tres descendidos reales (rank 18, 19, 20) con rel == 1.0.
    relegated = sorted((t for t in teams if sd[t]['rank'] >= 18),
                       key=lambda t: sd[t]['rank'])
    assert len(relegated) == 3, f"esperados 3 descendidos, hay {len(relegated)}"
    for t in relegated:
        assert res[t]['rel'] == 1.0, f"{t} (rank {sd[t]['rank']}): rel={res[t]['rel']} != 1.0"

    # Invariante 2 de la épica: línea que el Auditor pega desde develop mergeado.
    print(f"osasuna_rel={osasuna_rel}")
    print("OK (a) rama completa: categorías == rank oficial; "
          f"Osasuna rel 0.0; descendidos {relegated} rel 1.0")


# ---------------------------------------------------------------------------
# (b) Rama simulada — el mejor current_ranks gana el empate en el 100% de sims
# ---------------------------------------------------------------------------
def _two_tied_teams(better):
    """Escenario sintético: A y B empatados a 10 pts en TODAS las ramas (el
    único partido es entre C y D, que nunca los alcanzan). `better` es el
    equipo con mejor (menor) rank oficial. Devuelve el dict de resultados."""
    teams = ['A', 'B', 'C', 'D']
    current_pts = np.array([10, 10, 0, 0])
    # 1 partido C(2) vs D(3): mantiene a A y B intactos y hace n_matches>0.
    match_list = [(2, 3, 0.5, 0.3)]
    ranks = {'A': 1, 'B': 2, 'C': 3, 'D': 4} if better == 'A' \
        else {'A': 2, 'B': 1, 'C': 3, 'D': 4}
    return teams, simulate_position_probs(teams, current_pts, match_list,
                                          n_sims=2000, lg='ll', current_ranks=ranks)


def test_simulated_branch_tiebreak_is_deterministic():
    # A mejor rank ⇒ A queda 1º en el 100% de las sims; B nunca.
    _, res = _two_tied_teams(better='A')
    assert res['A']['1st'] == 1.0, f"A debería ser 1º siempre, 1st={res['A']['1st']}"
    assert res['B']['1st'] == 0.0, f"B nunca 1º, 1st={res['B']['1st']}"

    # Invertir el rank invierte el ganador ⇒ lo decide current_ranks, no el índice.
    _, res2 = _two_tied_teams(better='B')
    assert res2['B']['1st'] == 1.0, f"B debería ser 1º siempre, 1st={res2['B']['1st']}"
    assert res2['A']['1st'] == 0.0, f"A nunca 1º, 1st={res2['A']['1st']}"

    print("OK (b) rama simulada: el mejor rank gana el empate en el 100% "
          "de las sims (ambos sentidos)")


# ---------------------------------------------------------------------------
# (c) Pretemporada — sin rank el desempate sigue siendo aleatorio (ruido)
# ---------------------------------------------------------------------------
def test_preseason_keeps_noise():
    teams = ['A', 'B', 'C', 'D']
    current_pts = np.array([10, 10, 0, 0])
    match_list = [(2, 3, 0.5, 0.3)]
    # current_ranks=None (default) ⇒ pretemporada: ruido. El empate A/B se
    # reparte, no colapsa determinista a un único ganador.
    res = simulate_position_probs(teams, current_pts, match_list, n_sims=2000,
                                  lg='ll', current_ranks=None)
    a1 = res['A']['1st']
    assert 0.0 < a1 < 1.0, f"sin rank el empate debe ser moneda, 1st(A)={a1}"
    print(f"OK (c) pretemporada: empate resuelto por ruido (1st A ~ {a1})")


if __name__ == '__main__':
    test_full_branch_matches_official_ranks()
    test_simulated_branch_tiebreak_is_deterministic()
    test_preseason_keeps_noise()
    print("\nTODOS LOS TESTS OK (ADR-006)")
