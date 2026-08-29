import json, pathlib, re, unicodedata
from datetime import datetime, timezone

FEED=pathlib.Path('feed')
OUT=FEED/'betflag-hot-feed.json'
FIXTURE_DIR=FEED/'betflag-fixtures'
FIXTURE_INDEX=FEED/'betflag-fixtures-index.json'


def norm(v):
    s=unicodedata.normalize('NFD',str(v or ''))
    s=''.join(c for c in s if unicodedata.category(c)!='Mn').lower()
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())


def slug(v):
    s=norm(v).replace(' ','-')
    s=re.sub(r'-+','-',s).strip('-')
    return s[:140] or 'fixture'


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


def slim(r):
    keep=('event_id','match_market_id','match','match_start','market_family','market','line','selection','odd','selection_id','market_id','odds_id','player','betflag_opening_odd','betflag_opening_odd_field')
    return {x:r.get(x) for x in keep if r.get(x) is not None}


def main():
    player=load('betflag-residential-current.json')
    standard=load('betflag-standard-current.json')
    fixtures={}
    for r in standard.get('rows',[]): add(fixtures,r,'standard')
    for r in player.get('rows',[]): add(fixtures,r,'player_props')

    generated_at=datetime.now(timezone.utc).isoformat()
    source_healthy=bool(player.get('source_healthy')) and bool(standard.get('source_healthy'))
    compact={}
    FIXTURE_DIR.mkdir(parents=True,exist_ok=True)

    # Remove only previously materialized JSON files so stale fixtures cannot survive indefinitely.
    for p in FIXTURE_DIR.glob('*.json'):
        try: p.unlink()
        except OSError: pass

    index=[]
    for k,f in fixtures.items():
        fixture={
            'schema_version':'betflag-fixture-feed-v1',
            'generated_at':generated_at,
            'player_source_generated_at':player.get('generated_at'),
            'standard_source_generated_at':standard.get('generated_at'),
            'source_class':'BETFLAG_AAMS_DIRECT',
            'source_healthy':source_healthy,
            'match':f.get('match'),
            'match_start':f.get('match_start'),
            'standard':[slim(r) for r in f['standard']],
            'player_props':[slim(r) for r in f['player_props']],
        }
        compact[k]={x:fixture[x] for x in ('match','match_start','standard','player_props')}
        filename=slug(f.get('match'))+'.json'
        path=FIXTURE_DIR/filename
        path.write_text(json.dumps(fixture,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        index.append({
            'match':f.get('match'),
            'match_start':f.get('match_start'),
            'file':f'feed/betflag-fixtures/{filename}',
            'standard_count':len(fixture['standard']),
            'player_props_count':len(fixture['player_props']),
            'match_market_ids':sorted({str(r.get('match_market_id')) for r in f['standard']+f['player_props'] if r.get('match_market_id') is not None}),
        })

    index.sort(key=lambda x:((x.get('match_start') or ''),(x.get('match') or '')))
    FIXTURE_INDEX.write_text(json.dumps({
        'schema_version':'betflag-fixtures-index-v1',
        'generated_at':generated_at,
        'player_source_generated_at':player.get('generated_at'),
        'standard_source_generated_at':standard.get('generated_at'),
        'source_healthy':source_healthy,
        'fixture_count':len(index),
        'fixtures':index,
    },ensure_ascii=False,separators=(',',':')),encoding='utf-8')

    out={'schema_version':'betflag-hot-feed-v1','generated_at':generated_at,'player_source_generated_at':player.get('generated_at'),'standard_source_generated_at':standard.get('generated_at'),'source_healthy':source_healthy,'fixture_count':len(compact),'fixtures':compact}
    OUT.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'source_healthy':out['source_healthy'],'fixtures':len(compact),'fixture_files':len(index),'bytes':OUT.stat().st_size},ensure_ascii=False))

if __name__=='__main__': main()
