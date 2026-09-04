import json
import pathlib
import re
from datetime import datetime, timezone

from betflag_session_transport import BetFlagTransport
from betflag_residential_collector import (
    BASE,
    AGG,
    norm,
    walk,
    extract_matches,
    discover_player_targets,
    player_market_family,
)

FEED = pathlib.Path('feed')
OUT = FEED / 'betflag-combo-residential-current.json'
SUMMARY = FEED / 'betflag-combo-residential-summary.json'

COMBO_FAMILIES = {'SCORER_COMBO', 'PLAYER_COMBO'}


def contextual_family(market_name, target):
    """Classify combo markets using both returned market name and discovered tab/slot context.

    BetFlag sometimes returns a generic market name such as "Combo" while the player nature is
    encoded in the lmtW tab/slot that produced the response. The canonical collector previously
    discarded those rows because the market name alone was not player-like.
    """
    direct = player_market_family(market_name)
    if direct in COMBO_FAMILIES:
        return direct

    target_market = str((target or {}).get('market') or '')
    tab_name = str((target or {}).get('tab_name') or '')
    ctx = norm(' '.join((str(market_name or ''), target_market, tab_name)))
    combo_context = bool((target or {}).get('combo_tab')) or 'combo' in ctx
    if not combo_context:
        return direct

    scorerish = bool(re.search(r'marcat|marc |segna|scorer|gol|goal|doppiett|triplett', ctx))
    playerish = bool(re.search(r'giocator|player|assist|tiri|shot|parate|sost', ctx))
    if scorerish:
        return 'SCORER_COMBO'
    if playerish or combo_context:
        return 'PLAYER_COMBO'
    return None


def combo_target(target):
    ctx = norm(' '.join((str(target.get('market') or ''), str(target.get('tab_name') or ''))))
    family = target.get('family') or player_market_family(target.get('market'))
    return bool(target.get('combo_tab') or 'combo' in ctx or family in COMBO_FAMILIES)


def iter_markets(mm):
    if isinstance(mm, dict):
        return mm.values()
    if isinstance(mm, list):
        return mm
    return []


def iter_spreads(spd):
    if isinstance(spd, dict):
        return spd.items()
    if isinstance(spd, list):
        return enumerate(spd)
    return []


def extract_combo_rows(data, matches, target):
    rows = []
    for event in walk(data):
        if not isinstance(event, dict):
            continue
        event_name = str(event.get('en') or '')
        if event.get('ei') is None or not event_name.startswith('('):
            continue

        player = re.sub(r'^\([^)]+\)\s*', '', event_name).strip()
        match_node = matches.get(str(event.get('mi'))) or {}
        match_name = match_node.get('en')
        match_start = match_node.get('ed') or event.get('ed')

        for market in iter_markets(event.get('mmkW') or {}):
            if not isinstance(market, dict):
                continue
            market_name = str(market.get('mn') or target.get('market') or '').strip()
            family = contextual_family(market_name, target)
            if family not in COMBO_FAMILIES:
                continue

            for line, spread in iter_spreads(market.get('spd') or {}):
                if not isinstance(spread, dict):
                    continue
                for quote in spread.get('asl') or []:
                    if not isinstance(quote, dict):
                        continue
                    odd = quote.get('ov')
                    if not isinstance(odd, (int, float)) or odd <= 1:
                        continue
                    rows.append({
                        'event_id': event.get('ei'),
                        'player_event': event_name,
                        'player': player,
                        'match_market_id': event.get('mi'),
                        'match': match_name,
                        'match_start': match_start,
                        'market': market_name,
                        'market_family': family,
                        'line': None if str(line) in ('0', '0.0') else line,
                        'selection': quote.get('sn'),
                        'odd': odd,
                        'selection_id': quote.get('si'),
                        'market_id': quote.get('mi'),
                        'odds_id': quote.get('oi'),
                        'source_tab': target.get('tab'),
                        'source_slot': target.get('slot'),
                        'source_slot_name': target.get('market'),
                        'source_tab_name': target.get('tab_name'),
                        'discovery_source': target.get('discovery_source'),
                    })
    return rows


def dedupe(rows):
    seen = set()
    out = []
    for row in rows:
        key = (
            row.get('match_market_id'), row.get('event_id'), row.get('market_id'),
            row.get('odds_id'), row.get('selection_id'), row.get('line'), row.get('odd'),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main():
    now = datetime.now(timezone.utc).isoformat()
    result = {
        'schema_version': 'betflag-combo-residential-v1',
        'generated_at': now,
        'source_class': 'BETFLAG_AAMS_DIRECT',
        'source': 'sportservice.betflag.it canonical residential lmtW tab/slot player routes',
        'source_healthy': False,
        'combo_targets': [],
        'rows': [],
    }
    client = BetFlagTransport(timeout=30)
    try:
        status, standard = client.get(f'{BASE}/getOverviewEventsAams/0/1/0/{AGG}/0/0/0?channelId=0')
        result['standard_status'] = status
        if status != 200:
            raise RuntimeError(f'overview HTTP {status}')

        matches = extract_matches(standard)
        discovered, unknown, combo_tabs = discover_player_targets(standard)
        targets = [t for t in discovered if combo_target(t)]
        result['combo_tabs'] = combo_tabs
        result['unknown_player_like_slots'] = unknown

        raw_rows = []
        successful_targets = 0
        for target in targets:
            target_row = {
                'tab': target.get('tab'),
                'slot': target.get('slot'),
                'market': target.get('market'),
                'tab_name': target.get('tab_name'),
                'family': target.get('family'),
                'combo_tab': bool(target.get('combo_tab')),
            }
            try:
                url = f"{BASE}/getOverviewEventsAams/0/-1/0/{AGG}/{target['tab']}/{target['slot']}/0?channelId=0"
                st, data = client.get(url)
                rows = extract_combo_rows(data, matches, target) if st == 200 else []
                target_row['status'] = st
                target_row['quote_rows'] = len(rows)
                if st == 200:
                    successful_targets += 1
                raw_rows.extend(rows)
            except Exception as exc:
                target_row['status'] = None
                target_row['quote_rows'] = 0
                target_row['error'] = repr(exc)
            result['combo_targets'].append(target_row)

        result['rows'] = dedupe(raw_rows)
        result['source_healthy'] = True
        result['combo_target_count'] = len(targets)
        result['combo_targets_queried_ok'] = successful_targets
    except Exception as exc:
        result['error'] = repr(exc)
    finally:
        result['transport'] = client.diagnostics()
        client.close()

    rows = result.get('rows') or []
    target_count = int(result.get('combo_target_count') or 0)
    ok_count = int(result.get('combo_targets_queried_ok') or 0)
    if not result.get('source_healthy'):
        state = 'SOURCE_UNHEALTHY'
    elif target_count == 0:
        state = 'NO_COMBO_TARGETS_DISCOVERED'
    elif ok_count == 0:
        state = 'COMBO_TARGET_ROUTES_UNHEALTHY'
    elif not rows:
        state = 'NO_LIVE_COMBO_QUOTES_OBSERVED'
    else:
        state = 'LIVE_COMBO_QUOTES_AVAILABLE'

    fixture_names = sorted({str(r.get('match')) for r in rows if r.get('match')})
    players = sorted({str(r.get('player')) for r in rows if r.get('player')})
    markets = sorted({str(r.get('market')) for r in rows if r.get('market')})
    families = sorted({str(r.get('market_family')) for r in rows if r.get('market_family')})
    summary = {
        'schema_version': 'betflag-combo-residential-summary-v1',
        'generated_at': now,
        'source_healthy': bool(result.get('source_healthy')),
        'availability_state': state,
        'ready': state == 'LIVE_COMBO_QUOTES_AVAILABLE',
        'combo_targets_discovered': target_count,
        'combo_targets_queried_ok': ok_count,
        'quote_rows': len(rows),
        'fixture_count': len(fixture_names),
        'player_count': len(players),
        'market_count': len(markets),
        'families': families,
        'fixtures': fixture_names[:50],
        'markets': markets[:100],
        'sample_rows': rows[:20],
        'contract': {
            'zero_rows_meaning': 'If source_healthy and combo_targets_queried_ok>0, zero rows means no live qualifying combo quotes were observed, not parser failure.',
            'bet_ready_requires': 'A concrete fixture/player/market/selection/odd row from the canonical BetFlag residential route.',
        },
    }
    result['summary'] = summary

    FEED.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
