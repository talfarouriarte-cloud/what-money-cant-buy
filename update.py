#!/usr/bin/env python3
"""
Daily data update for 'What money can't buy'
Downloads latest results, recomputes expected points, re-runs MC simulation.

Reads fixture calendar from fixtures.json (built by setup_season.py).
Produces updated data.json with fresh bands anchored at latest results.

Usage: python update.py
Requirements: pip install pandas numpy scipy requests
"""
import pandas as pd
import numpy as np
from scipy.special import expit
import json, os, requests, sys
from datetime import datetime

PARAMS = {
    'll': {'beta': 0.4719, 'theta1': -1.0404, 'theta2': 0.2081},
    'pl': {'beta': 0.676,  'theta1': -0.8358, 'theta2': 0.2422}
}
URLS = {
    'll': 'https://www.football-data.co.uk/mmz4281/2526/SP1.csv',
    'pl': 'https://www.football-data.co.uk/mmz4281/2526/E0.csv'
}
NAME_MAP = {"Nott'm Forest": "Nottm Forest", "Ath Madrid": "At Madrid"}
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(DATA_DIR, 'data.json')
FIXTURES_FILE = os.path.join(DATA_DIR, 'fixtures.json')

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

def process_season(filepath, wages, beta, t1, t2):
    df = pd.read_csv(filepath, encoding='utf-8', on_bad_lines='skip', low_memory=False)
    df = df[['HomeTeam','AwayTeam','FTR']].dropna()
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
        for team, pts, exp, opp, ih in [(h,hp,eh,a,1),(a,ap,ea,h,0)]:
            td[team]['cp'] += pts; td[team]['ce'] += exp
            td[team]['pts'].append(td[team]['cp'])
            td[team]['exp'].append(round(td[team]['ce'], 1))
            td[team]['m'].append([opp, ih, pts, round(exp, 2)])
    return {t: {'a':d['pts'],'e':d['exp'],'m':d['m'],'w':wages.get(t, wages.get(fix_name(t), 0))} for t,d in td.items()}

def get_remaining_fixtures(season_data, fixtures_calendar, lg, season='25/26'):
    """Get ordered remaining fixtures per team from fixtures.json calendar."""
    played = {}
    for team in season_data:
        played[team] = set()
        for m in season_data[team]['m']:
            played[team].add((fix_name(m[0]), m[1]))
    
    team_remaining = {t: [] for t in season_data}
    
    if fixtures_calendar:
        cal = fixtures_calendar.get(lg, {}).get(season, {}).get('calendar', [])
        for gw_data in cal:
            for h, a in gw_data['matches']:
                h, a = fix_name(h), fix_name(a)
                # Home team's fixture
                if h in team_remaining and (a, 1) not in played.get(h, set()):
                    team_remaining[h].append((a, 1))
                # Away team's fixture
                if a in team_remaining and (h, 0) not in played.get(a, set()):
                    team_remaining[a].append((h, 0))
    else:
        # Fallback: unordered
        teams = list(season_data.keys())
        for team in teams:
            for opp in teams:
                if opp == team: continue
                for ih in [1, 0]:
                    if (opp, ih) not in played.get(team, set()):
                        team_remaining[team].append((opp, ih))
    
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
        for opp, is_home in fixtures:
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


def simulate_position_probs(teams, current_pts, match_list, n_sims=10000):
    """Core joint simulation. Returns {team: {cat: probability}} for position categories."""
    n_teams = len(teams)
    n_matches = len(match_list)
    
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
    
    # Convert to category probabilities
    result = {}
    for i, team in enumerate(teams):
        counts = pos_counts[i]
        result[team] = {
            "1st": round(float(counts[0] / n_sims), 4),
            "ucl": round(float(counts[:4].sum() / n_sims), 4),
            "uel": round(float(counts[4:6].sum() / n_sims), 4),
            "ucol": round(float(counts[6] / n_sims), 4),
            "mid": round(float(counts[7:17].sum() / n_sims), 4),
            "rel": round(float(counts[17:].sum() / n_sims), 4)
        }
    return result


def build_match_list(teams, wages, remaining_fixtures, beta, t1, t2):
    """Build deduplicated match list with probabilities."""
    matches_seen = set()
    match_list = []
    for t_idx, team in enumerate(teams):
        for opp, is_home in remaining_fixtures.get(team, []):
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


def simulate_current_positions(season_data, wages, beta, t1, t2, remaining_fixtures, n_sims=10000):
    """Current season: lock in played results, simulate remaining."""
    teams = list(season_data.keys())
    current_pts = np.array([season_data[t]['a'][-1] if season_data[t]['a'] else 0 for t in teams])
    match_list = build_match_list(teams, wages, remaining_fixtures, beta, t1, t2)
    return simulate_position_probs(teams, current_pts, match_list, n_sims)


def simulate_preseason_positions(wages, beta, t1, t2, fixture_calendar, n_sims=10000):
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
    
    return simulate_position_probs(teams, current_pts, match_list, n_sims)


def compute_all_position_probs(data, fixtures_cal):
    """Compute position probabilities for all seasons."""
    pos = data.get('pos', {})
    
    for lg in ['ll', 'pl']:
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
                pre = simulate_preseason_positions(wages, p['beta'], p['theta1'], p['theta2'], cal_list)
            else:
                pre = simulate_preseason_positions(wages, p['beta'], p['theta1'], p['theta2'], cal)
            pos[lg][sn]['pre'] = pre
            
            # Current (only for 25/26)
            if sn == '25/26':
                remaining = get_remaining_fixtures(sd, fixtures_cal, lg)
                cur = simulate_current_positions(sd, wages, p['beta'], p['theta1'], p['theta2'], remaining)
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
    
    # Load fixture calendar
    fixtures_cal = None
    if os.path.exists(FIXTURES_FILE):
        with open(FIXTURES_FILE) as f:
            fixtures_cal = json.load(f)
        print("  Loaded fixtures.json")
    else:
        print("  WARNING: No fixtures.json — using unordered fixtures")
    
    files = download_current_season()
    
    for lg in ['ll', 'pl']:
        if not files[lg]:
            print(f"  Skipping {lg}: download failed")
            continue
        
        existing = data['seasons'][lg].get('25/26', {})
        wages = {t: d['w'] for t, d in existing.items() if d.get('w', 0) > 0}
        
        if len(wages) < 15:
            print(f"  WARNING: only {len(wages)} wages for {lg}")
            continue
        
        p = PARAMS[lg]
        result = process_season(files[lg], wages, p['beta'], p['theta1'], p['theta2'])
        
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
            for opp, is_home in rem:
                wh = wages.get(team, 20) if is_home else wages.get(opp, wages.get(fix_name(opp), 20))
                wa = wages.get(opp, wages.get(fix_name(opp), 20)) if is_home else wages.get(team, 20)
                x = np.log2(wa / wh)
                ph = float(round(1 - expit(p['theta2'] + p['beta'] * x), 2))
                pd_ = float(round(expit(p['theta2'] + p['beta'] * x) - expit(p['theta1'] + p['beta'] * x), 2))
                pa = float(round(1 - ph - pd_, 2))
                if is_home:
                    r_list.append([fix_name(opp), 1, ph, pd_, pa])
                else:
                    r_list.append([fix_name(opp), 0, pa, pd_, ph])
            result[team]['r'] = r_list
        data['seasons'][lg]['25/26'] = result
        print(f"  Added remaining fixtures: {len(result[sample].get('r',[]))} per team")
    
    # Compute position probabilities for all seasons
    print("  Computing position probabilities...")
    data['pos'] = compute_all_position_probs(data, fixtures_cal)
    
    # Save
    out = json.dumps(data, separators=(',',':'), ensure_ascii=False)
    for old, new in NAME_MAP.items():
        out = out.replace(old, new)
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        f.write(out)
    
    print(f"  Saved: {len(out)/1024:.1f} KB")
    print("Done!")

if __name__ == '__main__':
    update()
