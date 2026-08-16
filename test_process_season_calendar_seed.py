#!/usr/bin/env python3
"""
Tests de `process_season` sembrando el universo de equipos desde el calendario
(issue #80).

Bug: con pocos resultados (p. ej. La Liga 26/27 a 2 partidos jugados) el bloque
de CURRENT_SEASON quedaba SOLO con los equipos que aparecen en los resultados;
los demás equipos de la liga desaparecían de la temporada actual. La causa:
`process_season` construía `td` exclusivamente desde `df['HomeTeam']/AwayTeam`,
sin usar el calendario (`fixtures_calendar`) que ya recibe para `gw_lookup`.

Contrato (issue #80):
  1. Con `fixtures_calendar` y `lg` disponibles y calendario de CURRENT_SEASON
     con equipos, `td` se siembra con TODOS los equipos del calendario (vía
     fix_name) además de los de `df`. Los equipos sin partidos jugados quedan
     con las estructuras vacías (a=[], e=[], m=[], gd=0) — mismo estado que
     build_preseason_block.
  2. Los equipos CON partidos jugados conservan números IDÉNTICOS a los del
     código previo (el sembrado no altera el núcleo numérico).
  3. Sin calendario (ligas históricas, llamadas sin `lg`): comportamiento
     previo intacto — `td` solo desde `df`, byte-idéntico.

DoD: DataFrame de 2 partidos + calendario de 20 equipos → bloque de 20 equipos,
y los 4 con partidos con números idénticos a los del código actual.

Ejecutable standalone con exit code (asserts):
    python3 test_process_season_calendar_seed.py

Requiere pandas + numpy + scipy (los usa process_season). NO requiere red ni
data.json: todo el escenario es sintético.
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

CS = update.CURRENT_SEASON


def _teams(n):
    """Nombres deterministas T00..T{n-1}; no colisionan con NAME_MAP (fix_name
    es identidad sobre ellos), así el roster esperado es exactamente estos."""
    return [f'T{i:02d}' for i in range(n)]


def _round_robin_calendar(teams):
    """Doble round-robin: cada par ordenado (h, a) es una jornada con fecha.
    Cubre a los 20 equipos aunque ninguno haya jugado todavía."""
    pairs = [(h, a) for h in teams for a in teams if h != a]
    return [
        {'gw': i + 1, 'matches': [[h, a]],
         'dates': [f'2026-08-{(i % 28) + 1:02d}T17:00:00Z']}
        for i, (h, a) in enumerate(pairs)
    ]


def _two_match_df(teams):
    """DataFrame de 2 partidos entre 4 de los equipos (formato API con goles)."""
    h0, a0, h1, a1 = teams[0], teams[1], teams[2], teams[3]
    return pd.DataFrame({
        'HomeTeam': [h0, h1],
        'AwayTeam': [a0, a1],
        'FTHG':     [2, 1],
        'FTAG':     [0, 1],
        'FTR':      ['H', 'D'],
    })


def test_block_seeded_with_all_calendar_teams():
    """(1) DataFrame de 2 partidos + calendario de 20 → bloque de 20 equipos.
    Los 16 sin jugar quedan con a/e/m vacíos y gd=0."""
    teams = _teams(20)
    cal = _round_robin_calendar(teams)
    fx = {'ll': {CS: {'calendar': cal}}}
    wages = {t: 100 - i for i, t in enumerate(teams)}
    wages['_min'] = min(wages.values())
    p = update.PARAMS['ll']
    df = _two_match_df(teams)

    result = update.process_season(df, wages, p['beta'], p['theta1'], p['theta2'], fx, 'll')

    assert set(result.keys()) == set(teams), \
        f"el bloque debe cubrir los 20 equipos del calendario, got {sorted(result.keys())}"
    assert len(result) == 20, f"esperados 20 equipos, got {len(result)}"

    played = {teams[0], teams[1], teams[2], teams[3]}
    for t in teams:
        if t in played:
            assert result[t]['a'], f"{t} jugó: `a` no debe estar vacío"
        else:
            b = result[t]
            assert b['a'] == [] and b['e'] == [] and b['m'] == [] and b['gd'] == 0, \
                f"{t} sin jugar debe tener a/e/m=[] y gd=0, got {b}"
    print("OK (1) bloque sembrado con los 20 equipos; los 16 sin jugar con estructuras vacías")


def test_played_teams_numbers_unchanged_by_seeding():
    """(2) Los equipos CON partidos conservan números idénticos: el sembrado
    solo AÑADE equipos vacíos, jamás altera la agregación de los que jugaron.

    El sembrado es inerte para el núcleo numérico (a/e/w/gd y el core de cada
    entrada de `m`: opp/ih/pts/exp). El baseline es la MISMA `df` sin calendario,
    que reproduce la agregación del código previo para los equipos con partidos.
    Los índices gw (4) y date (5) de `m` derivan del calendario vía gw_lookup/
    date_lookup — ya presentes antes de este issue cuando se pasa calendario— y
    por eso se excluyen de la comparación (en el baseline sin calendario valen
    0/'')."""
    teams = _teams(20)
    cal = _round_robin_calendar(teams)
    fx = {'ll': {CS: {'calendar': cal}}}
    wages = {t: 100 - i for i, t in enumerate(teams)}
    wages['_min'] = min(wages.values())
    p = update.PARAMS['ll']
    df = _two_match_df(teams)

    seeded = update.process_season(df, wages, p['beta'], p['theta1'], p['theta2'], fx, 'll')
    # Sin calendario: universo solo desde `df` (4 equipos). Reproduce la
    # agregación del código previo para los equipos con partidos.
    df_only = update.process_season(df.copy(), wages, p['beta'], p['theta1'], p['theta2'], None, None)

    for t in df_only:
        assert t in seeded, f"{t} (con partidos) debe seguir en el bloque sembrado"
        for field in ('a', 'e', 'w', 'gd'):
            assert seeded[t][field] == df_only[t][field], \
                (f"{t}.{field} cambió al sembrar el calendario: "
                 f"seeded={seeded[t][field]!r} df_only={df_only[t][field]!r}")
        # Core de cada partido (opp/ih/pts/exp) inalterado; gw/date vienen del
        # calendario (idénticos al código previo con calendario) => se excluyen.
        assert len(seeded[t]['m']) == len(df_only[t]['m']), \
            f"{t}: nº de partidos cambió: {len(seeded[t]['m'])} vs {len(df_only[t]['m'])}"
        for ms, md in zip(seeded[t]['m'], df_only[t]['m']):
            assert ms[:4] == md[:4], \
                f"{t}: core del partido cambió al sembrar: {ms[:4]!r} vs {md[:4]!r}"
    print("OK (2) equipos con partidos: a/e/w/gd y core de `m` idénticos con y sin sembrado")


def test_no_calendar_behavior_unchanged():
    """(3) Sin calendario (o sin lg): `td` solo desde `df` — comportamiento
    previo intacto, byte-idéntico."""
    teams = _teams(20)
    wages = {t: 100 - i for i, t in enumerate(teams)}
    wages['_min'] = min(wages.values())
    p = update.PARAMS['ll']
    df = _two_match_df(teams)

    # Sin fixtures_calendar
    r1 = update.process_season(df.copy(), wages, p['beta'], p['theta1'], p['theta2'], None, 'll')
    # Con fixtures_calendar pero sin lg (llamada de liga histórica)
    fx = {'ll': {CS: {'calendar': _round_robin_calendar(teams)}}}
    r2 = update.process_season(df.copy(), wages, p['beta'], p['theta1'], p['theta2'], fx, None)

    for r, label in ((r1, 'sin calendario'), (r2, 'sin lg')):
        assert set(r.keys()) == {teams[0], teams[1], teams[2], teams[3]}, \
            f"{label}: el universo debe ser solo los 4 equipos de df, got {sorted(r.keys())}"
    print("OK (3) sin calendario/sin lg: universo solo desde df (comportamiento previo)")


def test_full_pipeline_tolerates_zero_played():
    """(2 del contrato) El resto del pipeline (ranks, remaining, MC) tolera un
    bloque mixto: 4 equipos con partidos + 16 con 0 jugados. Reproduce el
    encadenado real de update()."""
    teams = _teams(20)
    cal = _round_robin_calendar(teams)
    fx = {'ll': {CS: {'calendar': cal}}}
    wages = {t: 100 - i for i, t in enumerate(teams)}
    wages['_min'] = min(wages.values())
    p = update.PARAMS['ll']
    df = _two_match_df(teams)

    result = update.process_season(df, wages, p['beta'], p['theta1'], p['theta2'], fx, 'll')

    # attach_ranks (dentro de process_season) debe dar rank a los 20 (permutación).
    ranks = [result[t].get('rank') for t in teams]
    assert sorted(ranks) == list(range(1, 21)), \
        f"rank debe ser permutación completa 1..20 sobre todo el bloque, got {sorted(ranks)}"

    # remaining + MC no deben romperse con equipos de 0 jugados.
    remaining = update.get_remaining_fixtures(result, fx, 'll')
    np.random.seed(0)
    bands = update.run_mc_simulation(result, wages, p['beta'], p['theta1'], p['theta2'], remaining)
    assert set(bands.keys()) == set(teams), "las bandas deben cubrir los 20 equipos"

    # Posiciones (camino con partidos: _has_real_block True).
    cur = update.simulate_current_positions(result, wages, p['beta'], p['theta1'], p['theta2'], remaining, lg='ll')
    assert set(cur.keys()) == set(teams), "las posiciones deben cubrir los 20 equipos"
    print("OK (pipeline) ranks 1..20, MC y posiciones toleran los 16 equipos con 0 jugados")


if __name__ == '__main__':
    test_block_seeded_with_all_calendar_teams()
    test_played_teams_numbers_unchanged_by_seeding()
    test_no_calendar_behavior_unchanged()
    test_full_pipeline_tolerates_zero_played()
    print("\nTODOS LOS TESTS OK (process_season siembra calendario, issue #80)")
