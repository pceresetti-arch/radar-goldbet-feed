import json, pathlib, re, unicodedata
from datetime import datetime, timezone

FEED=pathlib.Path('feed')
OUT=FEED/'betflag-hot-feed.json'


def norm(v):
    s=unicodedata.normalize('NFD',str(v or ''))
    s=''.join(c for c in s if unicodedata.category(c)!='Mn').lower()
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())


def load(name):
    p=FEED/name
    if not p.exists(): return {}
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return {}


def add(fixtures,row,kind):
    match=row.get('match') or row.get('event') or row.get('event_name')
    if not match: return
    key=norm(match)
    f=fixtures.setdefault(key,{'match':match,'match_start':row.get('match_start'),'standard':[],'player_props':[]})
    if not f.get('match_start') and row.get('match_start'): f['match_start']=row.get('match_start')
    f[kind].append(row)


def main():
    player=load('betflag-residential-current.json')
    standard=load('betflag-standard-current.json')
    fixtures={}
    for r in standard.get('rows',[]): add(fixtures,r,'standard')
    for r in player.get('rows',[]): add(fixtures,r,'player_props')
    compact={}
    for k,f in fixtures.items():
        # Keep only fields needed by Radar; this avoids multi-MB reads.
        def slim(r):
            keep=('event_id','match_market_id','match','match_start','market_family','market','line','selection','odd','selection_id','market_id','odds_id','player','betflag_opening_odd','betflag_opening_odd_field')
            return {x:r.get(x) for x in keep if r.get(x) is not None}
        compact[k]={**{x:f.get(x) for x in ('match','match_start')},'standard':[slim(r) for r in f['standard']],'player_props':[slim(r) for r in f['player_props']]}
    out={'schema_version':'betflag-hot-feed-v1','generated_at':datetime.now(timezone.utc).isoformat(),'player_source_generated_at':player.get('generated_at'),'standard_source_generated_at':standard.get('generated_at'),'source_healthy':bool(player.get('source_healthy')) and bool(standard.get('source_healthy')),'fixture_count':len(compact),'fixtures':compact}
    OUT.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'source_healthy':out['source_healthy'],'fixtures':len(compact),'bytes':OUT.stat().st_size},ensure_ascii=False))

if __name__=='__main__': main()
