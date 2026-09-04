import json, pathlib, re, unicodedata
from collections import Counter
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
    return re.sub(r'-+','-',s).strip('-')[:140] or 'fixture'


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
        try:p.unlink()
        except OSError:pass


def family_counts(rows):
    c=Counter()
    for r in rows:
        name=r.get('market_family') or r.get('family') or r.get('market') or 'UNKNOWN'
        c[str(name)]+=1
    return dict(sorted(c.items()))


def main():
    player=load('betflag-residential-current.json')
    standard=load('betflag-standard-current.json')
    standard_lane_healthy=bool(standard.get('source_healthy'))
    player_lane_healthy=bool(player.get('source_healthy'))
    combined_healthy=standard_lane_healthy and player_lane_healthy

    fixtures={}
    for r in standard.get('rows',[]): add(fixtures,r,'standard')
    for r in player.get('rows',[]): add(fixtures,r,'player_props')

    generated_at=datetime.now(timezone.utc).isoformat()
    compact={}
    clear_json_dir(FIXTURE_DIR); clear_json_dir(ALIAS_FIXTURE_DIR)
    index=[]; alias_index=[]

    for k,f in fixtures.items():
        standard_rows=[slim(r) for r in f['standard']]
        player_rows=[slim(r) for r in f['player_props']]
        mids=sorted({str(r.get('match_market_id')) for r in f['standard']+f['player_props'] if r.get('match_market_id') not in (None,'')})
        identity_consistent=len(mids)<=1
        standard_ready=bool(standard_lane_healthy and identity_consistent and standard_rows)
        player_ready=bool(player_lane_healthy and identity_consistent and player_rows)
        completeness='COMPLETE' if standard_ready and player_ready else ('STANDARD_ONLY' if standard_ready else ('PLAYER_ONLY' if player_ready else 'MISSING'))
        fixture={
            'schema_version':'betflag-residential-fixture-v3',
            'generated_at':generated_at,
            'player_source_generated_at':player.get('generated_at'),
            'standard_source_generated_at':standard.get('generated_at'),
            'source_class':'BETFLAG_AAMS_DIRECT',
            'source':'sportservice.betflag.it via residential self-hosted runner',
            'source_healthy':combined_healthy,
            'standard_lane_healthy':standard_lane_healthy,
            'player_lane_healthy':player_lane_healthy,
            'identity_consistent':identity_consistent,
            'price_gate_fixture_eligible':standard_ready,
            'player_price_gate_fixture_eligible':player_ready,
            'market_completeness':completeness,
            'match':f.get('match'),'match_start':f.get('match_start'),'match_market_ids':mids,
            'standard_market_families':family_counts(standard_rows),
            'player_market_families':family_counts(player_rows),
            'standard':standard_rows,'player_props':player_rows,
        }
        filename=slug(f.get('match'))+'.json'
        payload=json.dumps(fixture,ensure_ascii=False,separators=(',',':'))
        (FIXTURE_DIR/filename).write_text(payload,encoding='utf-8')
        (ALIAS_FIXTURE_DIR/filename).write_text(payload,encoding='utf-8')
        base={
            'match':f.get('match'),'match_start':f.get('match_start'),
            'standard_count':len(standard_rows),'player_props_count':len(player_rows),
            'match_market_ids':mids,'identity_consistent':identity_consistent,
            'price_gate_fixture_eligible':standard_ready,
            'player_price_gate_fixture_eligible':player_ready,
            'market_completeness':completeness,
            'standard_market_families':fixture['standard_market_families'],
            'player_market_families':fixture['player_market_families'],
        }
        index.append({**base,'file':f'feed/betflag-residential-fixtures/{filename}'})
        alias_index.append({**base,'file':f'feed/betflag-fixtures/{filename}'})
        compact[k]={**base,'standard':standard_rows,'player_props':player_rows}

    index.sort(key=lambda x:((x.get('match_start') or ''),(x.get('match') or '')))
    alias_index.sort(key=lambda x:((x.get('match_start') or ''),(x.get('match') or '')))
    standard_gate=sum(1 for x in index if x['price_gate_fixture_eligible'])
    player_gate=sum(1 for x in index if x['player_price_gate_fixture_eligible'])
    complete=sum(1 for x in index if x['market_completeness']=='COMPLETE')
    common={
        'schema_version':'betflag-residential-fixtures-index-v3','generated_at':generated_at,
        'player_source_generated_at':player.get('generated_at'),'standard_source_generated_at':standard.get('generated_at'),
        'source_class':'BETFLAG_AAMS_DIRECT','source_healthy':combined_healthy,
        'standard_lane_healthy':standard_lane_healthy,'player_lane_healthy':player_lane_healthy,
        'fixture_count':len(index),'gate_eligible_fixture_count':standard_gate,
        'player_gate_eligible_fixture_count':player_gate,'complete_fixture_count':complete,
    }
    FIXTURE_INDEX.write_text(json.dumps({**common,'fixtures':index},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    ALIAS_FIXTURE_INDEX.write_text(json.dumps({**common,'compatibility_alias':True,'canonical_index':'feed/betflag-residential-fixtures-index.json','fixtures':alias_index},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    OUT.write_text(json.dumps({**common,'schema_version':'betflag-residential-hot-feed-v3','fixtures':compact},ensure_ascii=False,separators=(',',':')),encoding='utf-8')

    status={
        'schema_version':'betflag-live-status-v2','generated_at':generated_at,'source_class':'BETFLAG_AAMS_DIRECT',
        'source_healthy':combined_healthy,'standard_source_healthy':standard_lane_healthy,'player_source_healthy':player_lane_healthy,
        'standard_price_lane_usable':standard_lane_healthy,'player_price_lane_usable':player_lane_healthy,
        'player_source_generated_at':player.get('generated_at'),'standard_source_generated_at':standard.get('generated_at'),
        'player_rows':len(player.get('rows') or []),'standard_rows':len(standard.get('rows') or []),
        'fixture_count':len(index),'gate_eligible_fixture_count':standard_gate,
        'player_gate_eligible_fixture_count':player_gate,'complete_fixture_count':complete,
        'player_transport':player.get('transport'),'standard_transport':standard.get('transport'),
        'read_contract':{'branch':'betflag-live','fixture_index':'feed/betflag-residential-fixtures-index.json','fixture_dir':'feed/betflag-residential-fixtures/','rule':'standard and player lanes are evaluated independently; player failure must not invalidate usable standard CURRENT'},
    }
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'standard_lane_healthy':standard_lane_healthy,'player_lane_healthy':player_lane_healthy,'fixtures':len(index),'standard_gate_eligible':standard_gate,'player_gate_eligible':player_gate,'complete':complete},ensure_ascii=False))

if __name__=='__main__':main()
