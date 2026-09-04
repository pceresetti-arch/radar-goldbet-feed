#!/usr/bin/env python3
import concurrent.futures
import json
import math
import pathlib
from collections import defaultdict, Counter
from datetime import datetime, timezone

from curl_cffi import requests

ROOT = pathlib.Path('feed')
NOW = datetime.now(timezone.utc)
LOOKBACK = 8
MAX_TARGET_MATCHES = 6
MIN_PAIR_STARTS = 2
FM_H = {
    'Accept': 'application/json,text/plain,*/*',
    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
    'Referer': 'https://www.fotmob.com/'
}


def load(name, default):
    p = ROOT / name
    try:
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    except Exception:
        return default


def fm_json(url):
    r = requests.get(url, headers=FM_H, impersonate='chrome', timeout=22)
    r.raise_for_status()
    return r.json()


def team_id(t):
    return (t or {}).get('id') or (t or {}).get('teamId')


def finished_match_ids(team_payload, wanted_team_id):
    found = {}
    def walk(x):
        if isinstance(x, dict):
            mid = x.get('id') or x.get('matchId')
            home = x.get('home') or x.get('homeTeam') or {}
            away = x.get('away') or x.get('awayTeam') or {}
            st = x.get('status') or {}
            finished = st.get('finished') if isinstance(st, dict) else None
            if finished is None:
                reason = str((st.get('reason') if isinstance(st, dict) else '') or '').lower()
                finished = reason in {'ft','aet','pen','finished','full-time'}
            if mid is not None and finished and str(wanted_team_id) in {str(team_id(home)), str(team_id(away))}:
                found[str(mid)] = {'match_id': int(mid), 'time': st.get('utcTime') if isinstance(st, dict) else None}
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(team_payload)
    return [x['match_id'] for x in sorted(found.values(), key=lambda r: str(r.get('time') or ''), reverse=True)[:LOOKBACK]]


def safe_float(v):
    try: return float(v)
    except Exception: return None


def role_bucket(p):
    # FotMob lineup coordinates are used only as contextual role buckets.
    vert = safe_float(p.get('verticalLayout'))
    horiz = safe_float(p.get('horizontalLayout'))
    pos = str(p.get('positionId') or p.get('usualPlayingPositionId') or '')
    if vert is not None:
        depth = 'ATTACK' if vert >= 0.70 else ('MIDFIELD' if vert >= 0.42 else 'DEFENCE')
        lane = 'LEFT' if horiz is not None and horiz < 0.34 else ('RIGHT' if horiz is not None and horiz > 0.66 else 'CENTER')
        return f'{depth}_{lane}'
    return f'POSITION_{pos}' if pos else 'UNKNOWN'


def substitution_time(p, typ):
    for e in ((p.get('performance') or {}).get('substitutionEvents') or []):
        if isinstance(e, dict) and str(e.get('type')) == typ:
            try: return int(e.get('time'))
            except Exception: pass
    return None


def player_minutes(p, starter):
    if starter:
        out = substitution_time(p, 'subOut')
        return min(90, max(1, out)) if out is not None else 90
    inn = substitution_time(p, 'subIn')
    out = substitution_time(p, 'subOut')
    if inn is None: return 0
    return max(0, (min(90, out) if out is not None else 90) - inn)


def parse_match(detail):
    content = detail.get('content') or {}
    lineup = content.get('lineup') or {}
    teams = []
    for key in ('homeTeam','awayTeam'):
        t = lineup.get(key)
        if isinstance(t, dict): teams.append(t)
    players = {}
    by_team = defaultdict(list)
    for t in teams:
        tid = team_id(t)
        for starter, key in ((True,'starters'),(False,'subs')):
            for p in t.get(key) or []:
                if not isinstance(p, dict) or p.get('id') is None: continue
                row = {
                    'id': p.get('id'), 'name': p.get('name'), 'team_id': tid,
                    'starter': starter, 'minutes': player_minutes(p, starter),
                    'role': role_bucket(p),
                }
                players[str(p.get('id'))] = row
                by_team[str(tid)].append(row)
    stat = defaultdict(lambda: {'shots':0,'sot':0,'xg':0.0,'goals':0})
    for s in ((content.get('shotmap') or {}).get('shots') or []):
        if not isinstance(s, dict) or s.get('playerId') is None: continue
        d = stat[str(s.get('playerId'))]
        d['shots'] += 1
        d['sot'] += int(bool(s.get('isOnTarget')))
        try: d['xg'] += float(s.get('expectedGoals') or 0)
        except Exception: pass
        d['goals'] += int(str(s.get('eventType') or '').lower() == 'goal')
    return {'players': players, 'by_team': dict(by_team), 'stats': dict(stat)}


def metric_row(matches, pid):
    mins=shots=sot=goals=0; xg=0.0; apps=starts=0
    roles=Counter()
    for m in matches:
        p = m['players'].get(str(pid))
        if not p: continue
        apps += 1; starts += int(p['starter']); mins += int(p['minutes'] or 0); roles[p['role']] += 1
        s = m['stats'].get(str(pid), {})
        shots += int(s.get('shots') or 0); sot += int(s.get('sot') or 0); goals += int(s.get('goals') or 0); xg += float(s.get('xg') or 0)
    per90 = lambda v: round(v*90/mins,3) if mins >= 90 else None
    return {
        'appearances':apps,'starts':starts,'minutes':mins,'goals':goals,'shots':shots,'shots_on_target':sot,'xg':round(xg,3),
        'goals_per90':per90(goals),'shots_per90':per90(shots),'sot_per90':per90(sot),'xg_per90':per90(xg),
        'dominant_role': roles.most_common(1)[0][0] if roles else None,'role_counts':dict(roles)
    }


def player_synergy(pid, tid, matches):
    relevant = [m for m in matches if str(pid) in m['players'] and str(m['players'][str(pid)].get('team_id')) == str(tid)]
    base = metric_row(relevant, pid)

    role_groups = defaultdict(list)
    for m in relevant:
        role_groups[m['players'][str(pid)].get('role') or 'UNKNOWN'].append(m)
    role_splits = []
    for role, ms in role_groups.items():
        r = metric_row(ms, pid); r['role'] = role; role_splits.append(r)
    role_splits.sort(key=lambda r: ((r.get('xg_per90') or -1), r.get('minutes') or 0), reverse=True)

    teammate_games = defaultdict(list)
    teammate_names = {}
    for m in relevant:
        target = m['players'][str(pid)]
        if not target.get('starter'): continue
        for q in m['by_team'].get(str(tid), []):
            if str(q.get('id')) == str(pid) or not q.get('starter'): continue
            teammate_games[str(q['id'])].append(m); teammate_names[str(q['id'])] = q.get('name')
    pairs = []
    for qid, ms in teammate_games.items():
        if len(ms) < MIN_PAIR_STARTS: continue
        with_q = metric_row(ms, pid)
        without = [m for m in relevant if m not in ms]
        without_q = metric_row(without, pid) if without else None
        delta_xg90 = None
        if without_q and with_q.get('xg_per90') is not None and without_q.get('xg_per90') is not None:
            delta_xg90 = round(with_q['xg_per90'] - without_q['xg_per90'], 3)
        pairs.append({
            'teammate_id':qid,'teammate':teammate_names.get(qid),'co_starts':len(ms),
            'with_teammate':with_q,'without_teammate':without_q,'delta_xg_per90':delta_xg90,
            'sample_warning': len(ms) < 4 or (without_q and without_q.get('appearances',0) < 2)
        })
    pairs.sort(key=lambda r: ((r.get('delta_xg_per90') if r.get('delta_xg_per90') is not None else -999), r['co_starts']), reverse=True)
    return {'baseline':base,'position_splits':role_splits,'teammate_splits':pairs[:8]}


lineups = load('lineups-current.json', {'matches':[]})
targets = [m for m in (lineups.get('matches') or []) if m.get('status') in ('SOURCE_CONFIRMED','CROSS_CONFIRMED') and (m.get('lineup') or {}).get('confirmed')]
targets.sort(key=lambda m: abs(float(m.get('minutes_to_start') or 9999)))
targets = targets[:MAX_TARGET_MATCHES]

team_ids = set()
for m in targets:
    for t in (m.get('lineup') or {}).get('teams') or []:
        if t.get('team_id') is not None: team_ids.add(str(t['team_id']))

team_match_ids = {}; errors=[]
for tid in team_ids:
    try:
        tp = fm_json(f'https://www.fotmob.com/api/data/teams?id={tid}&ccode3=ITA')
        team_match_ids[tid] = finished_match_ids(tp, tid)
    except Exception as e:
        errors.append({'team_id':tid,'stage':'team_history','error':type(e).__name__+': '+str(e)[:160]})

all_ids = sorted({mid for mids in team_match_ids.values() for mid in mids})
def fetch(mid):
    try: return str(mid), parse_match(fm_json(f'https://www.fotmob.com/api/data/matchDetails?matchId={mid}')), None
    except Exception as e: return str(mid), None, type(e).__name__+': '+str(e)[:160]
features={}
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    for mid, feat, err in ex.map(fetch, all_ids):
        if feat: features[mid]=feat
        elif err: errors.append({'match_id':mid,'stage':'match_detail','error':err})

out=[]
for m in targets:
    tm=[]
    for t in (m.get('lineup') or {}).get('teams') or []:
        tid=str(t.get('team_id'))
        hist=[features[str(mid)] for mid in team_match_ids.get(tid,[]) if str(mid) in features]
        players=[]
        for p in t.get('starters') or []:
            if p.get('id') is None: continue
            players.append({'player_id':p.get('id'),'player':p.get('name'),'current_position_id':p.get('position_id'),**player_synergy(p.get('id'),tid,hist)})
        tm.append({'team_id':t.get('team_id'),'team':t.get('team_name'),'history_matches':len(hist),'players':players})
    out.append({'match_market_id':m.get('match_market_id'),'match':m.get('match'),'league':m.get('league'),'start_time':m.get('start_time'),'minutes_to_start':m.get('minutes_to_start'),'teams':tm})

payload={
    'schema':'radar-player-synergy-position-v1','generated_at':NOW.isoformat(),'lookback_matches':LOOKBACK,
    'method':'Recent official/historical FotMob lineups + shotmaps. Splits by actual starting role bucket and co-starting teammates.',
    'policy':'Context modifier only. Small-sample teammate/position splits must not create a standalone edge; use shrinkage/caution and require current official XI.',
    'target_count':len(targets),'errors':errors,'matches':out
}
ROOT.mkdir(exist_ok=True)
(ROOT/'player-synergy-position-current.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
summary={'schema':payload['schema'],'generated_at':payload['generated_at'],'target_count':len(out),'errors':len(errors),'matches':[]}
for m in out:
    summary['matches'].append({'match':m['match'],'teams':[{'team':t['team'],'history_matches':t['history_matches'],'players':len(t['players']),'players_with_pair_splits':sum(1 for p in t['players'] if p.get('teammate_splits')),'players_with_position_splits':sum(1 for p in t['players'] if len(p.get('position_splits') or [])>1)} for t in m['teams']]})
(ROOT/'player-synergy-position-current-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
