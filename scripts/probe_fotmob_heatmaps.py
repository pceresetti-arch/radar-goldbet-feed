#!/usr/bin/env python3
import json, pathlib
from curl_cffi import requests

ROOT=pathlib.Path('feed')
H={'Accept':'application/json,text/plain,*/*','Accept-Language':'it-IT,it;q=0.9,en;q=0.8','Referer':'https://www.fotmob.com/'}
def get(url): return requests.get(url,headers=H,impersonate='chrome',timeout=25)
def short(v,limit=1800):
    s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    return s[:limit]
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
def lineup_ids(detail):
    out=[];line=((detail.get('content') or {}).get('lineup') or {})
    for t in (line.get('homeTeam'),line.get('awayTeam')):
        if not isinstance(t,dict):continue
        for key in ('starters','subs'):
            for p in t.get(key) or []:
                if isinstance(p,dict) and p.get('id') is not None:
                    out.append({'id':str(p.get('id')),'name':p.get('name'),'team':t.get('name'),'positionId':p.get('positionId')})
    return out

ctx={}; p=ROOT/'player-matchup-context-current.json'
if p.exists():ctx=json.loads(p.read_text(encoding='utf-8'))
ids=[]
for m in ctx.get('matches') or []:
    for t in m.get('teams') or []:
        for mid in (t.get('recent_match_ids') or [])[:2]:
            if mid not in ids:ids.append(mid)
for tid in (8456,8650,8633,9823):
    for mid in recent(tid):
        if mid not in ids:ids.append(mid)
rows=[]
for mid in ids[:14] or [5140001]:
    rec={'match_id':mid}
    try:
        d=get(f'https://www.fotmob.com/api/data/matchDetails?matchId={mid}').json(); hu=(d.get('content') or {}).get('heatmapUrl')
        lu=lineup_ids(d); rec['lineup_player_count']=len(lu);rec['lineup_sample']=lu[:8]
        if not hu:rec['status']='NO_HEATMAP_URL';rows.append(rec);continue
        url='https://www.fotmob.com'+hu if str(hu).startswith('/') else str(hu);payload=get(url).json();pls=payload.get('players') or {}
        hids=[str(k)[1:] if str(k).startswith('p') else str(k) for k in pls.keys()] if isinstance(pls,dict) else []
        lids=[x['id'] for x in lu];overlap=sorted(set(hids)&set(lids))
        rec['heatmap_player_count']=len(hids);rec['heatmap_ids_sample']=hids[:10];rec['id_overlap_count']=len(overlap);rec['id_overlap_sample']=overlap[:10]
        rec['lineup_ids_missing_in_heatmap_sample']=[x for x in lu if x['id'] not in set(hids)][:10]
        rec['status']='MAPPING_OK' if overlap else 'NO_ID_OVERLAP'
    except Exception as e:rec['status']='ERROR';rec['error']=type(e).__name__+': '+str(e)[:300]
    rows.append(rec)
ROOT.mkdir(exist_ok=True);(ROOT/'fotmob-heatmap-probe.json').write_text(json.dumps({'matches':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'probed':len(rows),'mapping_ok':sum(r.get('status')=='MAPPING_OK' for r in rows),'no_overlap':sum(r.get('status')=='NO_ID_OVERLAP' for r in rows)},ensure_ascii=False))
