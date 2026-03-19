#!/usr/bin/env python3
"""
Daily data update for 'What money can't buy'
Downloads latest results, recomputes expected points, re-runs MC simulation.

Reads fixture calendar from fixtures.json (built by setup_season.py).
Optionally updates fixture calendar from football-data.org API (requires FOOTBALL_DATA_API_KEY env var).
Produces updated data.json with fresh bands anchored at latest results.

Usage: python update.py
       FOOTBALL_DATA_API_KEY=xxx python update.py  (to update fixtures from API)
Requirements: pip install pandas numpy scipy requests
"""
import pandas as pd
import numpy as np
from scipy.special import expit
import json, os, requests, sys
from datetime import datetime

PARAMS = {
    'll': {'beta': 0.4719, 'theta1': -1.0404, 'theta2': 0.2081},
    'pl': {'beta': 0.676,  'theta1': -0.8358, 'theta2': 0.2422},
    'sa': {'beta': 0.5974, 'theta1': -0.8601, 'theta2': 0.3391},
    'bl': {'beta': 0.4269, 'theta1': -0.8439, 'theta2': 0.2673},
    'l1': {'beta': 0.4237, 'theta1': -0.8941, 'theta2': 0.2411},
    'ed': {'beta': 0.61,   'theta1': -0.9014, 'theta2': 0.2038},
}
URLS = {
    'll': 'https://www.football-data.co.uk/mmz4281/2526/SP1.csv',
    'pl': 'https://www.football-data.co.uk/mmz4281/2526/E0.csv',
    'sa': 'https://www.football-data.co.uk/mmz4281/2526/I1.csv',
    'bl': 'https://www.football-data.co.uk/mmz4281/2526/D1.csv',
    'l1': 'https://www.football-data.co.uk/mmz4281/2526/F1.csv',
    'ed': 'https://www.football-data.co.uk/mmz4281/2526/N1.csv',
}
NAME_MAP = {
    "Nott'm Forest": "Nottm Forest", "Ath Madrid": "At Madrid",
    # Serie A
    "Inter": "Inter Milan", "Milan": "AC Milan", "Verona": "Hellas Verona",
    "Chievo": "Chievo Verona", "Spal": "SPAL",
    # Bundesliga
    "Dortmund": "Borussia Dortmund", "Ein Frankfurt": "Eintracht Frankfurt",
    "FC Koln": "Koln", "M'gladbach": "Monchengladbach",
    "Leverkusen": "Bayer Leverkusen", "RB Leipzig": "Leipzig",
    "Fortuna Dusseldorf": "Dusseldorf", "Greuther Furth": "Furth",
    "Hertha": "Hertha Berlin", "Bielefeld": "Arminia Bielefeld",
    "Braunschweig": "Braunschweiger",
    # Ligue 1
    "Paris SG": "PSG", "St Etienne": "St-Etienne",
    "Evian Thonon Gaillard": "Evian", "Ajaccio GFCO": "Gazelec Ajaccio",
    # Eredivisie
    "PSV Eindhoven": "PSV", "Nijmegen": "NEC Nijmegen",
    "For Sittard": "Fortuna Sittard", "Waalwijk": "RKC Waalwijk",
    "Zwolle": "PEC Zwolle", "Almere City": "Almere",
    "Den Haag": "ADO Den Haag", "Ado Den Haag": "ADO Den Haag",
    "Venlo": "VVV-Venlo", "VVV Venlo": "VVV-Venlo",
    "Cambuur": "Cambuur Leeuwarden", "Roda": "Roda JC",
    "Graafschap": "De Graafschap", "FC Emmen": "Emmen",
}
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(DATA_DIR, 'data.json')
FIXTURES_FILE = os.path.join(DATA_DIR, 'fixtures.json')

# football-data.org API → our internal name mapping
# API uses 'shortName'; most match directly, these are the exceptions
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
    # Premier League
    "Manchester City": "Man City", "Man City": "Man City",
    "Manchester United": "Man United", "Man United": "Man United",
    "Nottm Forest": "Nottm Forest", "Nott'm Forest": "Nottm Forest",
    "Nottingham Forest": "Nottm Forest", "Nottingham Forest FC": "Nottm Forest",
    "Newcastle United": "Newcastle", "Newcastle": "Newcastle",
    "Wolverhampton": "Wolves", "Wolves": "Wolves",
    "Wolverhampton Wanderers": "Wolves", "Wolverhampton Wanderers FC": "Wolves",
    "AFC Sunderland": "Sunderland", "Sunderland AFC": "Sunderland",
    "West Ham United": "West Ham", "West Ham": "West Ham",
    "Aston Villa": "Aston Villa", "Crystal Palace": "Crystal Palace",
    "AFC Bournemouth": "Bournemouth",
    "Brighton & Hove Albion": "Brighton", "Brighton Hove": "Brighton",
    "Leeds United": "Leeds", "Leeds": "Leeds",
    "Burnley FC": "Burnley", "Burnley": "Burnley",
    "Brentford FC": "Brentford", "Brentford": "Brentford",
    "Arsenal FC": "Arsenal", "Chelsea FC": "Chelsea",
    "Everton FC": "Everton", "Fulham FC": "Fulham",
    "Liverpool FC": "Liverpool",
    "Tottenham Hotspur": "Tottenham", "Tottenham Hotspur FC": "Tottenham",
    # Serie A (football-data.org API names)
    "FC Internazionale Milano": "Inter Milan", "Inter Milano": "Inter Milan",
    "AC Milan": "AC Milan", "AS Roma": "Roma", "SSC Napoli": "Napoli",
    "SS Lazio": "Lazio", "Juventus FC": "Juventus",
    "ACF Fiorentina": "Fiorentina", "Atalanta BC": "Atalanta",
    "Torino FC": "Torino", "US Sassuolo Calcio": "Sassuolo",
    "Genoa CFC": "Genoa", "US Salernitana 1919": "Salernitana",
    "US Lecce": "Lecce", "Empoli FC": "Empoli",
    "Udinese Calcio": "Udinese", "Bologna FC 1909": "Bologna",
    "Cagliari Calcio": "Cagliari", "Hellas Verona FC": "Hellas Verona",
    "Parma Calcio 1913": "Parma", "Venezia FC": "Venezia",
    "Como 1907": "Como", "Spezia Calcio": "Spezia",
    "Benevento Calcio": "Benevento", "AC Monza": "Monza",
    "US Cremonese": "Cremonese", "US Sampdoria": "Sampdoria",
    "Frosinone Calcio": "Frosinone", "FC Crotone": "Crotone",
    "Brescia Calcio": "Brescia", "Pisa SC": "Pisa",
    # Bundesliga
    "FC Bayern München": "Bayern Munich",
    "BV Borussia 09 Dortmund": "Borussia Dortmund",
    "RB Leipzig": "Leipzig", "Bayer 04 Leverkusen": "Bayer Leverkusen",
    "VfL Wolfsburg": "Wolfsburg", "VfB Stuttgart": "Stuttgart",
    "Borussia Mönchengladbach": "Monchengladbach",
    "SC Freiburg": "Freiburg", "TSG 1899 Hoffenheim": "Hoffenheim",
    "1. FC Union Berlin": "Union Berlin",
    "SV Werder Bremen": "Werder Bremen",
    "1. FSV Mainz 05": "Mainz", "FC Augsburg": "Augsburg",
    "1. FC Köln": "Koln", "1. FC Heidenheim 1846": "Heidenheim",
    "FC St. Pauli 1910": "St Pauli", "Holstein Kiel": "Holstein Kiel",
    "VfL Bochum 1848": "Bochum", "Hertha BSC": "Hertha Berlin",
    "FC Schalke 04": "Schalke 04", "Hannover 96": "Hannover",
    "Hamburger SV": "Hamburg", "SV Darmstadt 98": "Darmstadt",
    "Fortuna Düsseldorf": "Dusseldorf", "SC Paderborn 07": "Paderborn",
    "SpVgg Greuther Fürth": "Furth",
    "DSC Arminia Bielefeld": "Arminia Bielefeld",
    "1. FC Nürnberg": "Nurnberg", "FC Ingolstadt 04": "Ingolstadt",
    "Eintracht Braunschweig": "Braunschweiger",
    # Ligue 1
    "Paris Saint-Germain FC": "PSG",
    "Olympique de Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon", "AS Monaco FC": "Monaco",
    "OGC Nice": "Nice", "Stade Rennais FC 1901": "Rennes",
    "LOSC Lille": "Lille", "Racing Club de Lens": "Lens",
    "FC Nantes": "Nantes", "Stade Brestois 29": "Brest",
    "RC Strasbourg Alsace": "Strasbourg",
    "Montpellier Hérault SC": "Montpellier",
    "Toulouse FC": "Toulouse", "Angers SCO": "Angers",
    "Stade de Reims": "Reims", "Le Havre AC": "Le Havre",
    "FC Lorient": "Lorient", "Clermont Foot 63": "Clermont",
    "AJ Auxerre": "Auxerre", "FC Metz": "Metz",
    "AS Saint-Étienne": "St-Etienne",
    "FC Girondins de Bordeaux": "Bordeaux",
    "Paris FC": "Paris FC",
    # Eredivisie
    "AFC Ajax": "Ajax", "PSV": "PSV",
    "Feyenoord Rotterdam": "Feyenoord",
    "AZ": "AZ Alkmaar", "FC Utrecht": "Utrecht",
    "FC Twente": "Twente", "SC Heerenveen": "Heerenveen",
    "FC Groningen": "Groningen", "N.E.C.": "NEC Nijmegen",
    "Sparta Rotterdam": "Sparta Rotterdam",
    "Fortuna Sittard": "Fortuna Sittard",
    "Go Ahead Eagles": "Go Ahead Eagles",
    "Heracles Almelo": "Heracles", "RKC Waalwijk": "RKC Waalwijk",
    "PEC Zwolle": "PEC Zwolle", "FC Volendam": "Volendam",
    "Willem II": "Willem II", "NAC Breda": "NAC Breda",
    "ADO Den Haag": "ADO Den Haag", "FC Emmen": "Emmen",
    "Excelsior": "Excelsior", "Vitesse": "Vitesse",
    "SC Cambuur": "Cambuur Leeuwarden",
    "VVV-Venlo": "VVV-Venlo", "Almere City FC": "Almere",
    # API fixture names that differ from CSV/internal names
    "AC Pisa 1909": "Pisa",
    "Lille OSC": "Lille", "LOSC": "Lille",
    "FC Twente '65": "Twente",
    "NEC": "NEC Nijmegen",
    "SBV Excelsior": "Excelsior",
    "Telstar 1963": "Telstar",
}
COMPETITION_CODES = {'ll': 'PD', 'pl': 'PL', 'sa': 'SA', 'bl': 'BL1', 'l1': 'FL1', 'ed': 'DED'}

def api_name_to_internal(name):
    """Convert football-data.org team name to our internal name."""
    if name in API_NAME_MAP:
        return API_NAME_MAP[name]
    # Try without common suffixes
    for suffix in [' FC', ' CF', ' UD', ' CD']:
        stripped = name.replace(suffix, '').strip()
        if stripped in API_NAME_MAP:
            return API_NAME_MAP[stripped]
    # Strip accents as last resort
    import unicodedata
    normalized = unicodedata.normalize('NFD', name)
    ascii_name = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    if ascii_name in API_NAME_MAP:
        return API_NAME_MAP[ascii_name]
    return name

def fetch_fixtures_from_api():
    """Fetch full fixture calendar from football-data.org API for both leagues.
    Returns updated fixtures dict in same format as fixtures.json, or None on failure."""
    api_key = os.environ.get('FOOTBALL_DATA_API_KEY', '')
    if not api_key:
        print("  No FOOTBALL_DATA_API_KEY set, skipping API fixture update")
        return None
    
    headers = {'X-Auth-Token': api_key}
    base_url = 'https://api.football-data.org/v4/competitions'
    fixtures = {}
    
    for lg, code in COMPETITION_CODES.items():
        url = f'{base_url}/{code}/matches'
        print(f"  Fetching {lg} fixtures from football-data.org ({code})...")
        try:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
            matches = data.get('matches', [])
            print(f"    Got {len(matches)} matches")
            
            if not matches:
                continue
            
            # Build name mapping from this response
            name_cache = {}
            for m in matches:
                for side in ['homeTeam', 'awayTeam']:
                    api_short = m[side].get('shortName', m[side].get('name', ''))
                    api_full = m[side].get('name', '')
                    if api_short not in name_cache:
                        internal = api_name_to_internal(api_short)
                        if internal == api_short:
                            internal = api_name_to_internal(api_full)
                        name_cache[api_short] = fix_name(internal)
            
            # Log name mapping for debugging
            our_teams = set()
            for m in matches:
                h_short = m['homeTeam'].get('shortName', m['homeTeam'].get('name', ''))
                a_short = m['awayTeam'].get('shortName', m['awayTeam'].get('name', ''))
                our_teams.add(name_cache.get(h_short, h_short))
                our_teams.add(name_cache.get(a_short, a_short))
            print(f"    Teams: {sorted(our_teams)}")
            
            # Group by matchday, sort matches within each GW by date
            gw_matches = {}
            for m in matches:
                md = m.get('matchday', 0) or 0
                if md < 1:
                    continue
                if md not in gw_matches:
                    gw_matches[md] = []
                
                h_short = m['homeTeam'].get('shortName', m['homeTeam'].get('name', ''))
                a_short = m['awayTeam'].get('shortName', m['awayTeam'].get('name', ''))
                h_name = name_cache.get(h_short, h_short)
                a_name = name_cache.get(a_short, a_short)
                
                status = m.get('status', 'SCHEDULED')
                is_played = status == 'FINISHED'
                utc_date = m.get('utcDate', '')
                
                gw_matches[md].append({
                    'home': h_name, 'away': a_name,
                    'played': is_played, 'date': utc_date,
                    'status': status
                })
            
            # Build calendar
            max_gw = max(gw_matches.keys()) if gw_matches else 38
            calendar = []
            for gw in range(1, max_gw + 1):
                gw_list = gw_matches.get(gw, [])
                # Sort by date within each GW
                gw_list.sort(key=lambda x: x['date'] or '9999')
                match_pairs = [[m['home'], m['away']] for m in gw_list]
                played_flags = [m['played'] for m in gw_list]
                dates = [m['date'] for m in gw_list]
                calendar.append({
                    'gw': gw, 'matches': match_pairs,
                    'played': played_flags, 'dates': dates
                })
            
            n_played = sum(1 for gw in calendar for p in gw['played'] if p)
            n_total = sum(len(gw['matches']) for gw in calendar)
            print(f"    Calendar: {max_gw} matchdays, {n_total} fixtures, {n_played} played")
            
            if lg not in fixtures:
                fixtures[lg] = {}
            fixtures[lg]['25/26'] = {'calendar': calendar}
            
        except Exception as e:
            print(f"    API FAILED: {e}")
            continue
    
    return fixtures if fixtures else None

def fix_name(n):
    return NAME_MAP.get(n, n)

def download_current_season():
    results = {}
    for lg, url in URLS.items():
        print(f"  Downloading {lg}...")
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            path = os.path.join(DATA_DIR, f'current_{lg}.csv')
            with open(path, 'w') as f:
                f.write(r.text)
            results[lg] = path
            print(f"    OK ({len(r.text)} bytes)")
        except Exception as e:
            print(f"    FAILED: {e}")
            results[lg] = None
    return results

def process_season(filepath, wages, beta, t1, t2, fixtures_calendar=None, lg=None):
    df = pd.read_csv(filepath, encoding='utf-8', on_bad_lines='skip', low_memory=False)
    df = df[['HomeTeam','AwayTeam','FTR']].dropna()
    # Map CSV names to internal names
    df['HomeTeam'] = df['HomeTeam'].apply(fix_name)
    df['AwayTeam'] = df['AwayTeam'].apply(fix_name)
    
    # Build matchday lookup from fixture calendar: (home, away) -> official GW
    gw_lookup = {}
    date_lookup = {}
    if fixtures_calendar and lg:
        cal = fixtures_calendar.get(lg, {}).get('25/26', {}).get('calendar', [])
        for gw_data in cal:
            gw = gw_data.get('gw', 0)
            dates = gw_data.get('dates', [])
            for mi, pair in enumerate(gw_data['matches']):
                h_fix, a_fix = fix_name(pair[0]), fix_name(pair[1])
                gw_lookup[(h_fix, a_fix)] = gw
                if mi < len(dates) and dates[mi]:
                    date_lookup[(h_fix, a_fix)] = dates[mi][:10]
    
    td = {}
    for t in sorted(set(df['HomeTeam']) | set(df['AwayTeam'])):
        td[t] = {'pts':[],'exp':[],'m':[],'cp':0,'ce':0.0}
    for _, r in df.iterrows():
        h, a = r['HomeTeam'], r['AwayTeam']
        wh, wa = wages.get(h, wages.get(fix_name(h), 20)), wages.get(a, wages.get(fix_name(a), 20))
        x = np.log2(wa / wh)
        ph = 1 - expit(t2 + beta * x)
        pd_ = expit(t2 + beta * x) - expit(t1 + beta * x)
        pa = expit(t1 + beta * x)
        if r['FTR'] == 'H': hp, ap = 3, 0
        elif r['FTR'] == 'A': hp, ap = 0, 3
        else: hp, ap = 1, 1
        eh, ea = ph * 3 + pd_, pa * 3 + pd_
        official_gw = gw_lookup.get((fix_name(h), fix_name(a)), 0)
        mdate = date_lookup.get((fix_name(h), fix_name(a)), '')
        for team, pts, exp, opp, ih in [(h,hp,eh,a,1),(a,ap,ea,h,0)]:
            td[team]['cp'] += pts; td[team]['ce'] += exp
            td[team]['pts'].append(td[team]['cp'])
            td[team]['exp'].append(round(td[team]['ce'], 1))
            td[team]['m'].append([opp, ih, pts, round(exp, 2), official_gw, mdate])
    return {t: {'a':d['pts'],'e':d['exp'],'m':d['m'],'w':round(wages.get(t, wages.get(fix_name(t), 0)))} for t,d in td.items()}


def recalculate_budget_bands(fixtures_cal, wages, beta, t1, t2, lg, season_data, remaining_fixtures, n_sims=10000):
    """Recalculate budget-only bands using the SAME match order as actual season.
    For played matches: uses opponent order from season_data.m array.
    For remaining matches: uses order from remaining_fixtures.
    This ensures budget line match N is against the same opponent as actual line match N."""
    if not season_data:
        return {}
    
    bands = {}
    for team in season_data:
        td = season_data[team]
        if not td.get('m'):
            continue
        
        # Build fixture list: played matches (same order as actual) + remaining
        fixes = []
        for m in td['m']:
            opp = m[0]
            ih = m[1]
            fixes.append((opp, ih))
        
        for opp, is_home, *_ in remaining_fixtures.get(team, []):
            fixes.append((opp, is_home))
        
        n = len(fixes)
        if n == 0:
            continue
        
        # Compute probabilities for each match
        probs = []
        for opp, ih in fixes:
            wh = wages.get(team, 20) if ih else wages.get(opp, wages.get(fix_name(opp), 20))
            wa = wages.get(opp, wages.get(fix_name(opp), 20)) if ih else wages.get(team, 20)
            x = np.log2(wa / wh)
            ph = 1 - expit(t2 + beta * x)
            pd_ = expit(t2 + beta * x) - expit(t1 + beta * x)
            if ih:
                probs.append((ph, pd_))
            else:
                probs.append((1 - ph - pd_, pd_))
        
        # Simulate
        rng = np.random.random((n_sims, n))
        sim = np.zeros((n_sims, n), dtype=int)
        for m in range(n):
            pw, pd = probs[m]
            for s in range(n_sims):
                if rng[s,m] < pw: sim[s,m] = 3
                elif rng[s,m] < pw + pd: sim[s,m] = 1
        
        cum = np.cumsum(sim, axis=1)
        # Deterministic cumulative expected
        det_cum = []
        det_total = 0.0
        for pw, pd in probs:
            det_total += pw * 3 + pd
            det_cum.append(round(det_total, 1))
        
        bands[team] = {
            'p10': [int(np.percentile(cum[:,i], 10)) for i in range(n)],
            'p50': det_cum,
            'p90': [int(np.percentile(cum[:,i], 90)) for i in range(n)]
        }
    return bands

def get_remaining_fixtures(season_data, fixtures_calendar, lg, season='25/26'):
    """Get ordered remaining fixtures per team from fixtures.json calendar.
    Returns {team: [(opp, is_home, gw, date), ...]} ordered by date when available."""
    played = {}
    for team in season_data:
        played[team] = set()
        for m in season_data[team]['m']:
            played[team].add((fix_name(m[0]), m[1]))
    
    team_remaining = {t: [] for t in season_data}
    
    if fixtures_calendar:
        cal = fixtures_calendar.get(lg, {}).get(season, {}).get('calendar', [])
        for gw_data in cal:
            gw = gw_data.get('gw', 0)
            dates = gw_data.get('dates', [])
            for idx, pair in enumerate(gw_data['matches']):
                h, a = fix_name(pair[0]), fix_name(pair[1])
                match_date = dates[idx] if idx < len(dates) else ''
                if h in team_remaining and (a, 1) not in played.get(h, set()):
                    team_remaining[h].append((a, 1, gw, match_date))
                if a in team_remaining and (h, 0) not in played.get(a, set()):
                    team_remaining[a].append((h, 0, gw, match_date))
        
        # Sort by date if dates are available, falling back to calendar order
        for team in team_remaining:
            team_remaining[team].sort(key=lambda x: x[3] if x[3] else '9999')
    else:
        teams = list(season_data.keys())
        for team in teams:
            for opp in teams:
                if opp == team: continue
                for ih in [1, 0]:
                    if (opp, ih) not in played.get(team, set()):
                        team_remaining[team].append((opp, ih, 0, ''))
    
    return team_remaining

def run_mc_simulation(season_data, wages, beta, t1, t2, remaining_fixtures, n_sims=10000):
    """Run MC simulation using ordered remaining fixtures. Returns fresh bands."""
    teams = list(season_data.keys())
    bands = {}
    
    for team in teams:
        nP = len(season_data[team]['a'])
        fixtures = remaining_fixtures.get(team, [])
        n_rem = len(fixtures)
        
        if n_rem == 0:
            bands[team] = {
                'p10': list(season_data[team]['a']),
                'p50': list(season_data[team]['a']),
                'p90': list(season_data[team]['a'])
            }
            continue
        
        # Compute probabilities for each remaining fixture
        probs = []
        for opp, is_home, *_ in fixtures:
            wh = wages.get(team, 20) if is_home else wages.get(opp, wages.get(fix_name(opp), 20))
            wa = wages.get(opp, wages.get(fix_name(opp), 20)) if is_home else wages.get(team, 20)
            x = np.log2(wa / wh)
            ph = 1 - expit(t2 + beta * x)
            pd_ = expit(t2 + beta * x) - expit(t1 + beta * x)
            if is_home:
                probs.append((ph, pd_))
            else:
                probs.append((1 - ph - pd_, pd_))
        
        # Simulate
        rng = np.random.random((n_sims, n_rem))
        sim_pts = np.zeros((n_sims, n_rem), dtype=int)
        for m_idx in range(n_rem):
            p_win, p_draw = probs[m_idx]
            for s in range(n_sims):
                if rng[s, m_idx] < p_win:
                    sim_pts[s, m_idx] = 3
                elif rng[s, m_idx] < p_win + p_draw:
                    sim_pts[s, m_idx] = 1
        
        cum_sim = np.cumsum(sim_pts, axis=1)
        base_pts = season_data[team]['a'][-1] if season_data[team]['a'] else 0
        
        # Build full bands: locked part + simulated part
        p10 = list(season_data[team]['a'])
        p50 = list(season_data[team]['a'])
        p90 = list(season_data[team]['a'])
        
        for gw_offset in range(n_rem):
            total = base_pts + cum_sim[:, gw_offset]
            p10.append(int(np.percentile(total, 10)))
            p50.append(int(np.percentile(total, 50)))
            p90.append(int(np.percentile(total, 90)))
        
        bands[team] = {'p10': p10, 'p50': p50, 'p90': p90}
    
    return bands


def simulate_position_probs(teams, current_pts, match_list, n_sims=10000, lg=None):
    """Core joint simulation. Returns {team: {cat: probability}} for position categories."""
    n_teams = len(teams)
    n_matches = len(match_list)
    
    # European/relegation spots per league (0-indexed positions)
    # UCL = Champions League, UEL = Europa League, UCOL = Conference League
    LEAGUE_SPOTS = {
        'll': {'ucl': 4, 'uel': 2, 'ucol': 1, 'rel': 3},  # La Liga
        'pl': {'ucl': 4, 'uel': 2, 'ucol': 1, 'rel': 3},  # Premier League
        'sa': {'ucl': 4, 'uel': 2, 'ucol': 1, 'rel': 3},  # Serie A
        'bl': {'ucl': 4, 'uel': 2, 'ucol': 1, 'rel': 3},  # Bundesliga
        'l1': {'ucl': 4, 'uel': 1, 'ucol': 1, 'rel': 3},  # Ligue 1
        'ed': {'ucl': 2, 'uel': 1, 'ucol': 1, 'rel': 3},  # Eredivisie
    }
    spots = LEAGUE_SPOTS.get(lg, {'ucl': 4, 'uel': 2, 'ucol': 1, 'rel': 3})
    n_ucl = spots['ucl']
    n_uel = spots['uel']
    n_ucol = spots['ucol']
    n_rel = spots['rel']
    n_euro = n_ucl + n_uel + n_ucol
    n_mid = n_teams - n_euro - n_rel
    
    if n_matches == 0:
        # Season complete — use actual final standings
        order = np.argsort(-current_pts)
        pos_counts = np.zeros((n_teams, n_teams), dtype=int)
        for rank, idx in enumerate(order):
            pos_counts[idx, rank] = n_sims
    else:
        pos_counts = np.zeros((n_teams, n_teams), dtype=int)  # [team_idx, position] count
        rng = np.random.random((n_sims, n_matches))
        
        for s in range(n_sims):
            pts = current_pts.copy()
            for m_idx, (h_idx, a_idx, ph, pd_) in enumerate(match_list):
                r = rng[s, m_idx]
                if r < ph:
                    pts[h_idx] += 3
                elif r < ph + pd_:
                    pts[h_idx] += 1
                    pts[a_idx] += 1
                else:
                    pts[a_idx] += 3
            # Rank teams (randomize ties)
            noise = np.random.random(n_teams) * 0.001
            order = np.argsort(-(pts + noise))
            for rank, idx in enumerate(order):
                pos_counts[idx, rank] += 1
    
    # Convert to category probabilities using per-league spots
    result = {}
    for i, team in enumerate(teams):
        counts = pos_counts[i]
        result[team] = {
            "1st": round(float(counts[0] / n_sims), 4),
            "ucl": round(float(counts[:n_ucl].sum() / n_sims), 4),
            "uel": round(float(counts[n_ucl:n_ucl+n_uel].sum() / n_sims), 4),
            "ucol": round(float(counts[n_ucl+n_uel:n_euro].sum() / n_sims), 4),
            "mid": round(float(counts[n_euro:n_teams-n_rel].sum() / n_sims), 4),
            "rel": round(float(counts[n_teams-n_rel:].sum() / n_sims), 4)
        }
    return result


def build_match_list(teams, wages, remaining_fixtures, beta, t1, t2):
    """Build deduplicated match list with probabilities."""
    matches_seen = set()
    match_list = []
    for t_idx, team in enumerate(teams):
        for opp, is_home, *_ in remaining_fixtures.get(team, []):
            if opp not in teams:
                continue
            o_idx = teams.index(opp)
            h_idx = t_idx if is_home else o_idx
            a_idx = o_idx if is_home else t_idx
            key = (h_idx, a_idx)
            if key not in matches_seen:
                matches_seen.add(key)
                wh = wages.get(teams[h_idx], 20)
                wa = wages.get(teams[a_idx], 20)
                x = np.log2(wa / wh)
                ph = 1 - expit(t2 + beta * x)
                pd_ = expit(t2 + beta * x) - expit(t1 + beta * x)
                match_list.append((h_idx, a_idx, ph, pd_))
    return match_list


def simulate_current_positions(season_data, wages, beta, t1, t2, remaining_fixtures, n_sims=10000, lg=None):
    """Current season: lock in played results, simulate remaining."""
    teams = list(season_data.keys())
    current_pts = np.array([season_data[t]['a'][-1] if season_data[t]['a'] else 0 for t in teams])
    match_list = build_match_list(teams, wages, remaining_fixtures, beta, t1, t2)
    return simulate_position_probs(teams, current_pts, match_list, n_sims, lg=lg)


def simulate_preseason_positions(wages, beta, t1, t2, fixture_calendar, n_sims=10000, lg=None):
    """Pre-season: simulate full season from scratch using fixture calendar."""
    teams = list(wages.keys())
    n_teams = len(teams)
    current_pts = np.zeros(n_teams)
    
    # Build all matches from fixture calendar
    matches_seen = set()
    match_list = []
    for gw_data in fixture_calendar:
        for h, a in gw_data['matches']:
            h, a = fix_name(h), fix_name(a)
            if h not in teams or a not in teams:
                continue
            h_idx = teams.index(h)
            a_idx = teams.index(a)
            key = (h_idx, a_idx)
            if key not in matches_seen:
                matches_seen.add(key)
                wh = wages.get(h, 20)
                wa = wages.get(a, 20)
                x = np.log2(wa / wh)
                ph = 1 - expit(t2 + beta * x)
                pd_ = expit(t2 + beta * x) - expit(t1 + beta * x)
                match_list.append((h_idx, a_idx, ph, pd_))
    
    return simulate_position_probs(teams, current_pts, match_list, n_sims, lg=lg)


def generate_narratives_all(data):
    """Generate bilingual narrative sentences for each team in 25/26."""
    LEAGUE_SPOTS = {
        'll': {'ucl': 4, 'uel': 2, 'ucol': 1, 'rel': 3},
        'pl': {'ucl': 4, 'uel': 2, 'ucol': 1, 'rel': 3},
        'sa': {'ucl': 4, 'uel': 2, 'ucol': 1, 'rel': 3},
        'bl': {'ucl': 4, 'uel': 2, 'ucol': 1, 'rel': 3},
        'l1': {'ucl': 4, 'uel': 1, 'ucol': 1, 'rel': 3},
        'ed': {'ucl': 2, 'uel': 1, 'ucol': 1, 'rel': 3},
    }
    
    def ordinal(rank, lang='en'):
        if lang == 'es': return f"{rank}º"
        if rank == 1: return "1st"
        if rank == 2: return "2nd"
        if rank == 3: return "3rd"
        return f"{rank}th"
    
    def zone_names(rank, n, spots):
        n_ucl, n_uel, n_ucol, n_rel = spots['ucl'], spots['uel'], spots['ucol'], spots['rel']
        n_euro = n_ucl + n_uel + n_ucol
        if rank <= 1: return ('champion', 'campeón', 1)
        if rank <= n_ucl: return ('Champions League', 'Champions League', 2)
        if rank <= n_ucl + n_uel: return ('Europa League', 'Europa League', 3)
        if rank <= n_euro: return ('Conference League', 'Conference League', 4)
        if rank <= n - n_rel: return ('mid-table', 'mitad de tabla', 5)
        return ('relegation', 'descenso', 6)
    
    result = {}
    
    for lg in PARAMS:
        sd = data['seasons'][lg].get('25/26', {})
        if not sd: continue
        
        pos = data.get('pos', {}).get(lg, {}).get('25/26', {})
        cur = pos.get('cur', {})
        if not cur: continue
        
        bands = data.get('bands', {}).get(lg, {})
        pre_b = data.get('pre', {}).get(lg, {})
        wages = {t: sd[t]['w'] for t in sd if sd[t].get('w', 0) > 0}
        teams = list(sd.keys())
        n = len(teams)
        spots = LEAGUE_SPOTS.get(lg, LEAGUE_SPOTS['ll'])
        
        # Projected ranks (current)
        proj_pts = {}
        for t in teams:
            if bands and t in bands and bands[t].get('p50'):
                proj_pts[t] = bands[t]['p50'][-1]
            elif sd[t].get('a') and len(sd[t]['a']) > 0:
                gp = len(sd[t]['a'])
                proj_pts[t] = round(sd[t]['a'][-1] / gp * 38) if gp > 0 else 0
        proj_rank = {t: i+1 for i, (t, _) in enumerate(sorted(proj_pts.items(), key=lambda x: -x[1]))}
        
        # Pre-season ranks
        pre_pts = {}
        for t in teams:
            if pre_b and t in pre_b and pre_b[t].get('p50'):
                pre_pts[t] = pre_b[t]['p50'][-1]
            elif sd[t].get('e') and len(sd[t]['e']) > 0:
                pre_pts[t] = round(sd[t]['e'][-1])
        pre_rank = {t: i+1 for i, (t, _) in enumerate(sorted(pre_pts.items(), key=lambda x: -x[1]))}
        
        # Wage ranks
        wage_rank = {t: i+1 for i, (t, _) in enumerate(sorted(wages.items(), key=lambda x: -x[1]))}
        
        narr = {}
        for t in teams:
            if t not in cur or t not in proj_rank: continue
            c = cur[t]
            pr = proj_rank[t]
            wr = wage_rank.get(t, pr)
            prer = pre_rank.get(t, pr)
            
            ze, zs, zi = zone_names(pr, n, spots)
            _, _, prezi = zone_names(prer, n, spots)
            
            p_ucl = round(c.get('ucl', 0) * 100)
            p_rel = round(c.get('rel', 0) * 100)
            p_1st = round(c.get('1st', 0) * 100)
            
            rank_diff = prer - pr
            budget_diff = wr - pr
            
            # === ENGLISH ===
            if zi == 1:
                en = f"Projected {ordinal(pr)} with a {p_1st}% chance of the title." if p_1st >= 60 else f"Leading the title race — {p_1st}% chance of being crowned champion."
            elif zi == 2:
                en = f"Projected {ordinal(pr)}, in Champions League places ({p_ucl}% to qualify)."
            elif zi == 3:
                en = f"Projected {ordinal(pr)}, on track for Europa League."
            elif zi == 4:
                en = f"Projected {ordinal(pr)}, in Conference League contention."
            elif zi == 5:
                en = f"Projected {ordinal(pr)}, set for a mid-table finish."
            else:
                en = f"Projected {ordinal(pr)} — facing a {p_rel}% risk of relegation." if p_rel >= 60 else f"Projected {ordinal(pr)}, in the relegation battle ({p_rel}% risk)."
            
            if abs(rank_diff) >= 3 and zi < prezi:
                en += f" A remarkable rise from {ordinal(prer)} pre-season."
            elif abs(rank_diff) >= 3 and zi > prezi:
                en += f" A sharp fall from {ordinal(prer)} pre-season expectations."
            elif budget_diff >= 5:
                en += f" Punching well above their weight as the {ordinal(wr)}-biggest budget."
            elif budget_diff <= -5:
                en += f" Underperforming for the {ordinal(wr)}-biggest budget in the league."
            elif rank_diff > 0 and zi < prezi:
                en += f" Improving on pre-season expectations ({ordinal(prer)})."
            elif rank_diff < 0 and zi > prezi:
                en += f" Below pre-season expectations ({ordinal(prer)})."
            elif abs(budget_diff) >= 3 and budget_diff > 0:
                en += f" Outperforming their {ordinal(wr)}-place budget."
            elif abs(budget_diff) >= 3 and budget_diff < 0:
                en += f" Struggling despite the {ordinal(wr)}-biggest wage bill."
            else:
                en += f" Performing in line with their {ordinal(wr)}-place budget."
            
            # === SPANISH ===
            if zi == 1:
                es = f"Previsto {ordinal(pr,'es')} con un {p_1st}% de probabilidad de ganar la liga." if p_1st >= 60 else f"Lidera la carrera por el título — {p_1st}% de ser campeón."
            elif zi == 2:
                es = f"Previsto {ordinal(pr,'es')}, en puestos de Champions League ({p_ucl}% de clasificarse)."
            elif zi == 3:
                es = f"Previsto {ordinal(pr,'es')}, camino de la Europa League."
            elif zi == 4:
                es = f"Previsto {ordinal(pr,'es')}, en pugna por la Conference League."
            elif zi == 5:
                es = f"Previsto {ordinal(pr,'es')}, apunta a mitad de tabla."
            else:
                es = f"Previsto {ordinal(pr,'es')} — un {p_rel}% de riesgo de descenso." if p_rel >= 60 else f"Previsto {ordinal(pr,'es')}, en lucha por la permanencia ({p_rel}% de riesgo)."
            
            if abs(rank_diff) >= 3 and zi < prezi:
                es += f" Notable ascenso desde el {ordinal(prer,'es')} previsto en pretemporada."
            elif abs(rank_diff) >= 3 and zi > prezi:
                es += f" Fuerte caída respecto al {ordinal(prer,'es')} de pretemporada."
            elif budget_diff >= 5:
                es += f" Rinde muy por encima de su presupuesto ({ordinal(wr,'es')} en masa salarial)."
            elif budget_diff <= -5:
                es += f" Rinde por debajo de su presupuesto ({ordinal(wr,'es')} en masa salarial)."
            elif rank_diff > 0 and zi < prezi:
                es += f" Mejorando respecto a las previsiones ({ordinal(prer,'es')} en pretemporada)."
            elif rank_diff < 0 and zi > prezi:
                es += f" Por debajo de las expectativas ({ordinal(prer,'es')} en pretemporada)."
            elif abs(budget_diff) >= 3 and budget_diff > 0:
                es += f" Supera las expectativas de su presupuesto ({ordinal(wr,'es')})."
            elif abs(budget_diff) >= 3 and budget_diff < 0:
                es += f" Flaquea pese a tener el {ordinal(wr,'es')} mayor presupuesto."
            else:
                es += f" Rinde acorde a su presupuesto ({ordinal(wr,'es')})."
            
            narr[t] = {"en": en, "es": es}
        
        result[lg] = narr
        print(f"    {lg}: {len(narr)} narratives")
    
    return result


def compute_all_position_probs(data, fixtures_cal):
    """Compute position probabilities for all seasons."""
    pos = data.get('pos', {})
    
    for lg in PARAMS:
        if lg not in pos:
            pos[lg] = {}
        p = PARAMS[lg]
        
        for sn in sorted(data['seasons'][lg].keys()):
            sd = data['seasons'][lg][sn]
            wages = {t: sd[t].get('w', 0) for t in sd if sd[t].get('w', 0) > 0}
            if len(wages) < 15:
                continue
            
            # Skip if already computed (for historical seasons)
            if sn != '25/26' and sn in pos[lg] and 'pre' in pos[lg][sn]:
                continue
            
            if sn not in pos[lg]:
                pos[lg][sn] = {}
            
            # Build fixture calendar from played matches
            teams = list(sd.keys())
            ms = set()
            for team in teams:
                for m in sd[team]['m']:
                    ht = team if m[1] else m[0]
                    at = m[0] if m[1] else team
                    ms.add((ht, at))
            cal = [{"gw": 1, "matches": [[h, a] for h, a in ms]}]
            
            # Pre-season
            if sn == '25/26' and fixtures_cal and lg in fixtures_cal and '25/26' in fixtures_cal[lg]:
                cal_data = fixtures_cal[lg]['25/26']
                cal_list = cal_data.get('calendar', cal_data) if isinstance(cal_data, dict) else cal_data
                pre = simulate_preseason_positions(wages, p['beta'], p['theta1'], p['theta2'], cal_list, lg=lg)
            else:
                pre = simulate_preseason_positions(wages, p['beta'], p['theta1'], p['theta2'], cal, lg=lg)
            pos[lg][sn]['pre'] = pre
            
            # Current (only for 25/26)
            if sn == '25/26':
                remaining = get_remaining_fixtures(sd, fixtures_cal, lg)
                cur = simulate_current_positions(sd, wages, p['beta'], p['theta1'], p['theta2'], remaining, lg=lg)
                pos[lg][sn]['cur'] = cur
            
            # Log top 3
            top = sorted(pre.items(), key=lambda x: -x[1]['1st'])[:3]
            top_str = ", ".join([f"{t} {d['1st']*100:.0f}%" for t, d in top])
            cur_str = ""
            if 'cur' in pos[lg][sn]:
                top_c = sorted(pos[lg][sn]['cur'].items(), key=lambda x: -x[1]['1st'])[:3]
                cur_str = " | cur: " + ", ".join([f"{t} {d['1st']*100:.0f}%" for t, d in top_c])
            print(f"    {lg} {sn}: {top_str}{cur_str}")
    
    return pos


def update():
    print(f"=== Update: {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    
    if not os.path.exists(DATA_FILE):
        print("ERROR: data.json not found.")
        sys.exit(1)
    
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    if 'pre' not in data: data['pre'] = {}
    
    # Load fixture calendar
    fixtures_cal = None
    if os.path.exists(FIXTURES_FILE):
        with open(FIXTURES_FILE) as f:
            fixtures_cal = json.load(f)
        print("  Loaded fixtures.json")
    else:
        print("  WARNING: No fixtures.json — using unordered fixtures")
    
    # Update fixture calendar from football-data.org API
    api_fixtures = fetch_fixtures_from_api()
    if api_fixtures:
        if fixtures_cal is None:
            fixtures_cal = {}
        for lg_key in api_fixtures:
            if lg_key not in fixtures_cal:
                fixtures_cal[lg_key] = {}
            fixtures_cal[lg_key]['25/26'] = api_fixtures[lg_key]['25/26']
        # Save updated fixtures.json
        with open(FIXTURES_FILE, 'w') as f:
            json.dump(fixtures_cal, f)
        print("  Updated fixtures.json from API")
    
    files = download_current_season()
    
    for lg in PARAMS:
        if not files[lg]:
            print(f"  Skipping {lg}: download failed")
            continue
        
        existing = data['seasons'][lg].get('25/26', {})
        wages = {t: d['w'] for t, d in existing.items() if d.get('w', 0) > 0}
        
        if len(wages) < 15:
            print(f"  WARNING: only {len(wages)} wages for {lg}")
            continue
        
        p = PARAMS[lg]
        result = process_season(files[lg], wages, p['beta'], p['theta1'], p['theta2'], fixtures_cal, lg)
        
        # Fix names
        for old, new in NAME_MAP.items():
            if old in result:
                result[new] = result.pop(old)
            for team in result:
                for m in result[team]['m']:
                    if m[0] == old: m[0] = new
        
        old_gw = len(list(existing.values())[0]['a']) if existing else 0
        data['seasons'][lg]['25/26'] = result
        
        sample = list(result.keys())[0]
        new_gw = len(result[sample]['a'])
        print(f"  {lg}: {len(result)} teams, GW {old_gw} -> {new_gw}")
        
        # Run MC simulation with fixture calendar
        print(f"  Running MC simulation...")
        remaining = get_remaining_fixtures(result, fixtures_cal, lg)
        new_bands = run_mc_simulation(result, wages, p['beta'], p['theta1'], p['theta2'], remaining)
        data['bands'][lg] = new_bands
        
        sb = new_bands[sample]
        print(f"  MC: {sample} p10/p50/p90 = {sb['p10'][-1]}/{sb['p50'][-1]}/{sb['p90'][-1]}")
        
        # Add remaining fixtures with probabilities to each team
        for team in result:
            rem = remaining.get(team, [])
            r_list = []
            for opp, is_home, gw_num, match_date, *_ in rem:
                wh = wages.get(team, 20) if is_home else wages.get(opp, wages.get(fix_name(opp), 20))
                wa = wages.get(opp, wages.get(fix_name(opp), 20)) if is_home else wages.get(team, 20)
                x = np.log2(wa / wh)
                ph = float(round(1 - expit(p['theta2'] + p['beta'] * x), 2))
                pd_ = float(round(expit(p['theta2'] + p['beta'] * x) - expit(p['theta1'] + p['beta'] * x), 2))
                pa = float(round(1 - ph - pd_, 2))
                # r entry: [opp, isHome, pWin, pDraw, pLoss, matchday, date]
                if is_home:
                    r_list.append([fix_name(opp), 1, ph, pd_, pa, gw_num, match_date[:10] if match_date else ''])
                else:
                    r_list.append([fix_name(opp), 0, pa, pd_, ph, gw_num, match_date[:10] if match_date else ''])
            result[team]['r'] = r_list
        data['seasons'][lg]['25/26'] = result
        print(f"  Added remaining fixtures: {len(result[sample].get('r',[]))} per team")
    
        # Recalculate budget bands with current calendar order
        if fixtures_cal:
            print(f"  Recalculating budget bands with current calendar...")
            pre_bands = recalculate_budget_bands(fixtures_cal, wages, p['beta'], p['theta1'], p['theta2'], lg, result, remaining)
            if pre_bands:
                data['pre'][lg] = pre_bands
                ps = pre_bands.get(sample, {})
                if ps:
                    print(f"  Budget: {sample} p10/p50/p90 = {ps['p10'][-1]}/{ps['p50'][-1]}/{ps['p90'][-1]}")
    
    # Compute position probabilities for all seasons
    print("  Computing position probabilities...")
    data['pos'] = compute_all_position_probs(data, fixtures_cal)
    
    # Generate narratives for 25/26
    print("  Generating narratives...")
    data['narratives'] = generate_narratives_all(data)
    
    # Update cumulative with 25/26 partial season
    print("  Updating cumulative with 25/26...")
    if 'cumulative' not in data:
        data['cumulative'] = {}
    for lg in PARAMS:
        if lg not in data['cumulative']:
            data['cumulative'][lg] = {}
        sd = data['seasons'][lg].get('25/26', {})
        for team in sd:
            t = sd[team]
            if not t.get('a') or not t.get('e') or not t.get('w'):
                continue
            act = t['a'][-1]
            exp = t['e'][-1]
            wage = t['w']
            
            if team not in data['cumulative'][lg]:
                data['cumulative'][lg][team] = [0, 0, 0, []]
            
            c = data['cumulative'][lg][team]
            c[3] = [s for s in c[3] if s[0] != '25/26']
            c[3].append(['25/26', wage, round(exp, 1), act])
            cumOP = sum(s[3] - s[2] for s in c[3])
            nS = len(c[3])
            avgExp = sum(s[2] for s in c[3]) / nS if nS > 0 else 1
            c[0] = round(cumOP, 1)
            c[1] = nS
            c[2] = round((cumOP / nS) / avgExp * 100, 1) if avgExp > 0 else 0
    
    # Save
    out = json.dumps(data, separators=(',',':'), ensure_ascii=False)
    # Only apply safe global replacements (no substring conflicts)
    SAFE_REPLACE = {"Nott'm Forest": "Nottm Forest", "Ath Madrid": "At Madrid"}
    for old, new in SAFE_REPLACE.items():
        out = out.replace(old, new)
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        f.write(out)
    
    print(f"  Saved: {len(out)/1024:.1f} KB")
    print("Done!")

if __name__ == '__main__':
    update()
