#!/usr/bin/env python3
import json, pathlib
from curl_cffi import requests

ROOT=pathlib.Path('feed')
H={'Accept':'application/json,text/plain,*/*','Accept-Language':'it-IT,it;q=0.9,en;q=0.8','Referer':'https://www.fotmob.com/'}

def get(url): return requests.get(url,headers=H,impersonate='chrome',timeout=25)
def short(v,limit=1800):
    s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    return s[:limit]
def candidates(x,path='$',out=None):
    out=[] if out is None else out
    if isinstance(x,dict):
        for k,v in x.items():
            p=f'{path}.{k}'
            if 'heatmap' in str(k).lower() or (isinstance(v,str) and 'heatmap' in v.lower()): out.append({'path':p,'value':short(v,700)})
            candidates(v,p,out)
    elif isinstance(x,list):
        for i,v in enumerate(x): candidates(v,f'{path}[{i}]',out)
    return out
def recent(team_id,limit=2):
    try:d=get(f'https://www.fotmob.com/api/data/teams?id={team_id}&ccode3=ITA').json()
    except Exception:return []
    out=[]
    def walk(x):
        if isinstance(x,dict):
            mid=x.get('id') or x.get('matchId'); st=x.get('status') or {}; fin=bool(st.get('finished')) if isinstance(st,dict) else False
            if mid is not None and fin:
                try:mid=int(mid)
                except:mid=None
                if mid and mid not in out:out.append(mid)
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(d);return out[:limit]

ctx={}; p=ROOT/'player-matchup-context-current.json'
if p.exists():ctx=json.loads(p.read_text(encoding='utf-8'))
ids=[]
for m in ctx.get('matches') or []:
    for t in m.get('teams') or []:
        for mid in (t.get('recent_match_ids') or [])[:1]:
            if mid not in ids:ids.append(mid)
for tid in (8456,8650,8633,9823):
    for mid in recent(tid):
        if mid not in ids:ids.append(mid)
rows=[]
for mid in ids[:12] or [5140001]:
    rec={'match_id':mid}
    try:
        d=get(f'https://www.fotmob.com/api/data/matchDetails?matchId={mid}').json(); cs=candidates(d)
        hu=(d.get('content') or {}).get('heatmapUrl')
        if not hu:
            for c in cs:
                if '/api/data/heatmap/' in (c.get('value') or ''):hu=(c.get('value') or '').strip('"');break
        rec['heatmap_url']=hu;rec['heatmap_candidates']=cs[:10]
        if not hu:rec['status']='NO_HEATMAP_URL';rows.append(rec);continue
        url='https://www.fotmob.com'+hu if str(hu).startswith('/') else str(hu)
        r=get(url);payload=r.json();rec['http_status']=r.status_code;rec['top_keys']=sorted(payload.keys()) if isinstance(payload,dict) else []
        pls=payload.get('players') if isinstance(payload,dict) else None
        rec['players_type']=type(pls).__name__
        if isinstance(pls,dict):
            rec['player_count']=len(pls); rec['player_keys_sample']=list(pls.keys())[:5]
            rec['players_sample']={str(k):v for k,v in list(pls.items())[:2]}
        elif isinstance(pls,list):
            rec['player_count']=len(pls);rec['players_sample']=pls[:2]
        rec['players_sample_text']=short(rec.get('players_sample'),5000)
        rec['status']='OK_JSON' if r.ok else 'HTTP_JSON_ERROR'
    except Exception as e:rec['status']='ERROR';rec['error']=type(e).__name__+': '+str(e)[:300]
    rows.append(rec)
ROOT.mkdir(exist_ok=True);(ROOT/'fotmob-heatmap-probe.json').write_text(json.dumps({'matches':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'probed':len(rows),'statuses':sorted({r['status'] for r in rows}),'with_players':sum(bool(r.get('player_count')) for r in rows)},ensure_ascii=False))
