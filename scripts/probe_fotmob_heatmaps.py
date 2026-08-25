#!/usr/bin/env python3
import json, pathlib, urllib.parse
from curl_cffi import requests

ROOT=pathlib.Path('feed')
H={'Accept':'application/json,text/plain,*/*','Accept-Language':'it-IT,it;q=0.9,en;q=0.8','Referer':'https://www.fotmob.com/'}

def get(url):
    return requests.get(url,headers=H,impersonate='chrome',timeout=25)

def short(v,limit=3000):
    s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    return s[:limit]

ctx={}
p=ROOT/'player-matchup-context-current.json'
if p.exists():
    ctx=json.loads(p.read_text(encoding='utf-8'))
ids=[]
for m in ctx.get('matches') or []:
    for t in m.get('teams') or []:
        for mid in (t.get('recent_match_ids') or [])[:2]:
            if mid not in ids: ids.append(mid)
        for mid in (t.get('opponent_recent_match_ids') or [])[:1]:
            if mid not in ids: ids.append(mid)
ids=ids[:5] or [5140001]
rows=[]
for mid in ids:
    rec={'match_id':mid}
    try:
        d=get(f'https://www.fotmob.com/api/data/matchDetails?matchId={mid}').json()
        facts=((d.get('content') or {}).get('matchFacts') or {})
        hu=facts.get('heatmapUrl')
        rec['matchFacts_keys']=sorted(facts.keys())
        rec['heatmap_url']=hu
        if not hu:
            rec['status']='NO_HEATMAP_URL'; rows.append(rec); continue
        url='https://www.fotmob.com/api/data/heatmap/match/{}/heatmaps?{}'.format(mid,urllib.parse.urlencode({'heatmapUrl':hu}))
        r=get(url)
        rec['http_status']=r.status_code
        rec['content_type']=r.headers.get('content-type')
        try:
            payload=r.json()
            rec['payload_type']=type(payload).__name__
            if isinstance(payload,dict): rec['top_keys']=sorted(payload.keys())
            elif isinstance(payload,list): rec['list_length']=len(payload)
            rec['sample']=short(payload)
            rec['status']='OK_JSON'
        except Exception:
            rec['payload_type']='text'
            rec['sample']=r.text[:3000]
            rec['status']='OK_TEXT' if r.ok else 'HTTP_ERROR'
    except Exception as e:
        rec['status']='ERROR'; rec['error']=type(e).__name__+': '+str(e)[:300]
    rows.append(rec)
ROOT.mkdir(exist_ok=True)
(ROOT/'fotmob-heatmap-probe.json').write_text(json.dumps({'matches':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'probed':len(rows),'statuses':{r['status'] for r in rows}},ensure_ascii=False))
