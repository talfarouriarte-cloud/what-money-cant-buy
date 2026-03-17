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
    # Serie A
    "FC Internazionale Milano": "Inter Milan", "Inter": "Inter Milan",
    "AC Milan": "AC Milan", "Milan": "AC Milan",
    "AS Roma": "Roma", "SSC Napoli": "Napoli",
    "SS Lazio": "Lazio", "Lazio": "Lazio",
    "Juventus FC": "Juventus", "ACF Fiorentina": "Fiorentina",
    "Atalanta BC": "Atalanta", "Torino FC": "Torino",
    "US Sassuolo": "Sassuolo", "Sassuolo": "Sassuolo",
    "Genoa CFC": "Genoa", "US Salernitana": "Salernitana",
    "US Lecce": "Lecce", "Empoli FC": "Empoli",
    "Udinese Calcio": "Udinese", "Bologna FC": "Bologna", "Bologna FC 1909": "Bologna",
    "Cagliari Calcio": "Cagliari", "Hellas Verona FC": "Hellas Verona", "Verona": "Hellas Verona",
    "Parma Calcio 1913": "Parma", "Parma": "Parma",
    "Venezia FC": "Venezia", "Como 1907": "Como",
    "Spezia Calcio": "Spezia", "Benevento Calcio": "Benevento",
    "AC Monza": "Monza", "US Cremonese": "Cremonese",
    "US Sampdoria": "Sampdoria", "AC ChievoVerona": "Chievo Verona",
    "Frosinone Calcio": "Frosinone", "FC Crotone": "Crotone",
    "Brescia Calcio": "Brescia", "SPAL": "SPAL",
    "Pisa SC": "Pisa", "Pescara": "Pescara",
    "Palermo FC": "Palermo", "Catania": "Catania",
    "Livorno": "Livorno", "Cesena": "Cesena", "Carpi FC": "Carpi",
    # Bundesliga
    "FC Bayern München": "Bayern Munich", "Bayern Munich": "Bayern Munich",
    "Borussia Dortmund": "Borussia Dortmund", "BV Borussia 09 Dortmund": "Borussia Dortmund",
    "RB Leipzig": "Leipzig", "Bayer 04 Leverkusen": "Bayer Leverkusen",
    "VfL Wolfsburg": "Wolfsburg", "VfB Stuttgart": "Stuttgart",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "Borussia Mönchengladbach": "Monchengladbach", "Mönchengladbach": "Monchengladbach",
    "SC Freiburg": "Freiburg", "TSG 1899 Hoffenheim": "Hoffenheim",
    "1. FC Union Berlin": "Union Berlin", "Union Berlin": "Union Berlin",
    "SV Werder Bremen": "Werder Bremen", "Werder Bremen": "Werder Bremen",
    "1. FSV Mainz 05": "Mainz", "Mainz 05": "Mainz",
    "FC Augsburg": "Augsburg",
    "1. FC Köln": "Koln", "FC Köln": "Koln",
    "1. FC Heidenheim 1846": "Heidenheim", "Heidenheim": "Heidenheim",
    "FC St. Pauli": "St Pauli", "St. Pauli": "St Pauli",
    "Holstein Kiel": "Holstein Kiel",
    "VfL Bochum 1848": "Bochum", "Bochum": "Bochum",
    "Hertha BSC": "Hertha Berlin", "Hertha Berlin": "Hertha Berlin",
    "FC Schalke 04": "Schalke 04", "Schalke 04": "Schalke 04",
    "Hannover 96": "Hannover", "Hamburger SV": "Hamburg",
    "SV Darmstadt 98": "Darmstadt", "Fortuna Düsseldorf": "Dusseldorf",
    "SC Paderborn 07": "Paderborn", "SpVgg Greuther Fürth": "Furth",
    "DSC Arminia Bielefeld": "Arminia Bielefeld",
    "1. FC Nürnberg": "Nurnberg", "Nürnberg": "Nurnberg",
    "FC Ingolstadt 04": "Ingolstadt",
    "Eintracht Braunschweig": "Braunschweiger",
    # Ligue 1
    "Paris Saint-Germain": "PSG", "Paris Saint-Germain FC": "PSG",
    "Olympique de Marseille": "Marseille", "Olympique Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon", "Olympique Lyon": "Lyon",
    "AS Monaco FC": "Monaco", "AS Monaco": "Monaco",
    "OGC Nice": "Nice",
    "Stade Rennais FC": "Rennes", "Stade Rennais FC 1901": "Rennes",
    "LOSC Lille": "Lille", "LOSC": "Lille",
    "RC Lens": "Lens", "Racing Club de Lens": "Lens",
    "FC Nantes": "Nantes", "Stade Brestois 29": "Brest",
    "RC Strasbourg Alsace": "Strasbourg", "Strasbourg": "Strasbourg",
    "Montpellier HSC": "Montpellier", "Montpellier Hérault SC": "Montpellier",
    "Toulouse FC": "Toulouse", "Angers SCO": "Angers",
    "Stade de Reims": "Reims", "Le Havre AC": "Le Havre",
    "FC Lorient": "Lorient", "Clermont Foot 63": "Clermont",
    "AJ Auxerre": "Auxerre", "FC Metz": "Metz",
    "AS Saint-Étienne": "St-Etienne", "Saint-Étienne": "St-Etienne",
    "Girondins de Bordeaux": "Bordeaux", "FC Girondins de Bordeaux": "Bordeaux",
    "Dijon FCO": "Dijon", "Nîmes Olympique": "Nimes",
    "Amiens SC": "Amiens", "SM Caen": "Caen",
    "En Avant de Guingamp": "Guingamp", "EA Guingamp": "Guingamp",
    "ES Troyes AC": "Troyes", "SC Bastia": "Bastia",
    "Évian Thonon Gaillard FC": "Evian",
    "FC Sochaux-Montbéliard": "Sochaux",
    "Valenciennes FC": "Valenciennes", "AS Nancy": "Nancy",
    "Paris FC": "Paris FC",
    "GFC Ajaccio": "Gazelec Ajaccio", "AC Ajaccio": "Ajaccio",
    # Eredivisie
    "AFC Ajax": "Ajax", "Ajax": "Ajax",
    "PSV": "PSV", "PSV Eindhoven": "PSV",
    "Feyenoord Rotterdam": "Feyenoord", "Feyenoord": "Feyenoord",
    "AZ": "AZ Alkmaar", "AZ Alkmaar": "AZ Alkmaar",
    "FC Utrecht": "Utrecht", "FC Twente": "Twente",
    "SC Heerenveen": "Heerenveen", "FC Groningen": "Groningen",
    "NEC Nijmegen": "NEC Nijmegen", "N.E.C.": "NEC Nijmegen",
    "Sparta Rotterdam": "Sparta Rotterdam",
    "Fortuna Sittard": "Fortuna Sittard",
    "Go Ahead Eagles": "Go Ahead Eagles",
    "Heracles Almelo": "Heracles",
    "RKC Waalwijk": "RKC Waalwijk",
    "PEC Zwolle": "PEC Zwolle",
    "FC Volendam": "Volendam",
    "Willem II": "Willem II",
    "NAC Breda": "NAC Breda",
    "ADO Den Haag": "ADO Den Haag",
    "FC Emmen": "Emmen",
    "Excelsior": "Excelsior",
    "Vitesse": "Vitesse",
    "SC Cambuur": "Cambuur Leeuwarden",
    "VVV-Venlo": "VVV-Venlo",
    "Roda JC Kerkrade": "Roda JC", "Roda JC": "Roda JC",
    "De Graafschap": "De Graafschap",
    "FC Dordrecht": "Dordrecht",
    "Almere City FC": "Almere",
    "AC Pisa 1909": "Pisa",
    "Lille OSC": "Lille",
    "FC Twente '65": "Twente", "FC Twente": "Twente",
    "NEC": "NEC Nijmegen",
    "SBV Excelsior": "Excelsior",
    "Telstar 1963": "Telstar",

    "SBV Telstar": "Telstar",
}

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
