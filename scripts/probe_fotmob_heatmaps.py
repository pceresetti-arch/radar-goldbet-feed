#!/usr/bin/env python3
import json, pathlib, urllib.parse
from curl_cffi import requests

ROOT=pathlib.Path('feed')
H={'Accept':'application/json,text/plain,*/*','Accept-Language':'it-IT,it;q=0.9,en;q=0.8','Referer':'https://www.fotmob.com/'}

def get(url):
    return requests.get(url,headers=H,impersonate='chrome',timeout=25)

def short(v,limit=3500):
    s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    return s[:limit]

def heatmap_candidates(x,path='$',out=None):
    out=[] if out is None else out
    if isinstance(x,dict):
        for k,v in x.items():
            p=f'{path}.{k}'
            if 'heatmap' in str(k).lower() or (isinstance(v,str) and 'heatmap' in v.lower()):
                out.append({'path':p,'value':short(v,700)})
            heatmap_candidates(v,p,out)
    elif isinstance(x,list):
        for i,v in enumerate(x): heatmap_candidates(v,f'{path}[{i}]',out)
    return out

def recent_ids_from_team(team_id,limit=3):
    try: payload=get(f'https://www.fotmob.com/api/data/teams?id={team_id}&ccode3=ITA').json()
    except Exception:return []
    found=[]
    def walk(x):
        if isinstance(x,dict):
            mid=x.get('id') or x.get('matchId')
            st=x.get('status') or {}
            finished=bool(st.get('finished')) if isinstance(st,dict) else False
            if mid is not None and finished:
                try: mid=int(mid)
                except Exception: mid=None
                if mid and mid not in found: found.append(mid)
            for v in x.values(): walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(payload)
    return found[:limit]

ctx={}
p=ROOT/'player-matchup-context-current.json'
if p.exists(): ctx=json.loads(p.read_text(encoding='utf-8'))
ids=[]
for m in ctx.get('matches') or []:
    for t in m.get('teams') or []:
        for mid in (t.get('recent_match_ids') or [])[:1]:
            if mid not in ids: ids.append(mid)
# Add high-coverage clubs to test whether heatmaps are provider/competition dependent.
# FotMob IDs: Manchester City 8456, Liverpool 8650, Real Madrid 8633, Bayern 9823.
for tid in (8456,8650,8633,9823):
    for mid in recent_ids_from_team(tid,2):
        if mid not in ids: ids.append(mid)
ids=ids[:12] or [5140001]
rows=[]
for mid in ids:
    rec={'match_id':mid}
    try:
        d=get(f'https://www.fotmob.com/api/data/matchDetails?matchId={mid}').json()
        facts=((d.get('content') or {}).get('matchFacts') or {})
        candidates=heatmap_candidates(d)
        hu=facts.get('heatmapUrl')
        if not hu:
            for c in candidates:
                v=c.get('value') or ''
                if 'http' in v and 'heatmap' in v.lower():
                    try: hu=json.loads(v) if v.startswith('"') else v
                    except Exception: hu=v
                    if isinstance(hu,str): hu=hu.strip('"')
                    break
        rec['matchFacts_keys']=sorted(facts.keys())
        rec['heatmap_candidates']=candidates[:20]
        rec['heatmap_url']=hu
        if not hu:
            rec['status']='NO_HEATMAP_URL'; rows.append(rec); continue
        url='https://www.fotmob.com/api/data/heatmap/match/{}/heatmaps?{}'.format(mid,urllib.parse.urlencode({'heatmapUrl':hu}))
        r=get(url)
        rec['http_status']=r.status_code; rec['content_type']=r.headers.get('content-type')
        try:
            payload=r.json(); rec['payload_type']=type(payload).__name__
            if isinstance(payload,dict): rec['top_keys']=sorted(payload.keys())
            elif isinstance(payload,list): rec['list_length']=len(payload)
            rec['sample']=short(payload); rec['status']='OK_JSON'
        except Exception:
            rec['payload_type']='text'; rec['sample']=r.text[:3500]; rec['status']='OK_TEXT' if r.ok else 'HTTP_ERROR'
    except Exception as e:
        rec['status']='ERROR'; rec['error']=type(e).__name__+': '+str(e)[:300]
    rows.append(rec)
ROOT.mkdir(exist_ok=True)
(ROOT/'fotmob-heatmap-probe.json').write_text(json.dumps({'matches':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'probed':len(rows),'statuses':sorted({r['status'] for r in rows})},ensure_ascii=False))
