#!/usr/bin/env python3
"""
Tests de backfill_rk.py — reconstrucción de `rk[]`/`rank` en temporadas
históricas y verificación de consistencia contra `a[]` almacenado (ADR-005·R·2).

Ejecutable standalone con exit code (asserts, sin prints de resultado):
    python3 test_backfill_rk.py

Cubre (estilo test_tiebreakers.py):
  (a) CSV sintético 4 equipos × 12 partidos + bloque consistente ⇒ `rk` adjuntado,
      len(rk)==len(a), rk[-1]==rank, `rank` añadido.
  (b) mismo CSV con un `a[]` alterado en un elemento ⇒ SKIPPED, bloque de entrada
      byte-idéntico (json.dumps antes/después).
  (c) bloque con `rank` preexistente que NO coincide con el rango final calculado
      ⇒ SKIPPED.
  (d) el resto de campos (`a`, `e`, `m`, `w`) byte-idénticos en el caso (a).

No requiere pandas/numpy: importa solo los helpers puros usados por backfill_rk.
"""
import copy
import json

from backfill_rk import (
    parse_csv_matches,
    compute_rk_and_ranks,
    build_block,
)

LG = 'll'
SN = '13/14'


# ---------------------------------------------------------------------------
# Fixture sintético: 4 equipos, doble round-robin completo (12 partidos)
# ---------------------------------------------------------------------------
TEAMS = ['Alfa', 'Bravo', 'Charlie', 'Delta']

# (home, away, home_goals, away_goals) — 12 partidos (cada par juega ida y vuelta).
# Marcadores variados para que la clasificación final sea una permutación clara.
MATCHES = [
    ('Alfa', 'Bravo', 2, 0),
    ('Charlie', 'Delta', 1, 1),
    ('Alfa', 'Charlie', 3, 1),
    ('Bravo', 'Delta', 0, 2),
    ('Alfa', 'Delta', 1, 0),
    ('Bravo', 'Charlie', 2, 2),
    ('Bravo', 'Alfa', 1, 1),
    ('Delta', 'Charlie', 0, 3),
    ('Charlie', 'Alfa', 0, 2),
    ('Delta', 'Bravo', 1, 1),
    ('Delta', 'Alfa', 0, 0),
    ('Charlie', 'Bravo', 2, 1),
]


def make_csv(matches):
    """Serializa `matches` en un CSV de football-data.co.uk mínimo pero válido
    para parse_csv_matches (Div/Date/HomeTeam/AwayTeam/FTHG/FTAG/FTR)."""
    lines = ['Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR']
    for (h, a, hg, ag) in matches:
        ftr = 'H' if hg > ag else 'A' if ag > hg else 'D'
        lines.append(f'SP1,01/01/2014,{h},{a},{hg},{ag},{ftr}')
    return '\n'.join(lines) + '\n'


def replay_a(matches):
    """Reconstruye {team: a[]} (puntos acumulados por partido del equipo, en
    orden de filas) de forma independiente al código bajo test."""
    cp = {}
    a = {}
    for (h, ag_team, hg, ag) in matches:
        for t in (h, ag_team):
            cp.setdefault(t, 0)
            a.setdefault(t, [])
        if hg > ag:
            cp[h] += 3
        elif ag > hg:
            cp[ag_team] += 3
        else:
            cp[h] += 1
            cp[ag_team] += 1
        a[h].append(cp[h])
        a[ag_team].append(cp[ag_team])
    return a


def consistent_block(matches):
    """Bloque data.json sintético CONSISTENTE con `matches`: `a[]` correcto y
    campos `e`/`m`/`w` plausibles (no verificados, pero presentes para (d))."""
    a_map = replay_a(matches)
    block = {}
    for t in sorted(a_map):
        a = a_map[t]
        block[t] = {
            'a': list(a),
            'e': [round(0.5 * (i + 1), 1) for i in range(len(a))],
            'm': [['Rival', 1, 3, 1.23] for _ in range(len(a))],
            'w': 50,
        }
    return block


# ---------------------------------------------------------------------------
# (a) reconstrucción sobre bloque consistente
# ---------------------------------------------------------------------------
def test_a_reconstruccion_ok():
    text = make_csv(MATCHES)
    parsed = parse_csv_matches(text)
    assert len(parsed) == 12, len(parsed)
    td, final_ranks = compute_rk_and_ranks(parsed, LG)
    assert sorted(final_ranks.values()) == [1, 2, 3, 4], final_ranks

    block = consistent_block(MATCHES)
    new_block, reason = build_block(block, td, final_ranks, LG, SN)
    assert reason is None, reason
    for t in new_block:
        assert 'rk' in new_block[t], t
        assert 'rank' in new_block[t], t
        assert len(new_block[t]['rk']) == len(new_block[t]['a']), t
        assert new_block[t]['rk'][-1] == new_block[t]['rank'], t
        assert new_block[t]['rank'] == final_ranks[t], t
        # cada equipo jugó 6 partidos (doble round-robin de 4)
        assert len(new_block[t]['a']) == 6, (t, len(new_block[t]['a']))
        # rk es un rango válido 1..4 en cada corte
        assert all(1 <= r <= 4 for r in new_block[t]['rk']), (t, new_block[t]['rk'])
    # el bloque de ENTRADA no se muta (no gana rk/rank)
    for t in block:
        assert 'rk' not in block[t] and 'rank' not in block[t], t


# ---------------------------------------------------------------------------
# (b) a[] alterado ⇒ SKIPPED y bloque de entrada byte-idéntico
# ---------------------------------------------------------------------------
def test_b_a_alterado_skipped_byte_identico():
    text = make_csv(MATCHES)
    parsed = parse_csv_matches(text)
    td, final_ranks = compute_rk_and_ranks(parsed, LG)

    block = consistent_block(MATCHES)
    victim = sorted(block)[0]
    block[victim]['a'][3] += 1  # rompe la consistencia en un solo elemento

    before = json.dumps(block, sort_keys=True)
    new_block, reason = build_block(block, td, final_ranks, LG, SN)
    after = json.dumps(block, sort_keys=True)

    assert new_block is None, new_block
    assert reason is not None and reason.startswith('SKIPPED'), reason
    assert victim in reason, reason
    assert before == after, 'build_block mutó el bloque de entrada'


# ---------------------------------------------------------------------------
# (c) rank preexistente incongruente ⇒ SKIPPED
# ---------------------------------------------------------------------------
def test_c_rank_preexistente_incongruente_skipped():
    text = make_csv(MATCHES)
    parsed = parse_csv_matches(text)
    td, final_ranks = compute_rk_and_ranks(parsed, LG)

    block = consistent_block(MATCHES)
    for t in block:
        block[t]['rank'] = 99  # rango imposible (1..4) ⇒ nunca coincide

    before = json.dumps(block, sort_keys=True)
    new_block, reason = build_block(block, td, final_ranks, LG, SN)
    after = json.dumps(block, sort_keys=True)

    assert new_block is None, new_block
    assert reason is not None and reason.startswith('SKIPPED'), reason
    assert 'rank' in reason, reason
    assert before == after, 'build_block mutó el bloque de entrada'


# ---------------------------------------------------------------------------
# (d) a/e/m/w byte-idénticos tras la reconstrucción del caso (a)
# ---------------------------------------------------------------------------
def test_d_campos_existentes_byte_identicos():
    text = make_csv(MATCHES)
    parsed = parse_csv_matches(text)
    td, final_ranks = compute_rk_and_ranks(parsed, LG)

    block = consistent_block(MATCHES)
    snapshot = copy.deepcopy(block)
    new_block, reason = build_block(block, td, final_ranks, LG, SN)
    assert reason is None, reason

    for t in snapshot:
        for field in ('a', 'e', 'm', 'w'):
            assert new_block[t][field] == snapshot[t][field], (t, field)
            # y el bloque de entrada sigue igual (no mutado)
            assert block[t][field] == snapshot[t][field], (t, field)


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    tests = [
        test_a_reconstruccion_ok,
        test_b_a_alterado_skipped_byte_identico,
        test_c_rank_preexistente_incongruente_skipped,
        test_d_campos_existentes_byte_identicos,
    ]
    for t in tests:
        t()
    print(f'OK: {len(tests)} tests de backfill_rk (ADR-005·R·2) pasan')
