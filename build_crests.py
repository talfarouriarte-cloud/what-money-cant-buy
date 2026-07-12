#!/usr/bin/env python3
"""
Build crests.json — maps internal team names to crest URLs from football-data.org.

Queries multiple competitions to cover current + recently relegated teams:
  PD  = La Liga
  SD  = Segunda División
  PL  = Premier League
  ELC = Championship

Usage:
  FOOTBALL_DATA_API_KEY=xxx python build_crests.py

Output: crests.json  {"Barcelona": "https://crests.football-data.org/81.svg", ...}
"""
import json, os, sys, time, unicodedata

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
NAME_MAP_FILE = os.path.join(DATA_DIR, 'name_map.json')

# API name → internal name. Fuente única en name_map.json (sección
# api_to_internal), compartida con update.py (ADR-009). Zona de rigor
# spec §3.3: no editar este mapa aquí, editar name_map.json.
with open(NAME_MAP_FILE, encoding='utf-8') as _nm_f:
    API_NAME_MAP = json.load(_nm_f)['api_to_internal']

# Manual crest URLs for teams not found in current competitions
# These are historical teams relegated beyond the leagues we query
# IDs from football-data.org are stable
MANUAL_CRESTS = {
    # La Liga / Segunda
    "Almeria": "https://crests.football-data.org/267.svg",
    "Cadiz": "https://crests.football-data.org/264.svg",
    "Cardiff": "https://crests.football-data.org/715.svg",
    "Cordoba": "https://crests.football-data.org/8304.svg",
    "Eibar": "https://crests.football-data.org/278.svg",
    "Granada": "https://crests.football-data.org/281.svg",
    "Huddersfield": "https://crests.football-data.org/394.svg",
    "Huesca": "https://crests.football-data.org/299.svg",
    "La Coruna": "https://crests.football-data.org/560.svg",
    "Las Palmas": "https://crests.football-data.org/275.svg",
    "Leganes": "https://crests.football-data.org/745.svg",
    "Luton": "https://crests.football-data.org/1044.svg",
    "Malaga": "https://crests.football-data.org/84.svg",
    "Sp Gijon": "https://crests.football-data.org/296.svg",
    "Valladolid": "https://crests.football-data.org/250.svg",
    # Serie A historical
    "Benevento": "https://crests.football-data.org/8554.svg",
    "Brescia": "https://crests.football-data.org/104.svg",
    "Carpi": "https://crests.football-data.org/8529.svg",
    "Catania": "https://crests.football-data.org/110.svg",
    "Cesena": "https://crests.football-data.org/8543.svg",
    "Chievo Verona": "https://crests.football-data.org/8530.svg",
    "Crotone": "https://crests.football-data.org/8535.svg",
    "Empoli": "https://crests.football-data.org/8534.svg",
    "Frosinone": "https://crests.football-data.org/8536.svg",
    "Livorno": "https://crests.football-data.org/8540.svg",
    "Monza": "https://crests.football-data.org/5911.svg",
    "Palermo": "https://crests.football-data.org/116.svg",
    "Pescara": "https://crests.football-data.org/8545.svg",
    "SPAL": "https://crests.football-data.org/8548.svg",
    "Salernitana": "https://crests.football-data.org/8549.svg",
    "Sampdoria": "https://crests.football-data.org/8547.svg",
    "Spezia": "https://crests.football-data.org/8550.svg",
    "Venezia": "https://crests.football-data.org/8551.svg",
    # Bundesliga historical
    "Arminia Bielefeld": "https://crests.football-data.org/38.svg",
    "Bochum": "https://crests.football-data.org/36.svg",
    "Braunschweiger": "https://crests.football-data.org/2.svg",
    "Darmstadt": "https://crests.football-data.org/55.svg",
    "Dusseldorf": "https://crests.football-data.org/56.svg",
    "Furth": "https://crests.football-data.org/58.svg",
    "Hamburg": "https://crests.football-data.org/7.svg",
    "Hannover": "https://crests.football-data.org/8.svg",
    "Hertha Berlin": "https://crests.football-data.org/9.svg",
    "Holstein Kiel": "https://crests.football-data.org/720.svg",
    "Ingolstadt": "https://crests.football-data.org/65.svg",
    "Nurnberg": "https://crests.football-data.org/14.svg",
    "Paderborn": "https://crests.football-data.org/16.svg",
    "Schalke 04": "https://crests.football-data.org/6.svg",
    # Ligue 1 historical
    "Ajaccio": "https://crests.football-data.org/536.svg",
    "Amiens": "https://crests.football-data.org/546.svg",
    "Bastia": "https://crests.football-data.org/547.svg",
    "Bordeaux": "https://crests.football-data.org/526.svg",
    "Caen": "https://crests.football-data.org/514.svg",
    "Clermont": "https://crests.football-data.org/541.svg",
    "Dijon": "https://crests.football-data.org/548.svg",
    "Evian": "https://crests.football-data.org/545.svg",
    "Gazelec Ajaccio": "https://crests.football-data.org/551.svg",
    "Guingamp": "https://crests.football-data.org/549.svg",
    "Montpellier": "https://crests.football-data.org/518.svg",
    "Nancy": "https://crests.football-data.org/544.svg",
    "Nimes": "https://crests.football-data.org/553.svg",
    "Reims": "https://crests.football-data.org/547.svg",
    "Sochaux": "https://crests.football-data.org/554.svg",
    "St-Etienne": "https://crests.football-data.org/527.svg",
    "Troyes": "https://crests.football-data.org/555.svg",
    "Valenciennes": "https://crests.football-data.org/556.svg",
    # Eredivisie historical
    "ADO Den Haag": "https://crests.football-data.org/682.svg",
    "Almere": "https://crests.football-data.org/8264.svg",
    "Cambuur Leeuwarden": "https://crests.football-data.org/690.svg",
    "De Graafschap": "https://crests.football-data.org/678.svg",
    "Dordrecht": "https://crests.football-data.org/683.svg",
    "Emmen": "https://crests.football-data.org/684.svg",
    "RKC Waalwijk": "https://crests.football-data.org/685.svg",
    "Roda JC": "https://crests.football-data.org/671.svg",
    "VVV-Venlo": "https://crests.football-data.org/679.svg",
    "Vitesse": "https://crests.football-data.org/676.svg",
    "Willem II": "https://crests.football-data.org/677.svg",
}

COMPETITIONS = {
    'PD':  'La Liga',
    'SD':  'Segunda División',
    'PL':  'Premier League',
    'ELC': 'Championship',
    'SA':  'Serie A',
    'SB':  'Serie B',
    'BL1': 'Bundesliga',
    'BL2': '2. Bundesliga',
    'FL1': 'Ligue 1',
    'FL2': 'Ligue 2',
    'DED': 'Eredivisie',
    'KNV': 'Eerste Divisie',
}


def api_name_to_internal(name):
    """Convert football-data.org team name to our internal name."""
    if name in API_NAME_MAP:
        return API_NAME_MAP[name]
    for suffix in [' FC', ' CF', ' UD', ' CD', ' AFC']:
        stripped = name.replace(suffix, '').strip()
        if stripped in API_NAME_MAP:
            return API_NAME_MAP[stripped]
    # Strip accents
    normalized = unicodedata.normalize('NFD', name)
    ascii_name = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    if ascii_name in API_NAME_MAP:
        return API_NAME_MAP[ascii_name]
    return name


def fetch_teams(api_key, comp_code):
    """Fetch teams for a competition. Returns list of {name, crest} dicts."""
    url = f'https://api.football-data.org/v4/competitions/{comp_code}/teams'
    headers = {'X-Auth-Token': api_key}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 403:
        print(f"  {comp_code}: 403 Forbidden (not in your plan)")
        return []
    if r.status_code != 200:
        print(f"  {comp_code}: HTTP {r.status_code}")
        return []
    data = r.json()
    teams = data.get('teams', [])
    print(f"  {comp_code} ({COMPETITIONS.get(comp_code, '?')}): {len(teams)} teams")
    return teams


def main():
    api_key = os.environ.get('FOOTBALL_DATA_API_KEY', '')
    if not api_key:
        print("Set FOOTBALL_DATA_API_KEY environment variable")
        sys.exit(1)

    # Load data.json to know which team names we need
    data_file = os.path.join(DATA_DIR, 'data.json')
    with open(data_file) as f:
        data = json.load(f)
    
    needed = set()
    for lg in data.get('seasons', {}):
        for sn in data.get('seasons', {}).get(lg, {}):
            for team in data['seasons'][lg][sn]:
                needed.add(team)
    print(f"Need crests for {len(needed)} unique team names")

    crests = {}
    unmapped = []

    for comp_code in COMPETITIONS:
        teams = fetch_teams(api_key, comp_code)
        for t in teams:
            # Try name, shortName, and tla
            for field in ['name', 'shortName', 'tla']:
                raw = t.get(field, '')
                internal = api_name_to_internal(raw)
                if internal in needed and internal not in crests:
                    crests[internal] = t.get('crest', '')
                    break
            # Also try the raw name directly
            if t.get('name', '') in needed and t['name'] not in crests:
                crests[t['name']] = t.get('crest', '')
        
        time.sleep(6.5)  # respect 10 req/min rate limit

    # Fill missing with manual crests
    for name, url in MANUAL_CRESTS.items():
        if name in needed and name not in crests:
            crests[name] = url

    # Try API search for any still missing (free tier allows /v4/teams?name=)
    still_missing = needed - set(crests.keys())
    if still_missing:
        print(f"\n{len(still_missing)} teams not found in competitions (historical/relegated):")
        for name in sorted(still_missing):
            print(f"  - {name}")
        print("Add these to MANUAL_CRESTS if crest URLs are known.")

    # Report
    found = set(crests.keys())
    missing = needed - found
    print(f"\nFound crests: {len(found)}/{len(needed)}")
    if missing:
        print(f"Missing ({len(missing)}): {sorted(missing)}")
    
    # Write
    out_file = os.path.join(DATA_DIR, 'crests.json')
    with open(out_file, 'w') as f:
        json.dump(crests, f, indent=2, ensure_ascii=False)
    print(f"Written to {out_file}")


if __name__ == '__main__':
    main()
