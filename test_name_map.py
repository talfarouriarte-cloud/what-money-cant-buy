#!/usr/bin/env python3
"""
Tests de name_map.json — fuente única API→interno + capa de display (ADR-009).

Ejecutable standalone con exit code (asserts, sin prints de resultado):
    python3 test_name_map.py

Cubre:
  - El JSON parsea y tiene las dos secciones (api_to_internal, display).
  - Contiene las 11 claves API nuevas (ascendidos 26/27) con valores exactos.
  - Contiene las 24 entradas de display de la tabla de ADR-009 con valores
    exactos.
  - Toda clave de `display` existe como nombre de equipo en data.json o como
    valor de `api_to_internal` (el interno es la clave inmutable de datos).

No modifica ningún fichero; solo lee name_map.json y data.json.
"""
import json
import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def load_json(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


# --- (1) parsea y tiene las dos secciones -----------------------------------
nm = load_json("name_map.json")
assert isinstance(nm, dict), "name_map.json debe ser un objeto"
assert "api_to_internal" in nm, "falta sección api_to_internal"
assert "display" in nm, "falta sección display"
a2i = nm["api_to_internal"]
display = nm["display"]
assert isinstance(a2i, dict) and a2i, "api_to_internal debe ser un dict no vacío"
assert isinstance(display, dict) and display, "display debe ser un dict no vacío"


# --- (2) las 11 claves API nuevas con valores exactos -----------------------
NEW_API = {
    "Málaga CF": "Malaga",
    "RC Deportivo La Coruña": "La Coruna",
    "Real Racing Club de Santander": "Santander",
    "Coventry City FC": "Coventry",
    "Hull City AFC": "Hull",
    "Ipswich Town FC": "Ipswich",
    "SV 07 Elversberg": "Elversberg",
    "ES Troyes AC": "Troyes",
    "Le Mans FC": "Le Mans",
    "SC Cambuur-Leeuwarden": "Cambuur Leeuwarden",
    "Willem II Tilburg": "Willem II",
}
for k, v in NEW_API.items():
    assert k in a2i, "falta clave API nueva: %r" % k
    assert a2i[k] == v, "valor incorrecto para %r: %r != %r" % (k, a2i[k], v)


# --- (3) las 24 entradas de display con valores exactos ---------------------
DISPLAY = {
    "Alaves": "Alavés",
    "Almeria": "Almería",
    "At Madrid": "Atlético Madrid",
    "Ath Bilbao": "Athletic Club",
    "Cadiz": "Cádiz",
    "Cordoba": "Córdoba",
    "Espanol": "Espanyol",
    "La Coruna": "Deportivo",
    "Leganes": "Leganés",
    "Malaga": "Málaga",
    "Sociedad": "Real Sociedad",
    "Sp Gijon": "Sporting Gijón",
    "Vallecano": "Rayo Vallecano",
    "Santander": "Racing",
    "Koln": "Köln",
    "Monchengladbach": "M'gladbach",
    "Dusseldorf": "Düsseldorf",
    "Furth": "Greuther Fürth",
    "Nurnberg": "Nürnberg",
    "Braunschweiger": "Braunschweig",
    "St Pauli": "St. Pauli",
    "St-Etienne": "Saint-Étienne",
    "Nimes": "Nîmes",
    "Nottm Forest": "Nottingham Forest",
}
assert len(display) == len(DISPLAY), (
    "display debe tener exactamente %d entradas, tiene %d" % (len(DISPLAY), len(display))
)
for k, v in DISPLAY.items():
    assert k in display, "falta entrada de display: %r" % k
    assert display[k] == v, "display incorrecto para %r: %r != %r" % (k, display[k], v)


# --- (4) toda clave de display resuelve a interno de datos -------------------
data = load_json("data.json")
team_names = set()
for lg, seasons in data["seasons"].items():
    for sn, teams in seasons.items():
        if isinstance(teams, dict):
            team_names.update(teams.keys())
internal_values = set(a2i.values())
resolvable = team_names | internal_values
for k in display:
    assert k in resolvable, (
        "clave de display %r no existe como equipo en data.json ni como valor "
        "de api_to_internal" % k
    )
