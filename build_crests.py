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

# Same mapping as update.py — API name → internal name
API_NAME_MAP = {
    # La Liga
    "Alavés": "Alaves", "Atlético de Madrid": "At Madrid", "Atlético Madrid": "At Madrid",
    "Atl. Madrid": "At Madrid", "Athletic Club": "Ath Bilbao", "Athletic": "Ath Bilbao",
    "Club Atlético de Madrid": "At Madrid", "FC Barcelona": "Barcelona",
    "Real Betis": "Betis", "Celta de Vigo": "Celta", "Celta Vigo": "Celta",
    "Elche CF": "Elche", "RCD Espanyol": "Espanol", "Espanyol": "Espanol",
    "Getafe CF": "Getafe", "Girona FC": "Girona", "Levante UD": "Levante",
    "RCD Mallorca": "Mallorca", "CA Osasuna": "Osasuna", "Real Oviedo": "Oviedo",
    "Real Sociedad": "Sociedad", "Rayo Vallecano": "Vallecano", "Villarreal CF": "Villarreal",
    "Deportivo Alavés": "Alaves", "RC Celta de Vigo": "Celta",
    "RCD Espanyol de Barcelona": "Espanol",
    "Real Madrid CF": "Real Madrid", "Sevilla FC": "Sevilla", "Valencia CF": "Valencia",
    "UD Almería": "Almeria", "Almería": "Almeria",
    "Cádiz CF": "Cadiz", "Cádiz": "Cadiz",
    "Granada CF": "Granada", "Granada": "Granada",
    "SD Eibar": "Eibar", "Eibar": "Eibar",
    "SD Huesca": "Huesca", "Huesca": "Huesca",
    "Real Valladolid": "Valladolid", "Valladolid": "Valladolid",
    "Real Zaragoza": "Zaragoza",
    "CD Leganés": "Leganes", "Leganés": "Leganes",
    "Deportivo de La Coruña": "La Coruna", "Deportivo La Coruña": "La Coruna",
    "UD Las Palmas": "Las Palmas", "Las Palmas": "Las Palmas",
    "Sporting Gijón": "Sp Gijon", "Sporting de Gijón": "Sp Gijon",
    "Málaga CF": "Malaga", "Málaga": "Malaga",
    # Premier League
    "Manchester City": "Man City", "Manchester City FC": "Man City",
    "Manchester United": "Man United", "Manchester United FC": "Man United",
    "Nottingham Forest": "Nottm Forest", "Nottingham Forest FC": "Nottm Forest",
    "Newcastle United": "Newcastle", "Newcastle United FC": "Newcastle",
    "Wolverhampton Wanderers": "Wolves", "Wolverhampton Wanderers FC": "Wolves",
    "AFC Sunderland": "Sunderland", "Sunderland AFC": "Sunderland",
    "West Ham United": "West Ham", "West Ham United FC": "West Ham",
    "Aston Villa": "Aston Villa", "Aston Villa FC": "Aston Villa",
    "Crystal Palace": "Crystal Palace", "Crystal Palace FC": "Crystal Palace",
    "AFC Bournemouth": "Bournemouth",
    "Brighton & Hove Albion": "Brighton", "Brighton & Hove Albion FC": "Brighton",
    "Leeds United": "Leeds", "Leeds United FC": "Leeds",
    "Burnley FC": "Burnley", "Burnley": "Burnley",
    "Brentford FC": "Brentford", "Brentford": "Brentford",
    "Arsenal FC": "Arsenal",
    "Chelsea FC": "Chelsea",
    "Everton FC": "Everton",
    "Fulham FC": "Fulham",
    "Liverpool FC": "Liverpool",
    "Tottenham Hotspur": "Tottenham", "Tottenham Hotspur FC": "Tottenham",
    "Leicester City": "Leicester", "Leicester City FC": "Leicester",
    "Southampton FC": "Southampton", "Southampton": "Southampton",
    "Watford FC": "Watford", "Watford": "Watford",
    "West Bromwich Albion": "West Brom", "West Bromwich Albion FC": "West Brom",
    "Norwich City": "Norwich", "Norwich City FC": "Norwich",
    "Sheffield United": "Sheffield United", "Sheffield United FC": "Sheffield United",
    "Luton Town": "Luton", "Luton Town FC": "Luton",
    "Ipswich Town": "Ipswich", "Ipswich Town FC": "Ipswich",
    "Swansea City": "Swansea", "Swansea City AFC": "Swansea",
    "Stoke City": "Stoke", "Stoke City FC": "Stoke",
    "Hull City": "Hull", "Hull City AFC": "Hull",
    "Cardiff City": "Cardiff", "Cardiff City FC": "Cardiff",
    "Huddersfield Town": "Huddersfield", "Huddersfield Town AFC": "Huddersfield",
    "Middlesbrough FC": "Middlesbrough",
}

COMPETITIONS = {
    'PD':  'La Liga',
    'SD':  'Segunda División',
    'PL':  'Premier League',
    'ELC': 'Championship',
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
    for lg in ['ll', 'pl']:
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
