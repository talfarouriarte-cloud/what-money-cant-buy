#!/usr/bin/env python3
"""Test: el conjunto de necesidad de build_crests es data.json ∪ calendario
de la temporada actual (fixtures.json). Correctivo épica crests-needed.

Verifica que un equipo solo-histórico (en data.json) y uno solo-calendario
(un ascendido sin partidos jugados, en fixtures.json) aparezcan AMBOS en el
conjunto de necesidad. Sin red, con ficheros sintéticos mínimos en un tmpdir.
"""
import json, os, sys, tempfile
from datetime import datetime

import build_crests


def build_needed(data_dir, season):
    """Replica la construcción de `needed` de build_crests.main() sin red:
    data.json ∪ fixtures_needed(temporada actual)."""
    with open(os.path.join(data_dir, 'data.json')) as f:
        data = json.load(f)
    needed = set()
    for lg in data.get('seasons', {}):
        for sn in data.get('seasons', {}).get(lg, {}):
            for team in data['seasons'][lg][sn]:
                needed.add(team)
    needed |= build_crests.fixtures_needed(data_dir, season)
    return needed


def main():
    season = build_crests.derive_season(datetime.now())

    with tempfile.TemporaryDirectory() as d:
        # data.json: un equipo SOLO histórico (temporada pasada, no en calendario)
        data = {'seasons': {'ll': {'24/25': {'Solo Historico': {}}}}}
        with open(os.path.join(d, 'data.json'), 'w') as f:
            json.dump(data, f)

        # fixtures.json: temporada actual con un ascendido SOLO en calendario
        fixtures = {
            'll': {
                season: {
                    'calendar': [
                        {'gw': 1,
                         'matches': [['Solo Calendario', 'Otro Calendario']],
                         'played': [False], 'dates': [None]},
                    ]
                }
            }
        }
        with open(os.path.join(d, 'fixtures.json'), 'w') as f:
            json.dump(fixtures, f)

        needed = build_needed(d, season)

        assert 'Solo Historico' in needed, "equipo solo-histórico ausente"
        assert 'Solo Calendario' in needed, "ascendido solo-calendario ausente"
        assert 'Otro Calendario' in needed, "visitante solo-calendario ausente"
        assert needed == {'Solo Historico', 'Solo Calendario', 'Otro Calendario'}, \
            f"unión inesperada: {sorted(needed)}"

        # Temporada ausente en fixtures.json => solo data.json, sin fallo
        needed_no_season = build_needed(d, '99/00')
        assert needed_no_season == {'Solo Historico'}, \
            f"temporada ausente debe caer a solo data.json: {sorted(needed_no_season)}"

    # fixtures.json inexistente => set vacío, sin fallo
    with tempfile.TemporaryDirectory() as d2:
        assert build_crests.fixtures_needed(d2, season) == set(), \
            "fixtures.json inexistente debe dar set vacío"

    print("OK test_crests_needed: unión data.json ∪ calendario correcta")


if __name__ == '__main__':
    main()
    sys.exit(0)
