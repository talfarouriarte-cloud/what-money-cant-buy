#!/usr/bin/env python3
"""
Tests del bloque pre-season para CURRENT_SEASON sin resultados (issue #59).

Cuando el rollover escribe el calendario de la temporada nueva en fixtures.json
pero data.json aún no tiene bloque para ella (ni resultados API ni CSV),
update.py construye un bloque pre-season (0 partidos jugados) desde el
calendario en lugar de saltar la liga. Este test construye ese bloque desde un
fixtures sintético y verifica el contrato (puntos 1-6 del issue):

  1. Roster derivado del calendario (nombres vía fix_name), NUNCA de las claves
     de salarios: un equipo con salario pero sin partidos no entra; un equipo
     del calendario sin salario propio entra con el fallback.
  2. Por equipo: a=[], e=[], m=[], gd=0, w=salario fallback y `r` completo con
     todas las jornadas del calendario y probabilidades (build_remaining_r).
  3. `bands` (run_mc_simulation, desde jornada 0) y `pre`
     (recalculate_budget_bands) tienen el mismo roster y su p50 es IDÉNTICO por
     construcción (0 jugados => determinista sobre el mismo calendario).
  4. Narrativas: una liga con 0 partidos jugados emite {}.
  5. wage_status: si load_wages rellenó por fallback, detect_wage_status
     devuelve 'stale' (no 'fresh' por mera ausencia de la clave); sin fallback
     (temporada realmente vacía) sigue siendo 'fresh'.
  6. cumulative: una temporada con 0 jugados no aporta nada al acumulado.

Ejecutable standalone con exit code (asserts):
    python3 test_preseason.py

Requiere numpy y scipy (los usan run_mc_simulation / recalculate_budget_bands).
NO requiere red ni data.json: todo el escenario es sintético.
"""
import copy
import sys

try:
    import numpy as np
except ImportError:  # pragma: no cover
    print("FALLO: numpy no disponible (requerido por run_mc_simulation). "
          "Instala con: pip install numpy")
    sys.exit(1)

import update

if update.expit is None:  # pragma: no cover
    print("FALLO: scipy no disponible (expit requerido por el motor). "
          "Instala con: pip install scipy")
    sys.exit(1)

CS = update.CURRENT_SEASON
_prev_y = int(CS[:2]) - 1
PREV = f'{_prev_y:02d}/{_prev_y+1:02d}'


def _synthetic_calendar(teams):
    """Doble round-robin: cada par ordenado (h, a) es una jornada con fecha.
    Cada equipo juega 2*(n-1) partidos (mitad en casa, mitad fuera)."""
    pairs = [(h, a) for h in teams for a in teams if h != a]
    return [
        {'gw': i + 1, 'matches': [[h, a]],
         'dates': [f'2026-08-{(i % 28) + 1:02d}T17:00:00Z']}
        for i, (h, a) in enumerate(pairs)
    ]


def test_roster_from_calendar_not_wages():
    """(1) Roster desde el calendario, nunca desde las claves de salarios."""
    teams = ['A', 'B', 'C', 'D']
    cal = _synthetic_calendar(teams)
    fx = {'ll': {CS: {'calendar': cal}}}
    # 'Z' tiene salario pero NO está en el calendario => no debe entrar.
    # 'D' está en el calendario pero NO tiene salario propio => entra con el
    # fallback de diseño para ascendidos: el mínimo de liga `_min` (correctivo
    # #62; antes caía a 0 y rompía presupuesto/ratios de los ascendidos).
    wages = {'A': 100.0, 'B': 50.0, 'C': 30.0, 'Z': 999.0, '_min': 30.0}

    block = update.build_preseason_block(fx, wages, 'll')

    assert sorted(block.keys()) == teams, \
        f"roster {sorted(block.keys())} != calendario {teams}"
    assert 'Z' not in block, "un equipo con salario pero sin calendario NO debe entrar"
    assert 'D' in block, "un equipo del calendario sin salario propio DEBE entrar"
    # Ningún equipo del bloque puede quedar con w=0 (presupuesto/ratios rotos).
    assert all(b['w'] != 0 for b in block.values()), \
        f"ningún equipo debe tener w=0; got {{t: b['w'] for t, b in block.items()}}"
    # Un equipo ausente del dict de salarios recibe exactamente round(_min).
    assert block['D']['w'] == round(wages['_min']), \
        f"D sin salario propio => w=round(_min)={round(wages['_min'])}, got {block['D']['w']}"
    assert block['A']['w'] == 100, f"A w esperado 100, got {block['A']['w']}"
    print("OK (1) roster derivado del calendario; ascendidos con w=round(_min), no 0")


def test_team_fields_and_r():
    """(2) Campos por equipo (a/e/m/gd/w vacíos-cero) y `r` completo."""
    teams = ['A', 'B', 'C', 'D']
    cal = _synthetic_calendar(teams)
    fx = {'ll': {CS: {'calendar': cal}}}
    wages = {'A': 100.0, 'B': 50.0, 'C': 30.0, 'D': 20.0, '_min': 20.0}
    p = update.PARAMS['ll']

    block = update.build_preseason_block(fx, wages, 'll')
    for t in teams:
        b = block[t]
        assert b['a'] == [] and b['e'] == [] and b['m'] == [] and b['gd'] == 0, \
            f"{t}: bloque pre-season debe tener a/e/m vacíos y gd=0, got {b}"

    remaining = update.get_remaining_fixtures(block, fx, 'll')
    for t in teams:
        block[t]['r'] = update.build_remaining_r(t, remaining.get(t, []), wages, p)

    for t in teams:
        r = block[t]['r']
        # n=4 equipos => 2*(4-1) = 6 partidos por equipo (todas las jornadas).
        assert len(r) == 6, f"{t}: r debe cubrir las 6 jornadas del calendario, got {len(r)}"
        for entry in r:
            assert len(entry) == 7, f"entrada r mal formada: {entry}"
            opp, is_home, pw, pdr, pl, gw, date = entry
            assert is_home in (0, 1)
            assert abs(pw + pdr + pl - 1.0) <= 0.02, \
                f"{t} vs {opp}: probabilidades no suman ~1: {pw}+{pdr}+{pl}"
            assert gw >= 1 and date, f"{t} vs {opp}: jornada/fecha ausentes: {entry}"
    print("OK (2) a/e/m=[], gd=0, w=fallback y r completo con probabilidades")


def test_bands_and_pre_identical():
    """(3) bands (run_mc desde gw0) y pre (recalculate) mismo roster; p50 idéntico."""
    teams = ['A', 'B', 'C', 'D']
    cal = _synthetic_calendar(teams)
    fx = {'ll': {CS: {'calendar': cal}}}
    wages = {'A': 100.0, 'B': 50.0, 'C': 30.0, 'D': 20.0, '_min': 20.0}
    p = update.PARAMS['ll']

    block = update.build_preseason_block(fx, wages, 'll')
    remaining = update.get_remaining_fixtures(block, fx, 'll')

    np.random.seed(0)
    bands = update.run_mc_simulation(block, wages, p['beta'], p['theta1'], p['theta2'], remaining)
    pre = update.recalculate_budget_bands(fx, wages, p['beta'], p['theta1'], p['theta2'], 'll', block, remaining)

    assert bands, "run_mc_simulation debe producir bandas en pre-season"
    assert pre, "recalculate_budget_bands debe producir bandas en pre-season"
    assert set(bands.keys()) == set(teams) == set(pre.keys()), \
        "bands y pre deben cubrir exactamente el roster del calendario"
    for t in teams:
        # Desde jornada 0: sin puntos bloqueados, la banda cubre las 6 jornadas.
        assert len(bands[t]['p50']) == 6, f"{t}: bands desde gw0 => 6 puntos, got {len(bands[t]['p50'])}"
        assert len(pre[t]['p50']) == 6, f"{t}: pre => 6 puntos, got {len(pre[t]['p50'])}"
        # Con 0 jugados, el p50 (valor esperado determinista) es idéntico por
        # construcción entre ambos caminos (mismo calendario, mismo orden).
        assert bands[t]['p50'] == pre[t]['p50'], \
            f"{t}: p50 debe ser idéntico bands vs pre.\n bands={bands[t]['p50']}\n pre  ={pre[t]['p50']}"
    print("OK (3) bands/pre mismo roster y p50 idéntico por construcción")


def test_narratives_empty_for_zero_played():
    """(4) Una liga con 0 partidos jugados emite narrativas {}."""
    teams = ['A', 'B', 'C', 'D']
    cal = _synthetic_calendar(teams)
    fx = {'ll': {CS: {'calendar': cal}}}
    wages = {'A': 100.0, 'B': 50.0, 'C': 30.0, 'D': 20.0, '_min': 20.0}

    block = update.build_preseason_block(fx, wages, 'll')
    data = {'seasons': {lg: {} for lg in update.PARAMS}}
    data['seasons']['ll'] = {CS: block}

    narr = update.generate_narratives_all(data)
    assert narr.get('ll') == {}, f"liga sin partidos => narrativas {{}}, got {narr.get('ll')!r}"
    print("OK (4) narrativas {} para liga con 0 partidos jugados")


def test_wage_status_stale_on_fallback():
    """(5) detect_wage_status: 'stale' si hubo fallback; 'fresh' sin fallback."""
    teams20 = [f'T{i:02d}' for i in range(20)]
    prev_wages = {t: 40 + i for i, t in enumerate(teams20)}

    # Fallback: la temporada actual no tiene clave propia pero existe la anterior
    # => load_wages rellena desde ella => 'stale' (no 'fresh' por ausencia).
    cache_fb = {'data': {'la_liga': {PREV: prev_wages}}}
    assert update.detect_wage_status('ll', CS, _cache=cache_fb) == 'stale', \
        "ausencia de clave + fallback disponible => 'stale'"
    filled = update.load_wages('ll', CS, _cache=cache_fb)
    assert len(filled) == 20, f"load_wages debe rellenar 20 salarios por fallback, got {len(filled)}"

    # Sin fallback posible (ni actual ni anterior): 'fresh' (comportamiento previo).
    cache_none = {'data': {'la_liga': {}}}
    assert update.detect_wage_status('ll', CS, _cache=cache_none) == 'fresh', \
        "sin datos ni fallback => 'fresh'"

    # Temporada actual presente y distinta de la anterior => 'fresh'.
    cur_distinct = {t: 200 + i for i, t in enumerate(teams20)}
    cache_fresh = {'data': {'la_liga': {PREV: prev_wages, CS: cur_distinct}}}
    assert update.detect_wage_status('ll', CS, _cache=cache_fresh) == 'fresh', \
        "salarios propios distintos => 'fresh'"

    # Temporada actual idéntica a la anterior => 'stale' (deteccion clásica).
    cache_ident = {'data': {'la_liga': {PREV: prev_wages, CS: dict(prev_wages)}}}
    assert update.detect_wage_status('ll', CS, _cache=cache_ident) == 'stale', \
        ">=80% idénticos => 'stale'"
    print("OK (5) wage_status 'stale' por fallback; 'fresh' sin fallback")


def test_cumulative_ignores_zero_played():
    """(6) Una temporada con 0 partidos jugados no aporta nada al acumulado."""
    teams = ['A', 'B', 'C', 'D']
    cal = _synthetic_calendar(teams)
    fx = {'ll': {CS: {'calendar': cal}}}
    wages = {'A': 100.0, 'B': 50.0, 'C': 30.0, 'D': 20.0, '_min': 20.0}

    block = update.build_preseason_block(fx, wages, 'll')
    data = {
        'seasons': {lg: {} for lg in update.PARAMS},
        'cumulative': {'ll': {'A': [5.0, 1, 110.0, [['24/25', 100, 50.0, 55]]]}},
    }
    data['seasons']['ll'] = {CS: block}
    ll_before = copy.deepcopy(data['cumulative']['ll'])

    update.update_cumulative(data)

    assert data['cumulative']['ll'] == ll_before, \
        "el acumulado de la liga NO debe cambiar con 0 jugados"
    has_cs = any(s[0] == CS for c in data['cumulative']['ll'].values() for s in c[3])
    assert not has_cs, f"no debe añadirse ninguna entrada de {CS} al acumulado"
    print("OK (6) cumulative intacto: 0 jugados no aporta nada")


def test_preseason_ranks_permutation():
    """(8) issue #69: el bloque pre-season recibe `rank` como permutación
    completa 1..N (p50 de bands desc; empate w desc; empate nombre asc) y el
    equipo con mayor p50 queda `rank == 1`. Sin esto, officialRanks cae al
    fallback pts->gd y con todos a 0 la clasificación sale en orden de
    inserción del calendario (orden aparentemente aleatorio en producción)."""
    teams = ['A', 'B', 'C', 'D']
    cal = _synthetic_calendar(teams)
    fx = {'ll': {CS: {'calendar': cal}}}
    wages = {'A': 100.0, 'B': 50.0, 'C': 30.0, 'D': 20.0, '_min': 20.0}
    p = update.PARAMS['ll']

    block = update.build_preseason_block(fx, wages, 'll')
    remaining = update.get_remaining_fixtures(block, fx, 'll')

    np.random.seed(0)
    bands = update.run_mc_simulation(block, wages, p['beta'], p['theta1'], p['theta2'], remaining)

    update.attach_preseason_ranks(block, bands)

    ranks = [block[t]['rank'] for t in teams]
    assert sorted(ranks) == list(range(1, len(teams) + 1)), \
        f"`rank` debe ser permutación completa 1..N, got {sorted(ranks)}"
    # Todo equipo tiene rank entero.
    assert all(isinstance(block[t]['rank'], int) for t in teams), \
        "cada `rank` debe ser entero"
    # El equipo con mayor p50 final es rank 1.
    top = max(teams, key=lambda t: bands[t]['p50'][-1])
    assert block[top]['rank'] == 1, \
        f"el equipo con mayor p50 ({top}) debe ser rank 1, got {block[top]['rank']}"
    # El orden de `rank` respeta el p50 descendente (criterio primario).
    by_rank = sorted(teams, key=lambda t: block[t]['rank'])
    p50s = [bands[t]['p50'][-1] for t in by_rank]
    assert p50s == sorted(p50s, reverse=True), \
        f"rank ascendente debe seguir p50 descendente, got {list(zip(by_rank, p50s))}"

    # Determinismo de desempates: p50 empatado => w desc; w empatado => nombre asc.
    tie_block = {
        'Zeta': {'w': 50}, 'Alfa': {'w': 50},   # mismo p50, mismo w => nombre asc
        'Beta': {'w': 90}, 'Gamma': {'w': 10},  # mismo p50, w decide
    }
    tie_bands = {t: {'p50': [0.0, 7.0]} for t in tie_block}  # p50 final idéntico
    update.attach_preseason_ranks(tie_block, tie_bands)
    assert [tie_block[t]['rank'] for t in ['Beta', 'Alfa', 'Zeta', 'Gamma']] == [1, 2, 3, 4], \
        ("desempate: w desc y luego nombre asc => "
         f"Beta<Alfa<Zeta<Gamma, got {{t: tie_block[t]['rank'] for t in tie_block}}")

    # No-op sin señal del modelo: si a un equipo le falta p50, no se asigna rank.
    partial = {'A': {'w': 10}, 'B': {'w': 20}}
    update.attach_preseason_ranks(partial, {'A': {'p50': [1.0]}})  # falta B
    assert all('rank' not in partial[t] for t in partial), \
        "sin p50 completo no se inventa orden (officialRanks cae al fallback)"
    print("OK (8) rank pre-season: permutación 1..N, mayor p50 => rank 1, desempates deterministas")


def test_guard_preserves_real_block_on_outage():
    """(7) Regresión 🔴 #1: con bloque real (N jugados) ya en data.json y sin
    fuente (API+CSV caídos a la vez), la rama pre-season NO se activa — se
    preserva `existing` en vez de resetearlo a 0 jugados.

    La rama del bucle es
        elif not _has_real_block(existing) and fixtures_cal and lg in ... :
    así que `_has_real_block` es exactamente lo que decide entre pre-season y
    el `else`/skip que conserva los datos. Este test cubre esa decisión.
    """
    # Bloque real con jornadas jugadas => la rama pre-season debe QUEDAR FUERA.
    real_block = {
        'A': {'a': [1.0, 1.0], 'e': [0.9, 0.9], 'm': [['B', 1]], 'gd': 2, 'w': 100},
        'B': {'a': [0.0, 3.0], 'e': [1.1, 1.1], 'm': [['A', 0]], 'gd': -2, 'w': 50},
    }
    assert update._has_real_block(real_block), \
        "bloque con `a` no vacío => hay bloque real => NO pre-season (se preserva)"

    # Sin bloque (arranque pre-season): la rama SÍ debe activarse.
    assert not update._has_real_block({}), \
        "sin bloque => pre-season permitido (arranque de temporada)"

    # Bloque pre-season previo (0 jugados, `a` vacío): refresco permitido.
    zero_block = {
        'A': {'a': [], 'e': [], 'm': [], 'gd': 0, 'w': 100},
        'B': {'a': [], 'e': [], 'm': [], 'gd': 0, 'w': 50},
    }
    assert not update._has_real_block(zero_block), \
        "bloque de 0 jugados => pre-season permitido (refresco del bloque pre-season)"

    # Un solo equipo con partidos ya basta para considerarlo bloque real.
    mixed = {
        'A': {'a': [], 'e': [], 'm': [], 'gd': 0, 'w': 100},
        'B': {'a': [2.0], 'e': [1.0], 'm': [['A', 1]], 'gd': 1, 'w': 50},
    }
    assert update._has_real_block(mixed), \
        "al menos un equipo con `a` no vacío => bloque real => se preserva"
    print("OK (7) guarda: bloque real con outage se preserva; pre-season solo sin bloque real")


if __name__ == '__main__':
    test_roster_from_calendar_not_wages()
    test_team_fields_and_r()
    test_bands_and_pre_identical()
    test_narratives_empty_for_zero_played()
    test_wage_status_stale_on_fallback()
    test_cumulative_ignores_zero_played()
    test_preseason_ranks_permutation()
    test_guard_preserves_real_block_on_outage()
    print("\nTODOS LOS TESTS OK (pre-season, issue #59 + #69)")
