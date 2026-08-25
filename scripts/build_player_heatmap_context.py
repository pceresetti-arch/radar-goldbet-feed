#!/usr/bin/env python3
import concurrent.futures, json, math, pathlib, re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from curl_cffi import requests

ROOT=pathlib.Path('feed'); NOW=datetime.now(timezone.utc)
H={'Accept':'application/json,text/plain,*/*','Accept-Language':'it-IT,it;q=0.9,en;q=0.8','Referer':'https://www.fotmob.com/'}
CIRCLE=re.compile(r'<circle\s+cx="([0-9.]+)"\s+cy="([0-9.]+)"')

def load(name,default):
    p=ROOT/name
    try:return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    except Exception:return default

def get(url):
    r=requests.get(url,headers=H,impersonate='chrome',timeout=25);r.raise_for_status();return r.json()
def points(payload):
    out={};p=(payload or {}).get('players') or {}
    if not isinstance(p,dict):return out
    for k,s in p.items():
        if not isinstance(s,str):continue
        opta=str(k)[1:] if str(k).startswith('p') else str(k);arr=[]
        for x,y in CIRCLE.findall(s):
            try:arr.append((float(x),float(y)))
            except:pass
        if arr:out[opta]=arr
    return out
def player_bridge(detail):
    """Heatmap SVG keys are Opta IDs; matchDetails playerStats exposes FotMob id + optaId."""
    out=defaultdict(list); stats=((detail.get('content') or {}).get('playerStats') or {}) if isinstance(detail,dict) else {}
    if not isinstance(stats,dict):return out
    for key,p in stats.items():
        if not isinstance(p,dict):continue
        fid=p.get('id') if p.get('id') is not None else key; opta=p.get('optaId'); tid=p.get('teamId')
        if fid is None or opta in (None,'') or tid is None:continue
        try:pos=int(p.get('positionId')) if p.get('positionId') is not None else None
        except:pos=None
        out[str(tid)].append({'player_id':str(fid),'opta_id':str(opta),'name':p.get('name'),'position_id':pos,'is_goalkeeper':bool(p.get('isGoalkeeper'))})
    return out
def pmean(arr):return sum(x for x,_ in arr)/len(arr) if arr else None
def orient(plist,raw):
    gk=[]
    for p in plist:
        if p.get('is_goalkeeper') or p.get('position_id')==11:gk.extend(raw.get(p['opta_id'],[]))
    if len(gk)>=2:
        gx=pmean(gk);return (gx>52.5,'GK_HEATMAP',round(gx,3))
    defenders=[];attackers=[]
    for p in plist:
        arr=raw.get(p['opta_id']) or [];pos=p.get('position_id')
        if not arr or pos is None:continue
        if 25<=pos<60:defenders.append(pmean(arr))
        elif pos>=80:attackers.append(pmean(arr))
    if defenders and attackers:
        d=sum(defenders)/len(defenders);a=sum(attackers)/len(attackers)
        if abs(a-d)>=3:return (a<d,'ROLE_DEPTH_ORDER',round(a-d,3))
    return (None,'UNRESOLVED',None)
def zone(x,y):
    dep='DEFENSIVE' if x<1/3 else ('ATTACKING' if x>2/3 else 'MIDFIELD')
    lane='LEFT' if y<1/3 else ('RIGHT' if y>2/3 else 'CENTER')
    return f'{dep}_{lane}'
def summarize(arr,flip):
    pts=[]
    for x,y in arr:
        x/=105;y/=68
        if flip:x=1-x;y=1-y
        pts.append((x,y))
    n=len(pts);sx=sum(x for x,_ in pts);sy=sum(y for _,y in pts);sx2=sum(x*x for x,_ in pts);sy2=sum(y*y for _,y in pts)
    mx=sx/n;my=sy/n;disp=math.sqrt(max(0,sx2/n-mx*mx)+max(0,sy2/n-my*my));zs=Counter(zone(x,y) for x,y in pts)
    return {'n':n,'sx':sx,'sy':sy,'sx2':sx2,'sy2':sy2,'zones':dict(zs),'final':sum(x>=2/3 for x,_ in pts),'box':sum(x>=88/105 and 13.84/68<=y<=54.16/68 for x,y in pts),'central':sum(1/3<=y<=2/3 for _,y in pts),'centroid_x':mx,'centroid_y':my,'dispersion':disp}
def fetch(mid):
    rec={'match_id':str(mid)}
    try:
        d=get(f'https://www.fotmob.com/api/data/matchDetails?matchId={mid}');hu=(d.get('content') or {}).get('heatmapUrl');rec['has_url']=bool(hu)
        if not hu:return rec
        hp=get('https://www.fotmob.com'+hu if str(hu).startswith('/') else str(hu));raw=points(hp);rec['raw_heatmap_player_count']=len(raw)
        bridge=player_bridge(d);summ={};oris={};mapped=0
        for tid,plist in bridge.items():
            matching=sum(1 for p in plist if p['opta_id'] in raw);mapped+=matching
            flip,method,signal=orient(plist,raw);oris[tid]={'method':method,'flip_180':flip,'signal':signal,'bridge_players':len(plist),'heatmap_mapped_players':matching}
            if flip is None:continue
            for p in plist:
                arr=raw.get(p['opta_id']) or []
                if arr:
                    summ[p['player_id']]={**summarize(arr,flip),'opta_id':p['opta_id'],'mapping_source':'matchDetails.content.playerStats.optaId'}
        rec['bridge_mapped_player_count']=mapped;rec['orientation']=oris;rec['players']=summ
        rec['status']='OK' if summ else ('BRIDGE_OK_ORIENTATION_UNRESOLVED' if mapped else 'NO_OPTA_BRIDGE_OVERLAP')
    except Exception as e:rec['status']='ERROR';rec['error']=type(e).__name__+': '+str(e)[:180]
    return rec

def aggregate(pid,hist):
    hs=[];offered=0;mapped_matches=0
    for h in hist:
        if h.get('has_url'):offered+=1
        if h.get('bridge_mapped_player_count'):mapped_matches+=1
        s=(h.get('players') or {}).get(str(pid))
        if s:hs.append(s)
    n=sum(h['n'] for h in hs);zones=Counter()
    for h in hs:zones.update(h['zones'])
    if not n:return {'heatmap_status':'NOT_AVAILABLE_OR_UNORIENTED','heatmap_offered_matches':offered,'heatmap_bridge_matches':mapped_matches,'heatmap_sample_matches':0}
    sx=sum(h['sx'] for h in hs);sy=sum(h['sy'] for h in hs);sx2=sum(h['sx2'] for h in hs);sy2=sum(h['sy2'] for h in hs);mx=sx/n;my=sy/n
    disp=math.sqrt(max(0,sx2/n-mx*mx)+max(0,sy2/n-my*my))
    return {'heatmap_status':'AVAILABLE','heatmap_offered_matches':offered,'heatmap_bridge_matches':mapped_matches,'heatmap_sample_matches':len(hs),'heatmap_location_samples':n,'heatmap_centroid_x':round(mx,4),'heatmap_centroid_y':round(my,4),'heatmap_dispersion':round(disp,4),'heatmap_dominant_zone':zones.most_common(1)[0][0] if zones else None,'heatmap_final_third_share':round(sum(h['final'] for h in hs)/n,4),'heatmap_box_share':round(sum(h['box'] for h in hs)/n,4),'heatmap_central_share':round(sum(h['central'] for h in hs)/n,4),'heatmap_model_status':'REAL_PROVIDER_LOCATION_DENSITY_OPTA_MAPPED_NOT_GPS_NOT_CALIBRATED'}

ctx=load('player-matchup-context-current.json',{'matches':[]});mids=[];seen=set()
for m in ctx.get('matches') or []:
    for t in m.get('teams') or []:
        for mid in t.get('recent_match_ids') or []:
            if str(mid) not in seen:seen.add(str(mid));mids.append(mid)
history={}
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
    for r in ex.map(fetch,mids):history[str(r['match_id'])]=r
out=[]
for m in ctx.get('matches') or []:
    ts=[]
    for t in m.get('teams') or []:
        hist=[history[str(x)] for x in (t.get('recent_match_ids') or []) if str(x) in history];ps=[]
        for p in t.get('players') or []:ps.append({'player_id':p.get('player_id'),'player':p.get('player'),**aggregate(p.get('player_id'),hist)})
        ts.append({'team_id':t.get('team_id'),'team':t.get('team'),'historical_matches':len(hist),'heatmap_offered_matches':sum(bool(x.get('has_url')) for x in hist),'heatmap_bridge_matches':sum(bool(x.get('bridge_mapped_player_count')) for x in hist),'players':ps})
    out.append({'match_market_id':m.get('match_market_id'),'match_event_id':m.get('match_event_id'),'match':m.get('match'),'start_time':m.get('start_time'),'minutes_to_start':m.get('minutes_to_start'),'xi_fingerprint':m.get('xi_fingerprint'),'teams':ts})
payload={'generated_at':NOW.isoformat(),'source_player_context_generated_at':ctx.get('generated_at'),'method':'FotMob heatmap location-density circles on 105x68 pitch; heatmap Opta IDs mapped to FotMob player IDs via matchDetails.content.playerStats.optaId; orientation by goalkeeper heatmap then defender-vs-attacker depth order','policy':'Context only. Not GPS, not touches, not independent betting edge until prospective OOS validation. Missing/unresolved heatmaps fall back to starting-position and shot-origin context.','match_count':len(out),'historical_matches_fetched':len(history),'historical_heatmaps_offered':sum(bool(h.get('has_url')) for h in history.values()),'historical_heatmaps_with_id_bridge':sum(bool(h.get('bridge_mapped_player_count')) for h in history.values()),'matches':out}
ROOT.mkdir(exist_ok=True);(ROOT/'player-heatmap-context-current.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
summary={k:v for k,v in payload.items() if k!='matches'};summary['matches']=[{'match':m['match'],'teams':[{'team':t['team'],'offered':t['heatmap_offered_matches'],'bridge_matches':t['heatmap_bridge_matches'],'players_available':sum(p.get('heatmap_status')=='AVAILABLE' for p in t['players'])} for t in m['teams']]} for m in out]
(ROOT/'player-heatmap-context-current-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
