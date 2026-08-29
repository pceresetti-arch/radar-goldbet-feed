#!/usr/bin/env python3
import difflib
import hashlib
import json
import pathlib
import re
import time
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from curl_cffi import requests

ROME = ZoneInfo('Europe/Rome')
NOW = datetime.now(timezone.utc)
FM_H = {
    'Accept': 'application/json,text/plain,*/*',
    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
    'Referer': 'https://www.fotmob.com/'
}


def fm_json(url):
    r = requests.get(url, headers=FM_H, impersonate='chrome', timeout=25)
    r.raise_for_status()
    return r.json(), r.status_code


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(fc|cf|sc|ac|afc|cd|fk|bk|calcio|club|deportivo|sporting|united|city|pr|sp|rj|mg)\b', ' ', s)
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())


def side_score(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    A, B = set(a.split()), set(b.split())
    jac = len(A & B) / max(1, len(A | B))
    cont = 1 if a in b or b in a else 0
    return .62 * seq + .23 * jac + .15 * cont


def split_match(s):
    for sep in (' - ', ' vs ', ' v '):
        if sep in str(s):
            return tuple(x.strip() for x in str(s).split(sep, 1))
    return str(s), ''


def parse_iso(s):
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception:
        return None


def parse_aams(s):
    try:
        return datetime.strptime(str(s), '%d-%m-%Y %H:%M').replace(tzinfo=ROME).astimezone(timezone.utc)
    except Exception:
        return None


def player_name(row):
    return row.get('name') or (row.get('player') or {}).get('name') or row.get('playerName')


def normalize_player(r, bench=False):
    n = player_name(r)
    if not n:
        return None
    out = {
        'name': n,
        'id': r.get('id') or (r.get('player') or {}).get('id'),
        'shirt_number': r.get('shirtNumber') or r.get('shirt') or r.get('jerseyNumber'),
    }
    if not bench:
        out.update({
            'position_id': r.get('positionId'),
            'usual_position_id': r.get('usualPlayingPositionId'),
            'horizontal_layout': r.get('horizontalLayout'),
            'vertical_layout': r.get('verticalLayout'),
        })
    return out


def normalize_team(t):
    if not isinstance(t, dict):
        return None
    starters = []
    for r in (t.get('starters') or t.get('players') or t.get('startingXI') or []):
        if isinstance(r, dict):
            p = normalize_player(r)
            if p:
                starters.append(p)
    bench = []
    for r in (t.get('bench') or t.get('substitutes') or t.get('subs') or []):
        if isinstance(r, dict):
            p = normalize_player(r, bench=True)
            if p:
                bench.append(p)
    return {
        'team_id': t.get('id') or t.get('teamId'),
        'team_name': t.get('name') or t.get('teamName'),
        'formation': t.get('formation'),
        'starters': starters,
        'bench': bench,
        'raw_keys': list(t.keys()),
    }


def xi_fingerprint(teams):
    if len(teams) < 2:
        return None
    parts = []
    for t in teams[:2]:
        ids = [str(p.get('id') or norm(p.get('name'))) for p in (t.get('starters') or [])]
        parts.append(str(t.get('team_id') or norm(t.get('team_name'))) + ':' + ','.join(ids))
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()[:20]


def parse_lineup(line):
    if not isinstance(line, dict) or not line:
        return {'present': False, 'complete_11v11': False, 'confirmed': False, 'historical_reference': False, 'teams': [], 'raw_keys': []}
    teams = []
    if isinstance(line.get('homeTeam'), dict) or isinstance(line.get('awayTeam'), dict):
        for key in ('homeTeam', 'awayTeam'):
            nt = normalize_team(line.get(key))
            if nt:
                teams.append(nt)
    else:
        rawteams = line.get('lineups') or line.get('teams') or []
        for t in rawteams if isinstance(rawteams, list) else []:
            nt = normalize_team(t)
            if nt:
                teams.append(nt)
    present = any(len(t.get('starters') or []) > 0 for t in teams)
    complete = len(teams) >= 2 and all(len(t.get('starters') or []) == 11 for t in teams[:2])
    lineup_type = str(line.get('lineupType') or '').strip()
    provider_source = str(line.get('source') or '').strip()
    lt, ps = lineup_type.lower(), provider_source.lower()
    historical_reference = lt in {'laststarting11','predicted','probable','expected'} or 'laststarting' in ps or 'predicted' in ps or 'probable' in ps
    confirmed = complete and lt == 'standard' and not historical_reference
    return {
        'present': present,
        'complete_11v11': complete,
        'confirmed': confirmed,
        'historical_reference': historical_reference,
        'lineup_type': lineup_type,
        'provider_source': provider_source,
        'teams': teams,
        'xi_fingerprint': xi_fingerprint(teams),
        'raw_keys': list(line.keys()),
    }


def old_is_valid_official(m):
    if not isinstance(m, dict) or m.get('status') not in ('SOURCE_CONFIRMED','CROSS_CONFIRMED'):
        return False
    ln = m.get('lineup') or {}
    return bool(ln.get('confirmed')) and str(ln.get('lineup_type') or '').lower() == 'standard'


def add_target(targets, *, market_id=None, event_id=None, match=None, league=None, start=None, origin=None):
    if not match or not start:
        return
    dt = parse_iso(start) or parse_aams(start)
    if not dt:
        return
    delta = (dt - NOW).total_seconds() / 60
    if not (-15 <= delta <= 120):
        return
    key = str(market_id or event_id or f'{norm(match)}|{int(dt.timestamp())}')
    targets[key] = {
        'match_market_id': None if market_id is None else str(market_id),
        'match_event_id': event_id,
        'match': str(match),
        'start_time': dt.astimezone(ROME).strftime('%d-%m-%Y %H:%M'),
        'start_utc': dt.isoformat(),
        'league': league,
        'minutes_to_start': round(delta, 1),
        'target_origin': origin,
    }


targets = {}
target_sources = []

# 1) Canonical fresh BetFlag Worker-backed fixture index. This is the primary
# target source for the same fixtures whose prices the Radar will analyse.
fi = pathlib.Path('feed/betflag-fixtures-index.json')
if fi.exists():
    try:
        j = json.loads(fi.read_text(encoding='utf-8'))
        if j.get('source_healthy'):
            for f in j.get('fixtures') or []:
                if isinstance(f, dict):
                    add_target(
                        targets,
                        market_id=f.get('match_market_id'),
                        event_id=f.get('match_event_id'),
                        match=f.get('match'),
                        league=f.get('league'),
                        start=f.get('match_start'),
                        origin='BETFLAG_WORKER_FIXTURE_INDEX'
                    )
            target_sources.append('feed/betflag-fixtures-index.json')
    except Exception:
        pass

# 2) Legacy cached upcoming summary remains continuity-only fallback.
up = pathlib.Path('feed/radar-betflag-v7-live-upcoming-summary.json')
if up.exists():
    try:
        j = json.loads(up.read_text(encoding='utf-8'))
        for f in j.get('fixtures') or []:
            if isinstance(f, dict):
                add_target(targets, market_id=f.get('match_market_id'), event_id=f.get('match_event_id'), match=f.get('match'), league=f.get('league'), start=f.get('start_rome'), origin='BETFLAG_CACHED_UPCOMING')
        target_sources.append('feed/radar-betflag-v7-live-upcoming-summary.json')
    except Exception:
        pass

# 3) Runtime request fixtures: lets Radar pass the exact fixtures it is analysing.
rp = pathlib.Path('radar-runtime-request.json')
if rp.exists():
    try:
        j = json.loads(rp.read_text(encoding='utf-8'))
        for f in j.get('fixtures') or []:
            if isinstance(f, dict):
                add_target(targets, market_id=f.get('match_market_id'), event_id=f.get('match_event_id'), match=f.get('match'), league=f.get('league'), start=f.get('start_rome') or f.get('start_time'), origin='RADAR_RUNTIME_REQUEST')
        target_sources.append('radar-runtime-request.json')
    except Exception:
        pass

# 4) Retain still-relevant targets from the previous feed as a last continuity fallback.
old_by_key = {}
oldp = pathlib.Path('feed/lineups-current.json')
if oldp.exists():
    try:
        old = json.loads(oldp.read_text(encoding='utf-8'))
        old_by_key = {str(m.get('match_market_id') or m.get('match_event_id') or i): m for i,m in enumerate(old.get('matches', [])) if isinstance(m, dict)}
        for m in old.get('matches', []):
            if isinstance(m, dict):
                add_target(targets, market_id=m.get('match_market_id'), event_id=m.get('match_event_id'), match=m.get('match'), league=m.get('league'), start=m.get('start_utc') or m.get('start_time'), origin='PREVIOUS_LINEUP_FEED')
        target_sources.append('feed/lineups-current.json')
    except Exception:
        pass

# Fetch FotMob schedules only for dates we actually need.
dates = set()
for t in targets.values():
    d = parse_iso(t['start_utc'])
    if d:
        dates.add(d.astimezone(ROME).date())
        dates.add(d.date())

events, source_errors, schedule_stats = [], {}, []
for d in sorted(dates):
    url = f'https://www.fotmob.com/api/data/matches?date={d.strftime("%Y%m%d")}&timezone=Europe%2FRome&ccode3=ITA'
    try:
        j, status = fm_json(url)
        cnt = 0
        for lg in j.get('leagues', []):
            for m in lg.get('matches', []):
                st = (m.get('status') or {}).get('utcTime')
                md = parse_iso(st)
                if not md:
                    raw = m.get('time')
                    try:
                        md = datetime.strptime(raw, '%d.%m.%Y %H:%M').replace(tzinfo=ROME).astimezone(timezone.utc)
                    except Exception:
                        md = None
                events.append({'id':m.get('id'),'home':(m.get('home') or {}).get('name'),'away':(m.get('away') or {}).get('name'),'start':md,'league':lg.get('name')})
                cnt += 1
        schedule_stats.append({'date':str(d),'status':status,'matches':cnt})
    except Exception as e:
        source_errors[f'fotmob_{d}'] = type(e).__name__ + ': ' + str(e)[:220]


def best(t):
    th, ta = split_match(t['match'])
    tdt = parse_iso(t['start_utc'])
    winner = None
    for e in events:
        if not e['home'] or not e['away'] or not e['start']:
            continue
        hs, ass = side_score(th,e['home']), side_score(ta,e['away'])
        mins = abs((e['start']-tdt).total_seconds())/60
        if mins > 180 or hs < .40 or ass < .40:
            continue
        score = .86*((hs+ass)/2)+.14*max(0,1-mins/180)
        if winner is None or score > winner['score']:
            winner={**e,'score':round(score,4),'home_score':round(hs,4),'away_score':round(ass,4),'time_delta_min':round(mins,1)}
    return winner if winner and winner['score'] >= .58 else None

results=[]
for key,t in sorted(targets.items(), key=lambda kv:kv[1]['start_utc']):
    prior = None
    for om in old_by_key.values():
        if str(om.get('match_market_id')) == str(t.get('match_market_id')) and t.get('match_market_id') is not None:
            prior=om; break
    fm=best(t); err=None
    parsed={'present':False,'complete_11v11':False,'confirmed':False,'historical_reference':False,'teams':[]}
    if fm:
        try:
            d,_=fm_json(f'https://www.fotmob.com/api/data/matchDetails?matchId={fm["id"]}')
            parsed=parse_lineup(((d.get('content') or {}).get('lineup') or {}))
        except Exception as e:
            err=type(e).__name__+': '+str(e)[:220]

    retained=False; changed=False; previous_fp=None
    if old_is_valid_official(prior):
        previous_fp=(prior.get('lineup') or {}).get('xi_fingerprint')
        if not parsed.get('confirmed'):
            parsed=prior.get('lineup') or parsed; retained=True
        else:
            changed=bool(previous_fp and parsed.get('xi_fingerprint') and previous_fp != parsed.get('xi_fingerprint'))

    if parsed.get('confirmed'): status='SOURCE_CONFIRMED'
    elif parsed.get('historical_reference'): status='REFERENCE_PREVIOUS_XI'
    elif parsed.get('present'): status='LINEUP_PRESENT_UNCONFIRMED'
    else: status='NOT_AVAILABLE'

    confirmed_at=None
    if status=='SOURCE_CONFIRMED':
        if retained and prior: confirmed_at=prior.get('confirmed_at')
        elif prior and old_is_valid_official(prior) and not changed: confirmed_at=prior.get('confirmed_at') or NOW.isoformat()
        else: confirmed_at=NOW.isoformat()

    results.append({**t,'status':status,'confirmed_at':confirmed_at,'retained_from_previous':retained,'xi_changed_after_confirmation':changed,'previous_xi_fingerprint':previous_fp,'source':'FotMob','fotmob_match':None if not fm else {k:fm.get(k) for k in ('id','home','away','league','score','time_delta_min')},'lineup':parsed,'error':err})
    time.sleep(.08)

counts={}
for r in results: counts[r['status']]=counts.get(r['status'],0)+1
payload={
    'generated_at':NOW.isoformat(),
    'window':'T-120 to T+15 minutes',
    'source_strategy':'Canonical Worker-backed BetFlag fixture index + explicit Radar runtime fixtures + continuity fallbacks; FotMob standard XI certification',
    'target_sources':target_sources,
    'target_count':len(results),
    'status_counts':counts,
    'schedule_stats':schedule_stats,
    'source_errors':source_errors,
    'matches':results,
}
pathlib.Path('feed').mkdir(exist_ok=True)
pathlib.Path('feed/lineups-current.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
summary={k:v for k,v in payload.items() if k!='matches'}
summary['matches']=[{k:r.get(k) for k in ('match','start_time','league','minutes_to_start','status','match_market_id','confirmed_at','xi_changed_after_confirmation','target_origin')} for r in results]
pathlib.Path('feed/lineups-current-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
