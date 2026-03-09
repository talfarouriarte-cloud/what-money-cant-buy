#!/usr/bin/env python3
"""
Weekly data update script for 'What money can't buy'
Downloads latest results from football-data.co.uk and regenerates data.json

Usage:
    python update.py

Requirements:
    pip install pandas numpy scipy requests
"""
import pandas as pd
import numpy as np
from scipy.special import expit
import json, os, requests, sys
from datetime import datetime

# Model parameters (from ordered logit estimation)
PARAMS = {
    'll': {'beta': 0.4719, 'theta1': -1.0404, 'theta2': 0.2081},
    'pl': {'beta': 0.676,  'theta1': -0.8358, 'theta2': 0.2422}
}

# Data URLs for current season
URLS = {
    'll': 'https://www.football-data.co.uk/mmz4281/2526/SP1.csv',
    'pl': 'https://www.football-data.co.uk/mmz4281/2526/E0.csv'
}

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(DATA_DIR, 'data.json')

def download_current_season():
    """Download latest results for current season."""
    results = {}
    for lg, url in URLS.items():
        print(f"  Downloading {lg} from {url}...")
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
    """Process match results into running totals."""
    df = pd.read_csv(filepath, encoding='utf-8', on_bad_lines='skip', low_memory=False)
    df = df[['HomeTeam','AwayTeam','FTR']].dropna()
    
    td = {}
    for t in sorted(set(df['HomeTeam']) | set(df['AwayTeam'])):
        td[t] = {'pts':[],'exp':[],'m':[],'cp':0,'ce':0.0}
    
    for _, r in df.iterrows():
        h, a = r['HomeTeam'], r['AwayTeam']
        wh, wa = wages.get(h, 20), wages.get(a, 20)
        x = np.log2(wa / wh)
        ph = 1 - expit(t2 + beta * x)
        pd_ = expit(t2 + beta * x) - expit(t1 + beta * x)
        pa = expit(t1 + beta * x)
        
        if r['FTR'] == 'H': hp, ap = 3, 0
        elif r['FTR'] == 'A': hp, ap = 0, 3
        else: hp, ap = 1, 1
        
        eh, ea = ph*3 + pd_, pa*3 + pd_
        
        for team, pts, exp, opp, ih in [(h,hp,eh,a,1), (a,ap,ea,h,0)]:
            td[team]['cp'] += pts
            td[team]['ce'] += exp
            td[team]['pts'].append(td[team]['cp'])
            td[team]['exp'].append(round(td[team]['ce'], 1))
            td[team]['m'].append([opp, ih, pts, round(exp, 2)])
    
    return {t: {'a':d['pts'],'e':d['exp'],'m':d['m'],'w':wages.get(t,0)} for t,d in td.items()}

def update():
    print(f"=== Update: {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    
    # Load existing data
    if not os.path.exists(DATA_FILE):
        print("ERROR: data.json not found. Run the initial build first.")
        sys.exit(1)
    
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    
    # Download current season results
    files = download_current_season()
    
    for lg in ['ll', 'pl']:
        if not files[lg]:
            print(f"  Skipping {lg}: download failed")
            continue
        
        # Get wages (from existing 25/26 data or 24/25 fallback)
        existing = data['seasons'][lg].get('25/26', {})
        wages = {t: d['w'] for t, d in existing.items() if d.get('w', 0) > 0}
        
        if len(wages) < 15:
            print(f"  WARNING: only {len(wages)} wages for {lg}, using existing")
            continue
        
        p = PARAMS[lg]
        result = process_season(files[lg], wages, p['beta'], p['theta1'], p['theta2'])
        
        # Fix team name
        if "Nott'm Forest" in result:
            result["Nottm Forest"] = result.pop("Nott'm Forest")
        for team in result:
            for m in result[team]['m']:
                if m[0] == "Nott'm Forest":
                    m[0] = "Nottm Forest"
        
        old_teams = len(data['seasons'][lg].get('25/26', {}))
        data['seasons'][lg]['25/26'] = result
        
        sample = list(result.keys())[0]
        print(f"  {lg} 25/26: {len(result)} teams, {len(result[sample]['a'])} matchweeks (was {old_teams} teams)")
    
    # Save
    out = json.dumps(data, separators=(',',':'), ensure_ascii=False)
    out = out.replace("Nott'm Forest", "Nottm Forest")
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        f.write(out)
    
    print(f"  Saved: {len(out)/1024:.1f} KB")
    print("Done!")

if __name__ == '__main__':
    update()
