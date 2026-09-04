import json, pathlib, re, unicodedata
from collections import Counter
from datetime import datetime, timezone
from betflag_session_transport import BetFlagTransport

BASE='https://sportservice.betflag.it/api/sport/pregame'
AGG=1334500001
FEED=pathlib.Path('feed')
OUT=FEED/'betflag-combo-detail-availability.json'


def norm(v):
    s=unicodedata.normalize('NFD',str(v or ''))
    s=''.join(c for c in s if unicodedata.category(c)!='Mn').lower().replace('°','')
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())


def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)


def marketish(name):
    n=norm(name)
    return bool(re.search(r'marcat|marc |assist|giocator|player|combo|doppietta|tripletta|tiri|parate|segna',n))


def player_or_scorer_market(name):
    n=norm(name)
    return bool(re.search(r'marcat|marc |assist|giocator|player|doppietta|tripletta|tiri|parate|segna',n))


def extract_market_names(body):
    names=[]
    for x in walk(body):
        if not isinstance(x,dict): continue
        for k in ('mn','sn','tbN'):
            v=x.get(k)
            if isinstance(v,str) and marketish(v): names.append(v.strip())
    return sorted(set(names))


def _odd_value(x):
    for k in ('ov','odd','price','quota'):
        if x.get(k) is not None:
            return x.get(k)
    return None


def _market_name_from_node(x, inherited=None):
    mn=x.get('mn')
    if isinstance(mn,str) and marketish(mn):
        return mn.strip()
    # BetFlag detail trees frequently expose the market label as sn on a node
    # that owns los/spd/asl, while descendant selection nodes only carry ids/odds.
    sn=x.get('sn')
    if isinstance(sn,str) and marketish(sn) and any(k in x for k in ('spd','asl','los','mi','ti','minO','maxO')):
        return sn.strip()
    return inherited


def extract_quote_rows(body, section, section_name):
    """Extract odds from BetFlag detail payloads without assuming mn->spd->asl.

    The current AAMS payload can place ov several levels below a market node and
    can use sn instead of mn for the market label. We therefore walk the tree
    carrying market/line/selection context down to every odds-bearing node.
    """
    rows=[]
    seen=set()

    def rec(node, market=None, market_id=None, line=None, selection=None):
        if isinstance(node,list):
            for item in node:
                rec(item,market,market_id,line,selection)
            return
        if not isinstance(node,dict):
            return

        cur_market=_market_name_from_node(node,market)
        cur_market_id=node.get('mi') if node.get('mi') is not None else market_id
        if cur_market_id is None and cur_market and node.get('ti') is not None:
            cur_market_id=node.get('ti')

        cur_selection=selection
        for k in ('ssn','sn','name','selectionName'):
            v=node.get(k)
            if isinstance(v,str) and v.strip() and (not cur_market or norm(v)!=norm(cur_market)):
                # ssn is commonly the child selection label. sn is accepted only
                # when it is not the market label inherited above.
                if k=='ssn' or not marketish(v) or node.get('ov') is not None:
                    cur_selection=v.strip()
                    break

        odd=_odd_value(node)
        if odd is not None and cur_market and marketish(cur_market):
            sel_id=node.get('si')
            odds_id=node.get('oi')
            key=(str(cur_market),str(line),str(sel_id),str(odds_id),str(cur_selection),str(odd))
            if key not in seen:
                seen.add(key)
                rows.append({
                    'section':section,
                    'section_name':section_name,
                    'market':cur_market,
                    'market_is_player_or_scorer':player_or_scorer_market(cur_market),
                    'line':None if line is None or str(line) in ('0','0.0') else line,
                    'selection':cur_selection,
                    'odd':odd,
                    'selection_id':sel_id,
                    'market_id':cur_market_id,
                    'odds_id':odds_id
                })

        for k,v in node.items():
            if not isinstance(v,(dict,list)):
                continue
            if k=='spd' and isinstance(v,dict):
                for lk,lv in v.items():
                    rec(lv,cur_market,cur_market_id,lk,cur_selection)
            else:
                rec(v,cur_market,cur_market_id,line,cur_selection)

    rec(body)
    return rows


def overview_fixtures(std):
    out={}
    for x in walk(std):
        if not isinstance(x,dict): continue
        en=str(x.get('en') or '')
        if x.get('mi') is None or not en or en.startswith('('): continue
        key=norm(en)
        cur=out.setdefault(key,{'match':en,'nodes':[]})
        cur['nodes'].append({k:x.get(k) for k in ('ei','mi','ti','tai','ed','en')})
    return out


def relevant_sections(std):
    ids={0,1,2,3,4,5,6,7,8,9,10,2484}
    tab_names={}
    for node in walk(std):
        tabs=node.get('lmtW') if isinstance(node,dict) else None
        if not isinstance(tabs,list): continue
        for tab in tabs:
            if not isinstance(tab,dict): continue
            tid=tab.get('tbI'); tname=str(tab.get('tbN') or '')
            if tid is None: continue
            if re.search(r'giocator|player|marcator|combo|speciali',norm(tname)):
                try:
                    tid=int(tid); ids.add(tid); tab_names[str(tid)]=tname
                except: pass
    return sorted(ids),tab_names


def load_player_matches():
    p=FEED/'betflag-residential-current.json'
    if not p.exists(): return [],'missing feed/betflag-residential-current.json'
    try: data=json.loads(p.read_text(encoding='utf-8-sig'))
    except Exception as e: return [],repr(e)
    counts=Counter(); starts={}
    for r in data.get('rows') or []:
        m=r.get('match')
        if not m: continue
        counts[m]+=1
        if r.get('match_start'): starts[m]=r.get('match_start')
    rows=[{'match':m,'player_rows':c,'match_start':starts.get(m)} for m,c in counts.items()]
    rows.sort(key=lambda x:(-(x['player_rows']),x.get('match_start') or '',x['match']))
    return rows,None


def best_fixture_node(nodes):
    ranked=sorted(nodes,key=lambda x:sum(x.get(k) is not None for k in ('tai','ti','mi','ei')),reverse=True)
    return ranked[0] if ranked else None


def main():
    now=datetime.now(timezone.utc).isoformat()
    client=BetFlagTransport(timeout=20)
    out={'schema_version':'betflag-combo-detail-availability-v4','generated_at':now,'source_class':'BETFLAG_AAMS_DIRECT','source_healthy':False,'candidate_rule':'probe only fixtures that already expose BetFlag player rows; combo availability is fixture-specific, not assumed league-wide','fixtures':[]}
    try:
        st,std=client.get(f'{BASE}/getOverviewEventsAams/0/1/0/{AGG}/0/0/0?channelId=0')
        out['overview_status']=st
        if st!=200: raise RuntimeError(f'overview HTTP {st}')
        fixtures=overview_fixtures(std)
        sections,tab_names=relevant_sections(std)
        out['sections_probed']=sections
        out['section_names']=tab_names
        all_candidates,load_error=load_player_matches()
        out['player_feed_load_error']=load_error
        out['candidate_count_total']=len(all_candidates)
        candidates=all_candidates[:20]
        out['candidate_count']=len(candidates)
        for cand in candidates:
            f=fixtures.get(norm(cand['match']))
            row={**cand,'resolved':bool(f),'detail_attempts':[],'combo_or_player_detail_available':False,'market_names':[],'quote_rows':[]}
            if not f:
                out['fixtures'].append(row); continue
            node=best_fixture_node(f['nodes'])
            row['ids']=node
            if not node or any(node.get(k) is None for k in ('ti','mi','ei')):
                row['resolution_error']='missing detail identifiers'; out['fixtures'].append(row); continue
            tai=node.get('tai') or 0
            found=set(); qrows=[]; qseen=set(); positive_at=None
            for idx,sec in enumerate(sections):
                url=f"{BASE}/getDetailsEventAams/{tai}/{node['ti']}/{node['mi']}/{node['ei']}/{sec}/0?channelId=0"
                try:
                    status,body=client.get(url)
                    names=extract_market_names(body) if status==200 else []
                    quotes=extract_quote_rows(body,sec,tab_names.get(str(sec))) if status==200 else []
                    for n in names: found.add(n)
                    for qr in quotes:
                        k=(qr.get('market'),str(qr.get('line')),str(qr.get('selection_id')),str(qr.get('odds_id')),str(qr.get('selection')),str(qr.get('odd')))
                        if k not in qseen:
                            qseen.add(k); qrows.append(qr)
                    hit=bool(names or quotes)
                    row['detail_attempts'].append({'section':sec,'section_name':tab_names.get(str(sec)),'status':status,'market_name_count':len(names),'quote_row_count':len(quotes),'market_names':names[:40]})
                    if hit and positive_at is None: positive_at=idx
                    if positive_at is not None and idx-positive_at>=4: break
                except Exception as e:
                    row['detail_attempts'].append({'section':sec,'section_name':tab_names.get(str(sec)),'status':None,'error':repr(e)})
            row['market_names']=sorted(found)
            row['quote_rows']=qrows[:2000]
            row['quote_row_count']=len(qrows)
            row['player_or_scorer_quote_row_count']=sum(1 for q in qrows if q.get('market_is_player_or_scorer'))
            row['combo_or_player_detail_available']=bool(found or qrows)
            row['positive_sections']=[a['section'] for a in row['detail_attempts'] if a.get('market_name_count',0)>0 or a.get('quote_row_count',0)>0]
            out['fixtures'].append(row)
        out['resolved_fixture_count']=sum(1 for x in out['fixtures'] if x.get('resolved'))
        out['fixtures_with_detail_player_markets']=sum(1 for x in out['fixtures'] if x['combo_or_player_detail_available'])
        out['fixtures_with_quote_rows']=sum(1 for x in out['fixtures'] if x.get('quote_row_count',0)>0)
        out['fixtures_with_player_or_scorer_quote_rows']=sum(1 for x in out['fixtures'] if x.get('player_or_scorer_quote_row_count',0)>0)
        out['total_quote_rows']=sum(x.get('quote_row_count',0) for x in out['fixtures'])
        out['total_player_or_scorer_quote_rows']=sum(x.get('player_or_scorer_quote_row_count',0) for x in out['fixtures'])
        out['source_healthy']=True
    except Exception as e:
        out['error']=repr(e)
    finally:
        out['transport']=client.diagnostics(); client.close()
    FEED.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:out.get(k) for k in ('source_healthy','candidate_count_total','candidate_count','resolved_fixture_count','fixtures_with_detail_player_markets','fixtures_with_quote_rows','fixtures_with_player_or_scorer_quote_rows','total_quote_rows','total_player_or_scorer_quote_rows','player_feed_load_error')},ensure_ascii=False))

if __name__=='__main__': main()
