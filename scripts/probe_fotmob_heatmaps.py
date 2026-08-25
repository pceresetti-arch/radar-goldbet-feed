#!/usr/bin/env python3
import json, pathlib
from curl_cffi import requests

ROOT=pathlib.Path('feed')
H={'Accept':'application/json,text/plain,*/*','Accept-Language':'it-IT,it;q=0.9,en;q=0.8','Referer':'https://www.fotmob.com/'}
def get(url): return requests.get(url,headers=H,impersonate='chrome',timeout=25)
def compact(v,limit=1200):
    try:s=json.dumps(v,ensure_ascii=False,default=str)
    except:s=str(v)
    return s[:limit]
def lineup_players(detail):
    out=[];line=((detail.get('content') or {}).get('lineup') or {})
    for side,t in (('home',line.get('homeTeam')),('away',line.get('awayTeam'))):
        if not isinstance(t,dict):continue
        for key in ('starters','subs'):
            for p in t.get(key) or []:
                if isinstance(p,dict):out.append({'side':side,'team':t.get('name'),'slot':key,'id':str(p.get('id')) if p.get('id') is not None else None,'name':p.get('name'),'keys':sorted(p.keys()),'raw':p})
    return out
def find_values(x,targets,path='$',hits=None):
    hits=[] if hits is None else hits
    if isinstance(x,dict):
        # Record enclosing dict when any scalar equals one target.
        matched=[]
        for k,v in x.items():
            if isinstance(v,(str,int,float)) and str(v) in targets:matched.append((k,str(v)))
        if matched:hits.append({'path':path,'matched':matched,'dict_keys':sorted(x.keys()),'dict_sample':compact(x,1800)})
        for k,v in x.items():find_values(v,targets,f'{path}.{k}',hits)
    elif isinstance(x,list):
        for i,v in enumerate(x):find_values(v,targets,f'{path}[{i}]',hits)
    return hits

# Diagnose known heatmap-rich historical matches from current context, then a major-league fallback.
ctx={};p=ROOT/'player-matchup-context-current.json'
if p.exists():ctx=json.loads(p.read_text(encoding='utf-8'))
ids=[]
for m in ctx.get('matches') or []:
    for t in m.get('teams') or []:
        for mid in (t.get('recent_match_ids') or [])[:2]:
            if mid not in ids:ids.append(mid)
ids=ids[:8] or [5140001]
rows=[]
for mid in ids:
    rec={'match_id':mid}
    try:
        d=get(f'https://www.fotmob.com/api/data/matchDetails?matchId={mid}').json();hu=(d.get('content') or {}).get('heatmapUrl');lu=lineup_players(d)
        rec['lineup_count']=len(lu);rec['lineup_raw_sample']=[{k:p.get(k) for k in ('side','team','slot','id','name','keys','raw')} for p in lu[:3]]
        if not hu:rec['status']='NO_HEATMAP_URL';rows.append(rec);continue
        hp=get('https://www.fotmob.com'+hu if str(hu).startswith('/') else str(hu)).json();pls=hp.get('players') or {}
        hids=[str(k)[1:] if str(k).startswith('p') else str(k) for k in pls.keys()] if isinstance(pls,dict) else []
        rec['heatmap_ids_sample']=hids[:12];rec['heatmap_count']=len(hids)
        rec['alternate_id_hits']=find_values(d,set(hids[:12]))[:40]
        # Search all player-name occurrences to reveal sibling alternate ID fields.
        name_targets={p.get('name') for p in lu[:12] if p.get('name')}
        name_hits=[]
        def find_names(x,path='$'):
            if isinstance(x,dict):
                vals=[str(v) for v in x.values() if isinstance(v,(str,int,float))]
                if any(n in vals for n in name_targets):name_hits.append({'path':path,'dict_keys':sorted(x.keys()),'dict_sample':compact(x,2000)})
                for k,v in x.items():find_names(v,f'{path}.{k}')
            elif isinstance(x,list):
                for i,v in enumerate(x):find_names(v,f'{path}[{i}]')
        find_names(d);rec['name_context_hits']=name_hits[:40]
        rec['status']='BRIDGE_FOUND' if rec['alternate_id_hits'] else 'NO_ALT_ID_IN_MATCHDETAILS'
    except Exception as e:rec['status']='ERROR';rec['error']=type(e).__name__+': '+str(e)[:300]
    rows.append(rec)
ROOT.mkdir(exist_ok=True);(ROOT/'fotmob-heatmap-probe.json').write_text(json.dumps({'matches':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'probed':len(rows),'bridge_found':sum(r.get('status')=='BRIDGE_FOUND' for r in rows),'no_bridge':sum(r.get('status')=='NO_ALT_ID_IN_MATCHDETAILS' for r in rows)},ensure_ascii=False))
