import json, pathlib, re, unicodedata, urllib.request, urllib.parse, time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BASE='https://radar-betflag-v7.p-ceresetti.workers.dev'
FEED=pathlib.Path('feed')
FIXTURE_DIR=FEED/'betflag-fixtures'
INDEX=FEED/'betflag-fixtures-index.json'


def norm(v):
    s=unicodedata.normalize('NFD',str(v or ''))
    s=''.join(c for c in s if unicodedata.category(c)!='Mn').lower()
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())


def slug(v):
    s=norm(v).replace(' ','-')
    s=re.sub(r'-+','-',s).strip('-')
    return s[:140] or 'fixture'


def get_json(path, timeout=75):
    sep='&' if '?' in path else '?'
    url=BASE+path+sep+'cb='+str(int(time.time()*1000))
    req=urllib.request.Request(url,headers={
        'Accept':'application/json',
        'Cache-Control':'no-cache',
        'User-Agent':'RadarBetFlagWorkerFixtureFeed/1.0'
    })
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.status,json.loads(r.read().decode())


def freshness_ok(body):
    f=body.get('freshness') or {}
    return bool(body.get('source_healthy') and f.get('fresh'))


def main():
    today=datetime.now(ZoneInfo('Europe/Rome')).strftime('%d-%m-%Y')
    qs=urllib.parse.urlencode({'date':today})
    ss,standard=get_json('/live/standard-index?'+qs)
    ps,players=get_json('/live/player-index?'+qs)
    if ss!=200 or ps!=200:
        raise SystemExit(f'Worker HTTP failure standard={ss} player={ps}')
    if not freshness_ok(standard):
        raise SystemExit('Worker standard index is not healthy/fresh')
    if not freshness_ok(players):
        raise SystemExit('Worker player index is not healthy/fresh')

    merged={}
    for f in standard.get('fixtures') or []:
        mi=str(f.get('match_market_id') or '').strip()
        key=('mi:'+mi) if mi else ('match:'+norm(f.get('match'))+'|'+str(f.get('start_time') or ''))
        merged[key]={
            'fixture_key':key,
            'match_market_id':f.get('match_market_id'),
            'match_event_id':f.get('event_id'),
            'match':f.get('match'),
            'match_start':f.get('start_time'),
            'league':f.get('league'),
            'standard':f.get('standard') or [],
            'players':[],
            'player_mapping_status':None,
        }

    for f in players.get('fixtures') or []:
        mi=str(f.get('match_market_id') or '').strip()
        key=('mi:'+mi) if mi else str(f.get('fixture_key') or '')
        target=merged.get(key)
        if target is None:
            target={
                'fixture_key':key,
                'match_market_id':f.get('match_market_id'),
                'match_event_id':f.get('match_event_id'),
                'match':f.get('match'),
                'match_start':f.get('start_time'),
                'league':f.get('league'),
                'standard':[],
                'players':[],
                'player_mapping_status':f.get('mapping_status'),
            }
            merged[key]=target
        target['players']=f.get('players') or []
        target['player_mapping_status']=f.get('mapping_status')
        if not target.get('match') and f.get('match'): target['match']=f.get('match')
        if not target.get('match_start') and f.get('start_time'): target['match_start']=f.get('start_time')
        if not target.get('league') and f.get('league'): target['league']=f.get('league')
        if not target.get('match_event_id') and f.get('match_event_id'): target['match_event_id']=f.get('match_event_id')

    generated=datetime.now(timezone.utc).isoformat()
    FIXTURE_DIR.mkdir(parents=True,exist_ok=True)
    for p in FIXTURE_DIR.glob('*.json'):
        try: p.unlink()
        except OSError: pass

    index=[]
    for key,f in merged.items():
        if not f.get('match'): continue
        player_quote_count=sum(len(m.get('quotes') or []) for pl in f.get('players') or [] for m in pl.get('markets') or [])
        doc={
            'schema_version':'betflag-worker-fixture-feed-v1',
            'generated_at':generated,
            'source_class':'BETFLAG_AAMS_DIRECT',
            'source':'radar-betflag-v7 Worker -> sportservice.betflag.it AAMS',
            'source_healthy':True,
            'freshness':{
                'standard':standard.get('freshness'),
                'player':players.get('freshness')
            },
            'standard_source_generated_at':standard.get('generated_at'),
            'player_source_generated_at':players.get('generated_at'),
            'match':f.get('match'),
            'match_start':f.get('match_start'),
            'league':f.get('league'),
            'match_market_id':f.get('match_market_id'),
            'match_event_id':f.get('match_event_id'),
            'standard':f.get('standard') or [],
            'players':f.get('players') or [],
            'player_mapping_status':f.get('player_mapping_status'),
            'exact_player_price_endpoint':'/live/player-price',
        }
        filename=slug(f.get('match'))+'.json'
        (FIXTURE_DIR/filename).write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        index.append({
            'match':f.get('match'),
            'match_start':f.get('match_start'),
            'league':f.get('league'),
            'match_market_id':f.get('match_market_id'),
            'file':'feed/betflag-fixtures/'+filename,
            'standard_count':len(doc['standard']),
            'player_count':len(doc['players']),
            'player_quote_count':player_quote_count,
            'complete_for_full_scan':bool(doc['standard'] and doc['players'])
        })

    index.sort(key=lambda x:(str(x.get('match_start') or ''),str(x.get('match') or '')))
    output={
        'schema_version':'betflag-worker-fixtures-index-v1',
        'generated_at':generated,
        'date':today,
        'source_class':'BETFLAG_AAMS_DIRECT',
        'source':'radar-betflag-v7 Worker -> sportservice.betflag.it AAMS',
        'source_healthy':True,
        'standard_source_generated_at':standard.get('generated_at'),
        'player_source_generated_at':players.get('generated_at'),
        'standard_freshness':standard.get('freshness'),
        'player_freshness':players.get('freshness'),
        'fixture_count':len(index),
        'full_scan_ready_count':sum(1 for x in index if x['complete_for_full_scan']),
        'fixtures':index
    }
    INDEX.write_text(json.dumps(output,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'source_healthy':True,'fixture_count':len(index),'full_scan_ready_count':output['full_scan_ready_count'],'date':today},ensure_ascii=False))

if __name__=='__main__':
    main()
