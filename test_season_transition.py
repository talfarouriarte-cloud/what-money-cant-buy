#!/usr/bin/env python3
"""
Test script: simulates season transition without touching live data.
Run with: python test_season_transition.py --month 8 --year 2026

Simulates what update.py would do at a given date:
- Which season it detects
- Whether wages exist in all_wages.json
- What fallbacks kick in
"""
import json, os, argparse

WAGES_LG_MAP = {'ll': 'la_liga', 'pl': 'premier_league', 'sa': 'serie_a',
                'bl': 'bundesliga', 'l1': 'ligue_1', 'ed': 'eredivisie'}

def simulate(month, year, wages_file='all_wages.json'):
    y = year % 100
    season = f'{y}/{y+1:02d}' if month >= 8 else f'{y-1:02d}/{y:02d}'
    prev_y = int(season[:2]) - 1
    prev_sn = f'{prev_y:02d}/{prev_y+1:02d}'
    csv_year = season.replace('/', '')
    
    print(f"=== Simulating: {year}-{month:02d}-01 ===")
    print(f"CURRENT_SEASON: {season}")
    print(f"CSV URL: https://www.football-data.co.uk/mmz4281/{csv_year}/SP1.csv")
    
    try:
        with open(wages_file) as f:
            all_w = json.load(f)
    except FileNotFoundError:
        print(f"\n❌ {wages_file} not found")
        return
    
    print(f"\n--- load_wages() per league ---")
    for lg, lg_long in WAGES_LG_MAP.items():
        w = all_w.get(lg_long, {}).get(season, {})
        prev_w = all_w.get(lg_long, {}).get(prev_sn, {})
        
        if w and len(w) >= 15:
            _min = min(w.values())
            top = sorted(w.items(), key=lambda x: -x[1])[:2]
            print(f"  ✅ {lg}: {len(w)} teams from {season}. Top: {top[0][0]}={top[0][1]}M. Min: {_min}M")
        elif prev_w:
            merged = dict(prev_w)
            for t, v in w.items():
                merged[t] = v
            _min = min(merged.values())
            n_new = len(w)
            n_fill = len(merged) - n_new
            print(f"  ⚠️  {lg}: {n_new} teams for {season} + {n_fill} filled from {prev_sn} = {len(merged)} total. Min: {_min}M")
            # Check for promoted teams (in CSV but not in wages)
            print(f"       Promoted teams will get _min={_min}M until wages uploaded")
        else:
            print(f"  ❌ {lg}: no wages for {season} or {prev_sn}")
    
    print(f"\n--- Frontend ---")
    print(f"CUR_SN = latest season key in data.json")
    print(f"After first update.py run with {season}: CUR_SN will be '{season}'")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Simulate season transition')
    parser.add_argument('--month', type=int, required=True, help='Month (1-12)')
    parser.add_argument('--year', type=int, required=True, help='Year (e.g. 2026)')
    args = parser.parse_args()
    simulate(args.month, args.year)
