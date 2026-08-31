import json, pathlib, re, unicodedata
from datetime import datetime, timezone

FEED=pathlib.Path('feed')
OUT=FEED/'betflag-residential-hot-feed.json'
STATUS=FEED/'betflag-live-status.json'
FIXTURE_DIR=FEED/'betflag-residential-fixtures'
FIXTURE_INDEX=FEED/'betflag-residential-fixtures-index.json'
ALIAS_FIXTURE_DIR=FEED/'betflag-fixtures'
ALIAS_FIXTURE_INDEX=FEED/'betflag-fixtures-index.json'


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
    keep=('event_id','match_market_id','match','match_start','market_family','family','market_scope','market','line','selection','odd','selection_id','market_id','odds_id','player','player_event','betflag_opening_odd','betflag_opening_odd_field')
    return {x:r.get(x) for x in keep if r.get(x) is not None}


def clear_json_dir(path):
    path.mkdir(parents=True,exist_ok=True)
    for p in path.glob('*.json'):
        try: p.unlink()
        except OSError: pass


def main():
    player=load('betflag-residential-current.json')
    standard=load('betflag-standard-current.json')
    fixtures={}
    for r in standard.get('rows',[]): add(fixtures,r,'standard')
    for r in player.get('rows',[]): add(fixtures,r,'player_props')

    generated_at=datetime.now(timezone.utc).isoformat()
    source_healthy=bool(player.get('source_healthy')) and bool(standard.get('source_healthy'))
    compact={}
    clear_json_dir(FIXTURE_DIR)
    clear_json_dir(ALIAS_FIXTURE_DIR)

    index=[]
    alias_index=[]
    for k,f in fixtures.items():
        mids=sorted({str(r.get('match_market_id')) for r in f['standard']+f['player_props'] if r.get('match_market_id') is not None})
        identity_consistent=len(mids)<=1
        fixture={
            'schema_version':'betflag-residential-fixture-v2',
            'generated_at':generated_at,
            'player_source_generated_at':player.get('generated_at'),
            'standard_source_generated_at':standard.get('generated_at'),
            'source_class':'BETFLAG_AAMS_DIRECT',
            'source':'sportservice.betflag.it via residential self-hosted runner',
            'source_healthy':source_healthy,
            'identity_consistent':identity_consistent,
            'price_gate_fixture_eligible':bool(source_healthy and identity_consistent),
            'match':f.get('match'),
            'match_start':f.get('match_start'),
            'match_market_ids':mids,
            'standard':[slim(r) for r in f['standard']],
            'player_props':[slim(r) for r in f['player_props']],
        }
        compact[k]={x:fixture[x] for x in ('match','match_start','match_market_ids','identity_consistent','price_gate_fixture_eligible','standard','player_props')}
        filename=slug(f.get('match'))+'.json'
        payload=json.dumps(fixture,ensure_ascii=False,separators=(',',':'))
        (FIXTURE_DIR/filename).write_text(payload,encoding='utf-8')
        (ALIAS_FIXTURE_DIR/filename).write_text(payload,encoding='utf-8')
        base={
            'match':f.get('match'),
            'match_start':f.get('match_start'),
            'standard_count':len(fixture['standard']),
            'player_props_count':len(fixture['player_props']),
            'match_market_ids':mids,
            'identity_consistent':identity_consistent,
            'price_gate_fixture_eligible':fixture['price_gate_fixture_eligible'],
        }
        index.append({**base,'file':f'feed/betflag-residential-fixtures/{filename}'})
        alias_index.append({**base,'file':f'feed/betflag-fixtures/{filename}'})

    index.sort(key=lambda x:((x.get('match_start') or ''),(x.get('match') or '')))
    alias_index.sort(key=lambda x:((x.get('match_start') or ''),(x.get('match') or '')))
    gate_eligible=sum(1 for x in index if x['price_gate_fixture_eligible'])
    common={
        'schema_version':'betflag-residential-fixtures-index-v2',
        'generated_at':generated_at,
        'player_source_generated_at':player.get('generated_at'),
        'standard_source_generated_at':standard.get('generated_at'),
        'source_class':'BETFLAG_AAMS_DIRECT',
        'source_healthy':source_healthy,
        'fixture_count':len(index),
        'gate_eligible_fixture_count':gate_eligible,
    }
    FIXTURE_INDEX.write_text(json.dumps({**common,'fixtures':index},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    ALIAS_FIXTURE_INDEX.write_text(json.dumps({**common,'compatibility_alias':True,'canonical_index':'feed/betflag-residential-fixtures-index.json','fixtures':alias_index},ensure_ascii=False,separators=(',',':')),encoding='utf-8')

    out={'schema_version':'betflag-residential-hot-feed-v2','generated_at':generated_at,'player_source_generated_at':player.get('generated_at'),'standard_source_generated_at':standard.get('generated_at'),'source_class':'BETFLAG_AAMS_DIRECT','source_healthy':source_healthy,'fixture_count':len(compact),'fixtures':compact}
    OUT.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')

    status={
        'schema_version':'betflag-live-status-v1',
        'generated_at':generated_at,
        'source_class':'BETFLAG_AAMS_DIRECT',
        'source_healthy':source_healthy,
        'player_source_healthy':bool(player.get('source_healthy')),
        'standard_source_healthy':bool(standard.get('source_healthy')),
        'player_source_generated_at':player.get('generated_at'),
        'standard_source_generated_at':standard.get('generated_at'),
        'player_rows':len(player.get('rows') or []),
        'standard_rows':len(standard.get('rows') or []),
        'fixture_count':len(index),
        'gate_eligible_fixture_count':gate_eligible,
        'player_transport':player.get('transport'),
        'standard_transport':standard.get('transport'),
        'read_contract':{
            'branch':'betflag-live',
            'fixture_index':'feed/betflag-residential-fixtures-index.json',
            'fixture_dir':'feed/betflag-residential-fixtures/',
            'compatibility_index':'feed/betflag-fixtures-index.json',
            'compatibility_fixture_dir':'feed/betflag-fixtures/'
        },
    }
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'source_healthy':source_healthy,'fixtures':len(compact),'fixture_files':len(index),'gate_eligible':gate_eligible,'player_rows':status['player_rows'],'standard_rows':status['standard_rows'],'bytes':OUT.stat().st_size,'compatibility_alias':True},ensure_ascii=False))

if __name__=='__main__': main()
