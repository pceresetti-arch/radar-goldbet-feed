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
COMBO_FAMILIES={'SCORER_COMBO','PLAYER_COMBO'}


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
    keep=('event_id','match_market_id','match','match_start','market_family','family','market_scope','market','line','selection','odd','selection_id','market_id','odds_id','player','player_event','source_tab','source_slot','source_slot_name','source_tab_name','discovery_source','betflag_opening_odd','betflag_opening_odd_field')
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


def compact_discovery(player):
    d=player.get('discovery') or {}
    keys=(
        'enabled','source','static_seed_count','dynamic_catalog_count','dynamic_only_count',
        'effective_target_count','dynamic_targets_queried','dynamic_targets_with_rows',
        'dynamic_rows','unknown_player_like_slot_count'
    )
    out={k:d.get(k) for k in keys if k in d}
    active=d.get('active_dynamic_targets') or []
    out['active_dynamic_target_count']=len(active)
    out['active_dynamic_targets']=active[:50]
    return out


def row_key(r):
    return (r.get('match_market_id'),r.get('event_id'),r.get('market_id'),r.get('odds_id'),r.get('selection_id'),r.get('line'),r.get('odd'))


def merge_rows(primary,extra):
    out=[]; seen=set()
    for r in list(primary or [])+list(extra or []):
        if not isinstance(r,dict): continue
        k=row_key(r)
        if k in seen: continue
        seen.add(k); out.append(r)
    return out


def main():
    player=load('betflag-residential-current.json')
    combo=load('betflag-combo-residential-current.json')
    standard=load('betflag-standard-current.json')
    standard_lane_healthy=bool(standard.get('source_healthy'))
    player_lane_healthy=bool(player.get('source_healthy'))
    combo_lane_healthy=bool(combo.get('source_healthy'))
    combined_healthy=standard_lane_healthy and player_lane_healthy
    discovery=compact_discovery(player)

    player_rows_all=merge_rows(player.get('rows') or [],combo.get('rows') or [])
    fixtures={}
    for r in standard.get('rows',[]): add(fixtures,r,'standard')
    for r in player_rows_all: add(fixtures,r,'player_props')

    generated_at=datetime.now(timezone.utc).isoformat()
    compact={}
    clear_json_dir(FIXTURE_DIR); clear_json_dir(ALIAS_FIXTURE_DIR)
    index=[]; alias_index=[]

    for k,f in fixtures.items():
        standard_rows=[slim(r) for r in f['standard']]
        player_rows=[slim(r) for r in f['player_props']]
        combo_rows=[r for r in player_rows if (r.get('market_family') or r.get('family')) in COMBO_FAMILIES]
        mids=sorted({str(r.get('match_market_id')) for r in f['standard']+f['player_props'] if r.get('match_market_id') not in (None,'')})
        identity_consistent=len(mids)<=1
        standard_ready=bool(standard_lane_healthy and identity_consistent and standard_rows)
        player_ready=bool(player_lane_healthy and identity_consistent and player_rows)
        combo_ready=bool(combo_lane_healthy and identity_consistent and combo_rows)
        coverage_complete=bool(standard_ready and player_ready)
        completeness='COMPLETE' if coverage_complete else ('STANDARD_ONLY' if standard_ready else ('PLAYER_ONLY' if player_ready else 'MISSING'))
        fixture={
            'schema_version':'betflag-residential-fixture-v4-coverage',
            'generated_at':generated_at,
            'player_source_generated_at':player.get('generated_at'),
            'combo_source_generated_at':combo.get('generated_at'),
            'standard_source_generated_at':standard.get('generated_at'),
            'source_class':'BETFLAG_AAMS_DIRECT',
            'source':'sportservice.betflag.it via residential self-hosted runner',
            'source_healthy':combined_healthy,
            'standard_lane_healthy':standard_lane_healthy,
            'player_lane_healthy':player_lane_healthy,
            'combo_lane_healthy':combo_lane_healthy,
            'identity_consistent':identity_consistent,
            'standard_coverage_complete':standard_ready,
            'player_coverage_complete':player_ready,
            'combo_coverage_complete':combo_ready,
            'coverage_complete':coverage_complete,
            'price_gate_fixture_eligible':standard_ready,
            'player_price_gate_fixture_eligible':player_ready,
            'combo_price_gate_fixture_eligible':combo_ready,
            'market_completeness':completeness,
            'match':f.get('match'),'match_start':f.get('match_start'),'match_market_ids':mids,
            'standard_market_families':family_counts(standard_rows),
            'player_market_families':family_counts(player_rows),
            'combo_market_families':family_counts(combo_rows),
            'standard':standard_rows,'player_props':player_rows,'combo_props':combo_rows,
            'coverage_contract':{
                'standard':'true only with concrete standard quote rows on a healthy standard lane',
                'player':'true only with concrete player quote rows on a healthy player lane; an empty player_props array is never complete',
                'combo':'true only with concrete fixture-specific SCORER_COMBO/PLAYER_COMBO quote rows on the healthy canonical combo lane',
                'not_observed':'never means unavailable; missing player/combo rows require recovery/discovery before BET readiness'
            }
        }
        filename=slug(f.get('match'))+'.json'
        payload=json.dumps(fixture,ensure_ascii=False,separators=(',',':'))
        (FIXTURE_DIR/filename).write_text(payload,encoding='utf-8')
        (ALIAS_FIXTURE_DIR/filename).write_text(payload,encoding='utf-8')
        base={
            'match':f.get('match'),'match_start':f.get('match_start'),
            'standard_count':len(standard_rows),'player_props_count':len(player_rows),'combo_props_count':len(combo_rows),
            'match_market_ids':mids,'identity_consistent':identity_consistent,
            'standard_coverage_complete':standard_ready,'player_coverage_complete':player_ready,'combo_coverage_complete':combo_ready,'coverage_complete':coverage_complete,
            'price_gate_fixture_eligible':standard_ready,'player_price_gate_fixture_eligible':player_ready,'combo_price_gate_fixture_eligible':combo_ready,
            'market_completeness':completeness,
            'standard_market_families':fixture['standard_market_families'],
            'player_market_families':fixture['player_market_families'],
            'combo_market_families':fixture['combo_market_families'],
        }
        index.append({**base,'file':f'feed/betflag-residential-fixtures/{filename}'})
        alias_index.append({**base,'file':f'feed/betflag-fixtures/{filename}'})
        compact[k]={**base,'standard':standard_rows,'player_props':player_rows,'combo_props':combo_rows}

    index.sort(key=lambda x:((x.get('match_start') or ''),(x.get('match') or '')))
    alias_index.sort(key=lambda x:((x.get('match_start') or ''),(x.get('match') or '')))
    standard_gate=sum(1 for x in index if x['price_gate_fixture_eligible'])
    player_gate=sum(1 for x in index if x['player_price_gate_fixture_eligible'])
    combo_gate=sum(1 for x in index if x['combo_price_gate_fixture_eligible'])
    complete=sum(1 for x in index if x['coverage_complete'])
    common={
        'schema_version':'betflag-residential-fixtures-index-v4-coverage','generated_at':generated_at,
        'player_source_generated_at':player.get('generated_at'),'combo_source_generated_at':combo.get('generated_at'),'standard_source_generated_at':standard.get('generated_at'),
        'source_class':'BETFLAG_AAMS_DIRECT','source_healthy':combined_healthy,
        'standard_lane_healthy':standard_lane_healthy,'player_lane_healthy':player_lane_healthy,'combo_lane_healthy':combo_lane_healthy,
        'player_market_discovery':discovery,
        'fixture_count':len(index),'gate_eligible_fixture_count':standard_gate,
        'player_gate_eligible_fixture_count':player_gate,'combo_gate_eligible_fixture_count':combo_gate,'complete_fixture_count':complete,
        'coverage_contract':'generic coverage_complete requires both standard and player concrete rows; combo readiness is separate and requires fixture-specific combo rows'
    }
    FIXTURE_INDEX.write_text(json.dumps({**common,'fixtures':index},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    ALIAS_FIXTURE_INDEX.write_text(json.dumps({**common,'compatibility_alias':True,'canonical_index':'feed/betflag-residential-fixtures-index.json','fixtures':alias_index},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    OUT.write_text(json.dumps({**common,'schema_version':'betflag-residential-hot-feed-v4-coverage','fixtures':compact},ensure_ascii=False,separators=(',',':')),encoding='utf-8')

    status={
        'schema_version':'betflag-live-status-v4-coverage','generated_at':generated_at,'source_class':'BETFLAG_AAMS_DIRECT',
        'source_healthy':combined_healthy,'standard_source_healthy':standard_lane_healthy,'player_source_healthy':player_lane_healthy,'combo_source_healthy':combo_lane_healthy,
        'standard_price_lane_usable':standard_lane_healthy,'player_price_lane_usable':player_lane_healthy,'combo_price_lane_usable':combo_lane_healthy,
        'player_source_generated_at':player.get('generated_at'),'combo_source_generated_at':combo.get('generated_at'),'standard_source_generated_at':standard.get('generated_at'),
        'player_rows':len(player.get('rows') or []),'combo_rows':len(combo.get('rows') or []),'merged_player_rows':len(player_rows_all),'standard_rows':len(standard.get('rows') or []),
        'player_market_discovery':discovery,
        'fixture_count':len(index),'gate_eligible_fixture_count':standard_gate,
        'player_gate_eligible_fixture_count':player_gate,'combo_gate_eligible_fixture_count':combo_gate,'complete_fixture_count':complete,
        'player_transport':player.get('transport'),'combo_transport':combo.get('transport'),'standard_transport':standard.get('transport'),
        'read_contract':{'branch':'betflag-live','fixture_index':'feed/betflag-residential-fixtures-index.json','fixture_dir':'feed/betflag-residential-fixtures/','rule':'standard, player and combo coverage are evaluated independently; no empty player/combo lane may be treated as complete'}
    }
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'standard_lane_healthy':standard_lane_healthy,'player_lane_healthy':player_lane_healthy,'combo_lane_healthy':combo_lane_healthy,'fixtures':len(index),'standard_gate_eligible':standard_gate,'player_gate_eligible':player_gate,'combo_gate_eligible':combo_gate,'complete':complete,'player_market_discovery':discovery},ensure_ascii=False))

if __name__=='__main__':main()
