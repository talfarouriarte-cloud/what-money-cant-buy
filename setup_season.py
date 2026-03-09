#!/usr/bin/env python3
"""
Season setup script for 'What money can't buy'

Run once at start of each season to build fixtures.json and pre-season bands.

Usage:
    python setup_season.py --season 26/27 --ll LaLiga_fixtures.csv --pl EPL_fixtures.csv

The fixture CSV should have columns including HomeTeam, AwayTeam, and Round/Matchday.
Also works with football-data.co.uk CSVs (uses mirror pattern for remaining).

Requirements: pip install pandas numpy scipy
"""
import pandas as pd
import numpy as np
from scipy.special import expit
import json, os, argparse

PARAMS = {
    'll': {'beta': 0.4719, 'theta1': -1.0404, 'theta2': 0.2081},
    'pl': {'beta': 0.676,  'theta1': -0.8358, 'theta2': 0.2422}
}
NAME_MAP = {"Nott'm Forest": "Nottm Forest", "Ath Madrid": "At Madrid"}
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

def fix_name(n):
    return NAME_MAP.get(n, n)

def build_calendar_from_csv(csv_path):
    df = pd.read_csv(csv_path, encoding='utf-8', on_bad_lines='skip', low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    
    # Detect columns
    home_col = away_col = round_col = None
    for c in df.columns:
        cl = c.lower()
        if 'home' in cl: home_col = c
        elif 'away' in cl: away_col = c
        elif cl in ('round','round number','matchday','jornada','gw'): round_col = c
    
    if not home_col or not away_col:
        home_col, away_col = 'HomeTeam', 'AwayTeam'
    
    df['_h'] = df[home_col].apply(fix_name)
    df['_a'] = df[away_col].apply(fix_name)
    
    teams = sorted(set(df['_h']) | set(df['_a']))
    n_teams = len(teams)
    total_gw = (n_teams - 1) * 2
    
    if round_col:
        df['_gw'] = pd.to_numeric(df[round_col], errors='coerce').fillna(0).astype(int)
    else:
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
            df = df.sort_values('Date').reset_index(drop=True)
        df['_gw'] = (df.index // (n_teams // 2)) + 1
    
    # Check if results exist (played matches)
    has_results = 'FTR' in df.columns
    played = set()
    if has_results:
        for _, r in df.iterrows():
            if pd.notna(r.get('FTR')) and r['FTR'] != '':
                played.add((r['_h'], r['_a']))
    
    # Build calendar
    gw_fixtures = {}
    for _, r in df.iterrows():
        gw = int(r['_gw'])
        if gw < 1 or gw > total_gw:
            continue
        if gw not in gw_fixtures:
            gw_fixtures[gw] = []
        gw_fixtures[gw].append([r['_h'], r['_a']])
    
    # Fill missing GWs with mirror if needed
    all_fixtures = set()
    for gw_list in gw_fixtures.values():
        for h, a in gw_list:
            all_fixtures.add((h, a))
    
    remaining = set()
    for h in teams:
        for a in teams:
            if h != a and (h, a) not in all_fixtures:
                remaining.add((h, a))
    
    if remaining:
        half = n_teams - 1
        for j in range(1, half + 1):
            vgw = j + half
            if vgw not in gw_fixtures:
                gw_fixtures[vgw] = []
            if j in gw_fixtures:
                for h, a in gw_fixtures[j]:
                    if (a, h) in remaining:
                        gw_fixtures[vgw].append([a, h])
                        remaining.discard((a, h))
        if remaining:
            avail = [gw for gw in range(1, total_gw + 1) if len(gw_fixtures.get(gw, [])) < n_teams // 2]
            for i, (h, a) in enumerate(remaining):
                gw = avail[i % len(avail)] if avail else total_gw
                if gw not in gw_fixtures: gw_fixtures[gw] = []
                gw_fixtures[gw].append([h, a])
    
    calendar = []
    for gw in range(1, total_gw + 1):
        matches = gw_fixtures.get(gw, [])
        pflags = [(h, a) in played for h, a in matches]
        calendar.append({'gw': gw, 'matches': matches, 'played': pflags})
    
    total = sum(len(g['matches']) for g in calendar)
    np_ = sum(1 for g in calendar for p in g['played'] if p)
    print(f"  {n_teams} teams, {total} fixtures, {np_} played")
    return calendar, teams

def run_preseason_mc(calendar, wages, beta, t1, t2, teams, n_sims=10000):
    team_fix = {t: [] for t in teams}
    for gw_data in calendar:
        for h, a in gw_data['matches']:
            team_fix[h].append((a, 1))
            team_fix[a].append((h, 0))
    
    bands = {}
    for team in teams:
        fixes = team_fix[team]
        n = len(fixes)
        probs = []
        for opp, ih in fixes:
            wh = wages.get(team, 20) if ih else wages.get(opp, 20)
            wa = wages.get(opp, 20) if ih else wages.get(team, 20)
            x = np.log2(wa / wh)
            ph = 1 - expit(t2 + beta * x)
            pd_ = expit(t2 + beta * x) - expit(t1 + beta * x)
            probs.append((ph, pd_) if ih else (1 - ph - pd_, pd_))
        
        rng = np.random.random((n_sims, n))
        sim = np.zeros((n_sims, n), dtype=int)
        for m in range(n):
            pw, pd = probs[m]
            for s in range(n_sims):
                if rng[s,m] < pw: sim[s,m] = 3
                elif rng[s,m] < pw + pd: sim[s,m] = 1
        
        cum = np.cumsum(sim, axis=1)
        bands[team] = {
            'p10': [int(np.percentile(cum[:,i], 10)) for i in range(n)],
            'p50': [int(np.percentile(cum[:,i], 50)) for i in range(n)],
            'p90': [int(np.percentile(cum[:,i], 90)) for i in range(n)]
        }
    return bands

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--season', default='25/26')
    parser.add_argument('--ll', help='La Liga CSV')
    parser.add_argument('--pl', help='Premier League CSV')
    parser.add_argument('--sims', type=int, default=10000)
    args = parser.parse_args()
    
    fix_file = os.path.join(DATA_DIR, 'fixtures.json')
    data_file = os.path.join(DATA_DIR, 'data.json')
    
    fixtures = json.load(open(fix_file)) if os.path.exists(fix_file) else {}
    data = json.load(open(data_file)) if os.path.exists(data_file) else {'seasons':{},'bands':{},'pre':{},'model':PARAMS,'cumulative':{}}
    
    for lg, csv in [('ll', args.ll), ('pl', args.pl)]:
        if not csv: continue
        print(f"\n=== {lg} {args.season} ===")
        cal, teams = build_calendar_from_csv(csv)
        if lg not in fixtures: fixtures[lg] = {}
        fixtures[lg][args.season] = {'calendar': cal, 'teams': teams}
        
        wages = {}
        if lg in data.get('seasons',{}) and args.season in data['seasons'][lg]:
            wages = {fix_name(t): d['w'] for t, d in data['seasons'][lg][args.season].items() if d.get('w',0) > 0}
        
        if len(wages) >= 15:
            p = PARAMS[lg]
            print(f"  Running pre-season MC ({args.sims} sims)...")
            pre = run_preseason_mc(cal, wages, p['beta'], p['theta1'], p['theta2'], teams, args.sims)
            if 'pre' not in data: data['pre'] = {}
            data['pre'][lg] = pre
            s = teams[0]
            print(f"  {s}: p10={pre[s]['p10'][-1]} p50={pre[s]['p50'][-1]} p90={pre[s]['p90'][-1]}")
        else:
            print(f"  Skipping MC: {len(wages)} wages (need 15+)")
    
    with open(fix_file, 'w', encoding='utf-8') as f:
        json.dump(fixtures, f, separators=(',',':'), ensure_ascii=False)
    print(f"\nSaved fixtures.json ({os.path.getsize(fix_file)/1024:.1f} KB)")
    
    if data.get('pre'):
        out = json.dumps(data, separators=(',',':'), ensure_ascii=False)
        for o, n in NAME_MAP.items(): out = out.replace(o, n)
        with open(data_file, 'w', encoding='utf-8') as f: f.write(out)
        print(f"Saved data.json ({os.path.getsize(data_file)/1024:.1f} KB)")

if __name__ == '__main__':
    main()
