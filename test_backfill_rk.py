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
  (e) cronología (`m[i][0]`) alterada con `a[]` intacto ⇒ SKIPPED (la verificación
      ancla al ORDEN de los partidos, no solo a los puntos).
  (f) DIFERENCIAL: `compute_rk_and_ranks`+`build_block` === `process_season`
      (rk/rank por equipo). Requiere pandas; se salta si no está.
  (g)-(k) puerta de escritura `run` y `select_seasons` con downloader inyectado y
      data.json temporal: skip de verificación no escribe (byte-idéntico), skip de
      descarga escribe las verificadas, --check byte-idéntico, escritura +
      idempotencia en re-ejecución, exclusión de CURRENT_SEASON/filtros.

El núcleo (a)-(e) y (g)-(k) no requiere pandas/numpy; solo (f) lo usa (con skip
si falta), preservando el arranque «standalone» del resto de la suite.
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


def replay(matches):
    """Reconstruye {team: {'a': [...], 'm': [...]}} (puntos acumulados y la
    cronología [rival, es_local, puntos, exp] por partido, en orden de filas) de
    forma independiente al código bajo test. Espeja la forma histórica de `m`."""
    cp = {}
    out = {}
    for (h, ag_team, hg, ag) in matches:
        for t in (h, ag_team):
            cp.setdefault(t, 0)
            out.setdefault(t, {'a': [], 'm': []})
        if hg > ag:
            hp, ap = 3, 0
        elif ag > hg:
            hp, ap = 0, 3
        else:
            hp, ap = 1, 1
        cp[h] += hp
        cp[ag_team] += ap
        out[h]['a'].append(cp[h])
        out[ag_team]['a'].append(cp[ag_team])
        out[h]['m'].append([ag_team, 1, hp, 1.23])
        out[ag_team]['m'].append([h, 0, ap, 1.23])
    return out


def consistent_block(matches):
    """Bloque data.json sintético CONSISTENTE con `matches`: `a[]`/`m[]` correctos
    (rival y flag local/visitante reales, que build_block verifica) y campos
    `e`/`w` plausibles (no verificados, pero presentes para (d))."""
    replayed = replay(matches)
    block = {}
    for t in sorted(replayed):
        a = replayed[t]['a']
        block[t] = {
            'a': list(a),
            'e': [round(0.5 * (i + 1), 1) for i in range(len(a))],
            'm': [list(entry) for entry in replayed[t]['m']],
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
# (e) cronología (m[]) alterada ⇒ SKIPPED aunque a[] cuadre
# ---------------------------------------------------------------------------
def test_e_m_alterado_skipped():
    """Prueba que la verificación ancla al ORDEN de los partidos: se altera solo
    el rival de un `m[i]` (dejando `a[]` intacto y consistente) y build_block
    debe cazarlo. `a[]` por sí solo no lo caza."""
    text = make_csv(MATCHES)
    parsed = parse_csv_matches(text)
    td, final_ranks = compute_rk_and_ranks(parsed, LG)

    block = consistent_block(MATCHES)
    victim = sorted(block)[0]
    # rival falso en el primer partido (no toca `a[]`, que sigue cuadrando)
    block[victim]['m'][0][0] = 'Fantasma'

    before = json.dumps(block, sort_keys=True)
    new_block, reason = build_block(block, td, final_ranks, LG, SN)
    after = json.dumps(block, sort_keys=True)

    assert new_block is None, new_block
    assert reason is not None and reason.startswith('SKIPPED'), reason
    assert 'm[' in reason, reason
    assert before == after, 'build_block mutó el bloque de entrada'


# ---------------------------------------------------------------------------
# (f) DIFERENCIAL: compute_rk_and_ranks + build_block === process_season (rk/rank)
# ---------------------------------------------------------------------------
def test_f_diferencial_contra_process_season():
    """La única afirmación que sostiene el PR es «misma mecánica que
    process_season». Este test la convierte en aserción ejecutable: construye el
    DataFrame equivalente a MATCHES, llama a process_season(lg='ll') y assertar
    `rk[]` y `rank` idénticos por equipo a los de backfill_rk. Requiere pandas;
    si no está (fichero «standalone sin deps»), se salta con aviso."""
    try:
        import pandas as pd
    except ImportError:
        print('  (f) SKIP: pandas no disponible')
        return
    from update import process_season

    rows = []
    for (h, a, hg, ag) in MATCHES:
        ftr = 'H' if hg > ag else 'A' if ag > hg else 'D'
        rows.append({'Div': 'SP1', 'Date': '01/01/2014', 'HomeTeam': h,
                     'AwayTeam': a, 'FTHG': hg, 'FTAG': ag, 'FTR': ftr})
    df = pd.DataFrame(rows)
    # wages uniformes (_min): e/m no se comparan, solo rk/rank.
    result = process_season(df, {'_min': 20}, beta=1.0, t1=-0.5, t2=0.5, lg=LG)

    td, final_ranks = compute_rk_and_ranks(parse_csv_matches(make_csv(MATCHES)), LG)
    new_block, reason = build_block(consistent_block(MATCHES), td, final_ranks, LG, SN)
    assert reason is None, reason

    for t in new_block:
        assert result[t]['rk'] == new_block[t]['rk'], (t, result[t]['rk'], new_block[t]['rk'])
        assert result[t]['rank'] == new_block[t]['rank'], (t, result[t]['rank'], new_block[t]['rank'])


# ---------------------------------------------------------------------------
# (g)-(j) cobertura de la puerta de escritura `run` (guardián de data.json)
# ---------------------------------------------------------------------------
import os
import tempfile

from backfill_rk import run, select_seasons, block_has_full_rk
from update import CURRENT_SEASON, TIEBREAKERS

SN2 = '14/15'
assert SN != CURRENT_SEASON and SN2 != CURRENT_SEASON, 'fixture usa temporadas históricas'
assert LG in TIEBREAKERS


def _write_temp_data(seasons):
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'seasons': seasons}, f, ensure_ascii=False)
    return path


def _ok_downloader(lg, sn):
    return make_csv(MATCHES), None


def _fail_downloader_for(bad):
    def dl(lg, sn):
        if (lg, sn) == bad:
            return None, 'status 503 — transitorio'
        return make_csv(MATCHES), None
    return dl


def test_g_run_verificacion_skip_no_escribe():
    """Un SKIPPED de VERIFICACIÓN aborta la escritura completa (todo-o-nada):
    fichero byte-idéntico y run devuelve 1."""
    good = consistent_block(MATCHES)
    bad = consistent_block(MATCHES)
    bad[sorted(bad)[0]]['a'][3] += 1  # rompe la verificación de `a[]`
    path = _write_temp_data({LG: {SN: good, SN2: bad}})
    try:
        with open(path, 'rb') as f:
            before = f.read()
        rc = run(check=False, data_path=path, downloader=_ok_downloader)
        with open(path, 'rb') as f:
            after = f.read()
        assert rc == 1, rc
        assert before == after, 'un skip de verificación no debe escribir nada'
    finally:
        os.remove(path)


def test_h_run_descarga_skip_escribe_verificadas():
    """Un SKIPPED de DESCARGA NO aborta: la temporada verificada se escribe, la
    fallida queda pendiente (idempotencia). run devuelve 1 (hubo skip)."""
    path = _write_temp_data({LG: {SN: consistent_block(MATCHES),
                                  SN2: consistent_block(MATCHES)}})
    try:
        rc = run(check=False, data_path=path, downloader=_fail_downloader_for((LG, SN2)))
        assert rc == 1, rc
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        assert block_has_full_rk(data['seasons'][LG][SN]), 'la verificada debe escribirse'
        assert not block_has_full_rk(data['seasons'][LG][SN2]), 'la fallida queda pendiente'
    finally:
        os.remove(path)


def test_i_run_check_byte_identico():
    """--check con todo OK: fichero byte-idéntico y run devuelve 0."""
    path = _write_temp_data({LG: {SN: consistent_block(MATCHES)}})
    try:
        with open(path, 'rb') as f:
            before = f.read()
        rc = run(check=True, data_path=path, downloader=_ok_downloader)
        with open(path, 'rb') as f:
            after = f.read()
        assert rc == 0, rc
        assert before == after, '--check no debe escribir'
    finally:
        os.remove(path)


def test_j_run_write_luego_idempotente():
    """Sin --check y todo OK: escribe (rk/rank añadidos) y la RE-EJECUCIÓN es
    no-op (select_seasons vacío) — la idempotencia que el docstring promete."""
    path = _write_temp_data({LG: {SN: consistent_block(MATCHES)}})
    try:
        rc1 = run(check=False, data_path=path, downloader=_ok_downloader)
        assert rc1 == 0, rc1
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        assert block_has_full_rk(data['seasons'][LG][SN])
        # re-ejecución: nada seleccionado, nada escrito, byte-idéntico
        assert select_seasons(data, None, None) == []
        with open(path, 'rb') as f:
            before = f.read()
        rc2 = run(check=False, data_path=path, downloader=_ok_downloader)
        with open(path, 'rb') as f:
            after = f.read()
        assert rc2 == 0, rc2
        assert before == after, 're-ejecución debe ser no-op'
    finally:
        os.remove(path)


def test_k_select_seasons_excluye_current_y_filtra():
    """select_seasons excluye CURRENT_SEASON y los bloques con rk completo, y
    respeta los filtros --league/--season."""
    full = consistent_block(MATCHES)
    for t in full:
        full[t]['rk'] = list(range(1, len(full[t]['a']) + 1))
    data = {'seasons': {LG: {
        SN: consistent_block(MATCHES),      # pendiente
        SN2: full,                           # ya backfilleado ⇒ excluido
        CURRENT_SEASON: consistent_block(MATCHES),  # CURRENT ⇒ excluido
    }}}
    assert select_seasons(data, None, None) == [(LG, SN)]
    assert select_seasons(data, LG, SN) == [(LG, SN)]
    assert select_seasons(data, LG, SN2) == []  # rk completo
    assert select_seasons(data, 'pl', None) == []  # otra liga


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    tests = [
        test_a_reconstruccion_ok,
        test_b_a_alterado_skipped_byte_identico,
        test_c_rank_preexistente_incongruente_skipped,
        test_d_campos_existentes_byte_identicos,
        test_e_m_alterado_skipped,
        test_f_diferencial_contra_process_season,
        test_g_run_verificacion_skip_no_escribe,
        test_h_run_descarga_skip_escribe_verificadas,
        test_i_run_check_byte_identico,
        test_j_run_write_luego_idempotente,
        test_k_select_seasons_excluye_current_y_filtra,
    ]
    for t in tests:
        t()
    print(f'OK: {len(tests)} tests de backfill_rk (ADR-005·R·2) pasan')
