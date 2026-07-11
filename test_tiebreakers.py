#!/usr/bin/env python3
"""
Tests de los criterios de desempate de la clasificación real (ADR-005).

Ejecutable standalone con exit code (asserts, sin prints de resultado):
    python3 test_tiebreakers.py

Cubre (9 tests):
  - 6 unitarios, uno por liga, con fixtures sintéticos que ejercitan la
    cadena de TIEBREAKERS de esa liga (La Liga con triple empate resuelto
    por mini-liga).
  - 1 de contorno (a): enfrentamientos incompletos -> criterios generales.
  - 1 de integridad: rank es permutación exacta 1..N en toda liga x temporada
    del fixture.
  - 1 de no-regresión: attach_ranks no altera los campos existentes del dict
    de temporada (a, e, m, w, gd) — salen bit-idénticos.

No requiere pandas/numpy: importa solo los helpers puros de update.py.
"""
import copy
from update import (
    TIEBREAKERS,
    compute_league_ranks,
    attach_ranks,
)


# ---------------------------------------------------------------------------
# Helpers de fixture sintético
# ---------------------------------------------------------------------------
def standings(matches):
    """Calcula los totales de temporada {team: {pts,gd,gf,gf_away,wins,wins_away}}
    a partir de una lista de partidos (home, away, home_goals, away_goals).
    Espeja la agregación de process_season en update.py."""
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


def top_up(matches, team, n_wins, n_draws, gf_per_win=2, tag=''):
    """Añade partidos contra rivales de relleno ÚNICOS (cada uno juega un solo
    partido, así nunca empatan con los contendientes) para sumar puntos de forma
    controlada: n_wins victorias `gf_per_win`-0 y n_draws empates 1-1.
    Suma 3*n_wins + n_draws puntos al equipo. Devuelve la lista de partidos."""
    added = []
    for k in range(n_wins):
        added.append((team, f'F_{team}{tag}_w{k}', gf_per_win, 0))
    for k in range(n_draws):
        added.append((team, f'F_{team}{tag}_d{k}', 1, 1))
    matches.extend(added)
    return added


def ranks_of(matches, lg):
    return compute_league_ranks(standings(matches), matches, lg)


# ---------------------------------------------------------------------------
# 6 tests unitarios, uno por liga
# ---------------------------------------------------------------------------
def test_la_liga_triple_empate_mini_liga():
    """La Liga: particular puntos -> particular GD -> general GD -> goles marcados.
    Triple empate (A, B, C) a puntos, resuelto por PUNTOS de la mini-liga."""
    m = [
        # Mini-liga A,B,C (doble round-robin completo -> contorno (a) OK)
        ('A', 'B', 2, 0), ('B', 'A', 0, 1),   # A gana ambos vs B
        ('A', 'C', 1, 1), ('C', 'A', 0, 0),   # A y C empatan ambos
        ('B', 'C', 3, 0), ('C', 'B', 1, 2),   # B gana ambos vs C
    ]
    # h2h puntos: A=8, B=6, C=2. Igualamos totales a 12 compensando con relleno.
    top_up(m, 'A', 1, 1)   # +4 -> 12
    top_up(m, 'B', 2, 0)   # +6 -> 12
    top_up(m, 'C', 3, 1)   # +10 -> 12
    r = ranks_of(m, 'll')
    assert r['A'] == 1 and r['B'] == 2 and r['C'] == 3, r


def test_serie_a_particular_gd():
    """Serie A: misma cadena que La Liga. Empate a puntos y a PUNTOS de la
    mini-liga -> resuelve la DIFERENCIA de goles particular (A > C > B)."""
    m = [
        ('A', 'B', 5, 0), ('B', 'A', 1, 0),   # split, h2h_gd: A +4, B -4
        ('B', 'C', 3, 0), ('C', 'B', 1, 0),   # split, h2h_gd: B +2, C -2
        ('C', 'A', 2, 0), ('A', 'C', 1, 0),   # split, h2h_gd: C +1, A -1
    ]
    # h2h puntos todos = 6 (2 victorias, 2 derrotas). h2h_gd: A=+3, C=-1, B=-2.
    top_up(m, 'A', 0, 2)   # +2 -> 8
    top_up(m, 'B', 0, 2)   # +2 -> 8
    top_up(m, 'C', 0, 2)   # +2 -> 8
    r = ranks_of(m, 'sa')
    assert r['A'] == 1 and r['C'] == 2 and r['B'] == 3, r


def test_premier_general_luego_particular():
    """Premier: general GD -> goles marcados -> particular puntos -> particular
    goles fuera. Un trío se separa por goles marcados generales; un par que
    empata en TODO lo general se separa por goles marcados fuera particulares."""
    # A,B,C: cada uno 2 victorias con MISMO GD general (+4) y goles marcados distintos.
    m = [
        ('A', 'FA1', 4, 2), ('A', 'FA2', 4, 2),   # A: 6pts, gd+4, gf8
        ('B', 'FB1', 3, 1), ('B', 'FB2', 3, 1),   # B: 6pts, gd+4, gf6
        ('C', 'FC1', 2, 0), ('C', 'FC2', 2, 0),   # C: 6pts, gd+4, gf4
        # G,H: empatan a puntos(3), GD(0), gf(3) y a puntos particulares (3);
        # solo los separa los GOLES MARCADOS FUERA particulares (G marca 1 fuera, H 0).
        ('G', 'H', 2, 0), ('H', 'G', 3, 1),
    ]
    r = ranks_of(m, 'pl')
    assert r['A'] == 1 and r['B'] == 2 and r['C'] == 3, r
    st = standings(m)
    assert st['G']['pts'] == st['H']['pts'] and st['G']['gd'] == st['H']['gd'] \
        and st['G']['gf'] == st['H']['gf']
    assert r['G'] == 4 and r['H'] == 5, r


def test_bundesliga_particular_agregado():
    """Bundesliga: general GD -> goles marcados -> particular (agregado=GD) ->
    particular goles fuera -> goles fuera general. A y B empatan a puntos,
    GD general y goles marcados; los separa el GD particular (A > B)."""
    m = [
        ('A', 'B', 3, 1), ('B', 'A', 1, 1),   # h2h_gd: A +2, B -2
    ]
    # A: pts4 gd+2 gf4 ; B: pts1 gd-2 gf2. Igualamos a pts10, gd+2, gf10.
    top_up(m, 'A', 0, 6)                        # 6 empates 1-1: +6pts, gd0, gf+6 -> pts10 gd+2 gf10
    m += [('B', 'FBw0', 2, 0), ('B', 'FBw1', 2, 0),           # +6pts, gd+4, gf+4
          ('B', 'FBd0', 2, 2), ('B', 'FBd1', 1, 1), ('B', 'FBd2', 1, 1)]  # +3pts, gd0, gf+4
    # B: pts 1+9=10, gd -2+4=+2, gf 2+8=10
    r = ranks_of(m, 'bl')
    st = standings(m)
    assert st['A']['pts'] == st['B']['pts'] == 10
    assert st['A']['gd'] == st['B']['gd'] and st['A']['gf'] == st['B']['gf']
    assert r['A'] == 1 and r['B'] == 2, r


def test_ligue1_particular_puntos():
    """Ligue 1: general GD -> particular puntos -> particular GD -> goles
    marcados -> victorias -> victorias fuera. A y B empatan a puntos y GD
    general; los separa los PUNTOS particulares (A gana el head-to-head)."""
    m = [
        ('A', 'B', 1, 0), ('B', 'A', 0, 0),   # h2h pts: A 4, B 1
    ]
    # A: pts4 gd+1 ; B: pts1 gd-1. Igualamos a pts10, gd+1.
    top_up(m, 'A', 0, 6)                        # +6pts, gd0 -> pts10 gd+1
    m += [('B', 'FBw0', 1, 0), ('B', 'FBw1', 1, 0),            # +6pts, gd+2
          ('B', 'FBd0', 0, 0), ('B', 'FBd1', 0, 0), ('B', 'FBd2', 0, 0)]  # +3pts, gd0
    # B: pts 1+9=10, gd -1+2=+1
    r = ranks_of(m, 'l1')
    st = standings(m)
    assert st['A']['pts'] == st['B']['pts'] == 10 and st['A']['gd'] == st['B']['gd']
    assert r['A'] == 1 and r['B'] == 2, r


def test_eredivisie_goles_marcados():
    """Eredivisie: general GD -> goles marcados -> particular. A y B empatan a
    puntos y GD general; los separa los GOLES MARCADOS generales (A > B)."""
    m = []
    m += [('A', 'FAw0', 4, 2), ('A', 'FAw1', 4, 2),           # A: +6pts gd+4 gf8
          ('A', 'FAd0', 2, 2), ('A', 'FAd1', 2, 2),
          ('A', 'FAd2', 2, 2), ('A', 'FAd3', 2, 2)]           # +4pts gd0 gf8 -> pts10 gd+4 gf16
    m += [('B', 'FBw0', 2, 0), ('B', 'FBw1', 2, 0),           # B: +6pts gd+4 gf4
          ('B', 'FBd0', 0, 0), ('B', 'FBd1', 0, 0),
          ('B', 'FBd2', 0, 0), ('B', 'FBd3', 0, 0)]           # +4pts gd0 gf0 -> pts10 gd+4 gf4
    r = ranks_of(m, 'ed')
    st = standings(m)
    assert st['A']['pts'] == st['B']['pts'] == 10 and st['A']['gd'] == st['B']['gd']
    assert st['A']['gf'] > st['B']['gf']
    assert r['A'] == 1 and r['B'] == 2, r


# ---------------------------------------------------------------------------
# Contorno (a): enfrentamientos incompletos -> criterios generales
# ---------------------------------------------------------------------------
def test_contorno_a_incompletos_saltan_a_generales():
    """La Liga (particular-first). A y B empatan a puntos pero solo se han
    enfrentado UNA vez (ida y vuelta incompletas): los criterios particulares
    se saltan y decide el GD general. A ganaría el head-to-head, pero B tiene
    mejor GD general -> B debe quedar por delante."""
    m = [('A', 'B', 1, 0)]                      # solo un enfrentamiento
    top_up(m, 'A', 0, 7)                        # A: +7pts (empates 1-1) -> pts10, gd+1
    m += [('B', 'FBw0', 5, 0), ('B', 'FBw1', 5, 0), ('B', 'FBw2', 5, 0),
          ('B', 'FBd0', 0, 0)]                  # B: +10pts, gd+15 -> pts10, gd+14
    r = ranks_of(m, 'll')
    st = standings(m)
    assert st['A']['pts'] == st['B']['pts'] == 10
    assert st['B']['gd'] > st['A']['gd']
    # Si el particular se aplicara, A (ganó el h2h) iría delante. Contorno (a) lo impide:
    assert r['B'] == 1 and r['A'] == 2, r


# ---------------------------------------------------------------------------
# Integridad: rank es permutación 1..N en toda liga x temporada del fixture
# ---------------------------------------------------------------------------
def _all_league_fixtures():
    """Reconstruye los fixtures de los tests unitarios, uno por liga."""
    fx = {}

    m = [('A', 'B', 2, 0), ('B', 'A', 0, 1), ('A', 'C', 1, 1), ('C', 'A', 0, 0),
         ('B', 'C', 3, 0), ('C', 'B', 1, 2)]
    top_up(m, 'A', 1, 1); top_up(m, 'B', 2, 0); top_up(m, 'C', 3, 1)
    fx['ll'] = m

    m = [('A', 'B', 5, 0), ('B', 'A', 1, 0), ('B', 'C', 3, 0), ('C', 'B', 1, 0),
         ('C', 'A', 2, 0), ('A', 'C', 1, 0)]
    top_up(m, 'A', 0, 2); top_up(m, 'B', 0, 2); top_up(m, 'C', 0, 2)
    fx['sa'] = m

    fx['pl'] = [('A', 'FA1', 4, 2), ('A', 'FA2', 4, 2), ('B', 'FB1', 3, 1),
                ('B', 'FB2', 3, 1), ('C', 'FC1', 2, 0), ('C', 'FC2', 2, 0),
                ('G', 'H', 2, 0), ('H', 'G', 3, 1)]

    m = [('A', 'B', 3, 1), ('B', 'A', 1, 1)]
    top_up(m, 'A', 0, 6)
    m += [('B', 'FBw0', 2, 0), ('B', 'FBw1', 2, 0), ('B', 'FBd0', 2, 2),
          ('B', 'FBd1', 1, 1), ('B', 'FBd2', 1, 1)]
    fx['bl'] = m

    m = [('A', 'B', 1, 0), ('B', 'A', 0, 0)]
    top_up(m, 'A', 0, 6)
    m += [('B', 'FBw0', 1, 0), ('B', 'FBw1', 1, 0), ('B', 'FBd0', 0, 0),
          ('B', 'FBd1', 0, 0), ('B', 'FBd2', 0, 0)]
    fx['l1'] = m

    m = [('A', 'FAw0', 4, 2), ('A', 'FAw1', 4, 2), ('A', 'FAd0', 2, 2),
         ('A', 'FAd1', 2, 2), ('A', 'FAd2', 2, 2), ('A', 'FAd3', 2, 2),
         ('B', 'FBw0', 2, 0), ('B', 'FBw1', 2, 0), ('B', 'FBd0', 0, 0),
         ('B', 'FBd1', 0, 0), ('B', 'FBd2', 0, 0), ('B', 'FBd3', 0, 0)]
    fx['ed'] = m
    return fx


def test_integridad_permutacion_completa():
    """rank debe ser una permutación exacta 1..N en cada liga x temporada."""
    for lg, m in _all_league_fixtures().items():
        r = compute_league_ranks(standings(m), m, lg)
        n = len(standings(m))
        assert len(r) == n, (lg, len(r), n)
        assert sorted(r.values()) == list(range(1, n + 1)), (lg, sorted(r.values()))


# ---------------------------------------------------------------------------
# No-regresión: attach_ranks no altera los campos existentes del dict
# ---------------------------------------------------------------------------
def test_no_regresion_campos_bit_identicos():
    """attach_ranks añade 'rank' pero deja a/e/m/w/gd bit-idénticos."""
    # Dict de temporada representativo (como el que emite process_season).
    season_before = {
        'A': {'a': [3, 6, 9], 'e': [1.2, 2.4, 3.6], 'm': [['B', 1, 3, 1.5]],
              'w': 120, 'gd': 5},
        'B': {'a': [0, 1, 4], 'e': [1.1, 2.0, 2.9], 'm': [['A', 0, 0, 0.9]],
              'w': 80, 'gd': -3},
    }
    matches = [('A', 'B', 2, 0), ('B', 'A', 1, 1)]
    stats = standings(matches)
    # Alinear puntos con el dict de temporada (a[-1]) para un caso realista.
    stats['A']['pts'] = season_before['A']['a'][-1]
    stats['B']['pts'] = season_before['B']['a'][-1]

    snapshot = copy.deepcopy(season_before)
    season_after = attach_ranks(season_before, stats, matches, 'll')

    for t in snapshot:
        for field in ('a', 'e', 'm', 'w', 'gd'):
            assert season_after[t][field] == snapshot[t][field], (t, field)
        assert 'rank' in season_after[t] and isinstance(season_after[t]['rank'], int)
    assert sorted(season_after[t]['rank'] for t in season_after) == [1, 2]


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    tests = [
        test_la_liga_triple_empate_mini_liga,
        test_serie_a_particular_gd,
        test_premier_general_luego_particular,
        test_bundesliga_particular_agregado,
        test_ligue1_particular_puntos,
        test_eredivisie_goles_marcados,
        test_contorno_a_incompletos_saltan_a_generales,
        test_integridad_permutacion_completa,
        test_no_regresion_campos_bit_identicos,
    ]
    for t in tests:
        t()
    print(f'OK: {len(tests)} tests de desempate ADR-005 pasan')
