#!/usr/bin/env python3
"""Test del reloj único de temporada (ADR-007, ADR-008).

Verifica las funciones puras extraídas en update.py:
- derive_season(now): umbral (month, day) >= (7, 15) => temporada nueva (ADR-008).
- api_season_year(season_str): año de inicio para el parámetro ?season (ADR-007).
- season_key_from_start(start_date): clave de temporada del payload (ADR-007).

Run: python3 test_season_clock.py  (exit 0 si todo pasa)
"""
from datetime import datetime
from update import derive_season, api_season_year, season_key_from_start

# ADR-008 — umbral (month, day) >= (7, 15) inclusive
assert derive_season(datetime(2026, 7, 14)) == '25/26', derive_season(datetime(2026, 7, 14))
assert derive_season(datetime(2026, 7, 15)) == '26/27', derive_season(datetime(2026, 7, 15))
assert derive_season(datetime(2026, 8, 1)) == '26/27', derive_season(datetime(2026, 8, 1))
assert derive_season(datetime(2026, 1, 15)) == '25/26', derive_season(datetime(2026, 1, 15))

# ADR-007 — año de la API a partir de la clave de temporada
assert api_season_year('25/26') == 2025, api_season_year('25/26')
assert api_season_year('26/27') == 2026, api_season_year('26/27')

# ADR-007 — clave de temporada a partir de la fecha de inicio del calendario
assert season_key_from_start('2025-08-15') == '25/26', season_key_from_start('2025-08-15')
assert season_key_from_start('2026-08-14') == '26/27', season_key_from_start('2026-08-14')

print("OK: test_season_clock — all season-clock assertions passed")
