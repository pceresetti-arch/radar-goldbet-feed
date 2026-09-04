#!/usr/bin/env python3
from pathlib import Path

PATH = Path('worker/src/index.mjs')
text = PATH.read_text(encoding='utf-8')
SENTINEL = 'RADAR_DYNAMIC_PLAYER_DISCOVERY_V1'

if SENTINEL in text:
    print('dynamic player discovery already installed')
    raise SystemExit(0)

anchor = "function standardSlotsFromLmtW(data) {"
if anchor not in text:
    raise SystemExit('standardSlotsFromLmtW anchor not found')

helpers = r'''
// RADAR_DYNAMIC_PLAYER_DISCOVERY_V1
// PLAYER_TARGETS remains a compatibility seed. At runtime BetFlag lmtW is also
// scanned so newly exposed player tabs/slots are ingested without a code release.
function playerMarketFamily(name) {
  const n = standardNorm(name);
  if (!n) return null;
  if ((n.includes('1 marcatore') || n.includes('primo marcatore') || n.includes('first scorer')) && (n.includes('sost') || n.includes('substitute'))) return 'PRIMO_MARCATORE_O_SOSTITUTO';
  if (n.includes('1 marcatore') || n.includes('primo marcatore') || n.includes('first scorer')) return 'PRIMO_MARCATORE';
  if ((n.includes('marcatore') || n === 'marc' || n.includes('scorer')) && (n.includes('1t') || n.includes('primo tempo') || n.includes('first half'))) return 'MARCATORE_1T';
  if ((n.includes('marcatore') || n === 'marc' || n.includes('scorer')) && (n.includes('2t') || n.includes('secondo tempo') || n.includes('second half'))) return 'MARCATORE_2T';
  if ((n.includes('assist') && n.includes('sost')) && (n.includes('marc') || n.includes('marcatore'))) return 'ASSIST_O_SOST_O_MARC_PLUS';
  if ((n.includes('marcatore') || n.includes('marc')) && n.includes('sost')) return 'MARCATORE_O_SOSTITUTO';
  if (n.includes('assist') && n.includes('sost')) return 'ASSIST_O_SOSTITUTO';
  if ((n.includes('gol') || n.includes('goal')) && n.includes('assist') && (n.includes(' o ') || n.includes('oppure'))) return 'GOL_O_ASSIST';
  if ((n.includes('gol') || n.includes('goal')) && n.includes('assist')) return 'GOL_E_ASSIST';
  if (n.includes('assist')) return 'ASSIST';
  if ((n.includes('tiri in porta') || n.includes('shots on target')) && (n.includes('1t') || n.includes('primo tempo') || n.includes('first half'))) return 'TIRI_IN_PORTA_1T';
  if ((n.includes('tiri totali') || n.includes('total shots')) && (n.includes('1t') || n.includes('primo tempo') || n.includes('first half'))) return 'TIRI_TOTALI_1T';
  if (n.includes('tiri in porta') || n.includes('shots on target')) return 'TIRI_IN_PORTA';
  if (n.includes('tiri totali') || n.includes('total shots') || n === 'tiri') return 'TIRI_TOTALI';
  if (n.includes('parate') || n.includes('saves')) return 'PARATE';
  if (n.includes('doppietta')) return 'DOPPIETTA';
  if (n.includes('tripletta')) return 'TRIPLETTA';
  if ((n.includes('marcatore') || n.includes('marc')) && n.includes('plus')) return 'MARCATORE_PLUS';
  if (n === 'marc' || n === 'marcatore' || n.includes('anytime scorer')) return 'MARCATORE_ANYTIME';
  return null;
}

function playerSlotsFromLmtW(data) {
  const out = [];
  const unknown = [];
  const tabs = data && typeof data === 'object' && Array.isArray(data.lmtW) ? data.lmtW : [];
  const seen = new Set();
  for (const tab of tabs) {
    if (!tab || typeof tab !== 'object') continue;
    const tabId = tab.tbI;
    const tabName = String(tab.tbN || '');
    const tabLooksPlayer = /giocator|player|marc|tir|assist|sost|parate/i.test(tabName);
    for (const item of tab.lotb || []) {
      if (!item || typeof item !== 'object') continue;
      const slotId = item.ti;
      const slotName = String(item.sn || '').trim();
      if (tabId == null || slotId == null || !slotName) continue;
      const family = playerMarketFamily(slotName);
      const playerLike = Boolean(family || tabLooksPlayer || /giocator|player|marc|tir|assist|sost|parate|doppietta|tripletta/i.test(slotName));
      if (!playerLike) continue;
      const key = `${tabId}|${slotId}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const row = { tab_id: tabId, tab_name: tabName, slot_id: slotId, slot_name: slotName, family, discovery_source: 'DYNAMIC_LMTW' };
      if (family) out.push(row); else unknown.push(row);
    }
  }
  return { slots: out, unknown };
}

function mergePlayerTargets(seedTargets, discovered) {
  const merged = [];
  const seen = new Set();
  for (const target of seedTargets || []) {
    const key = `${target[0]}|${target[1]}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push([target[0], target[1], target[2], 'STATIC_SEED']);
  }
  for (const slot of discovered?.slots || []) {
    const key = `${slot.tab_id}|${slot.slot_id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push([slot.tab_id, slot.slot_id, slot.slot_name, 'DYNAMIC_LMTW']);
  }
  return merged;
}

'''
text = text.replace(anchor, helpers + anchor, 1)

old = r'''async function fetchBetflagTargets(targets) {
  const started = Date.now();
  const fetchedAt = new Date().toISOString();
  const headers = betflagHeaders();
  const [standardResult, ...targetResults] = await Promise.all([
    fetchJson(standardBetflagUrl(), { headers }, 16000),
    ...targets.map((target) => fetchJson(targetBetflagUrl(target), { headers }, 16000))
  ]);
  const matchMap = buildMatchMap(standardResult.data);
  const rows = [];
  const seen = new Set();
  const calls = [];
  for (let i = 0; i < targets.length; i += 1) {
    const target = targets[i];
    const result = targetResults[i];
    const added = collectPlayerRows(result.data, target[2], matchMap, fetchedAt, seen);
    rows.push(...added);
    calls.push({ tab: target[0], slot: target[1], label: target[2], status: result.status, ok: result.ok, rows_added: added.length });
  }
  const sourceHealthy = standardResult.ok && targetResults.every((result) => result.ok);
  return {
    generated_at: fetchedAt,
    source_class: 'BETFLAG_AAMS_DIRECT',
    source: 'sportservice.betflag.it direct AAMS player service',
    source_url_host: 'sportservice.betflag.it',
    betflag_direct: true,
    goldbet_direct: false,
    source_healthy: sourceHealthy,
    price_gate_eligible_at_fetch: sourceHealthy && rows.length > 0,
    freshness_policy_seconds: BETFLAG_EXACT_FRESHNESS_SECONDS,
    elapsed_ms: Date.now() - started,
    match_map_count: matchMap.size,
    row_count: rows.length,
    standard_status: standardResult.status,
    calls,
    rows
  };
}'''

new = r'''async function fetchBetflagTargets(targets) {
  const started = Date.now();
  const fetchedAt = new Date().toISOString();
  const headers = betflagHeaders();
  const standardResult = await fetchJson(standardBetflagUrl(), { headers }, 16000);
  const discovery = playerSlotsFromLmtW(standardResult.data);
  const effectiveTargets = mergePlayerTargets(targets, discovery);
  const targetResults = await Promise.all(effectiveTargets.map((target) => fetchJson(targetBetflagUrl(target), { headers }, 16000)));
  const matchMap = buildMatchMap(standardResult.data);
  const rows = [];
  const seen = new Set();
  const calls = [];
  for (let i = 0; i < effectiveTargets.length; i += 1) {
    const target = effectiveTargets[i];
    const result = targetResults[i];
    const added = result.ok ? collectPlayerRows(result.data, target[2], matchMap, fetchedAt, seen) : [];
    rows.push(...added);
    calls.push({ tab: target[0], slot: target[1], label: target[2], discovery_source: target[3] || 'STATIC_SEED', status: result.status, ok: result.ok, rows_added: added.length });
  }
  const sourceHealthy = standardResult.ok && targetResults.every((result) => result.ok);
  return {
    generated_at: fetchedAt,
    source_class: 'BETFLAG_AAMS_DIRECT',
    source: 'sportservice.betflag.it direct AAMS player service',
    source_url_host: 'sportservice.betflag.it',
    betflag_direct: true,
    goldbet_direct: false,
    source_healthy: sourceHealthy,
    price_gate_eligible_at_fetch: sourceHealthy && rows.length > 0,
    freshness_policy_seconds: BETFLAG_EXACT_FRESHNESS_SECONDS,
    elapsed_ms: Date.now() - started,
    match_map_count: matchMap.size,
    row_count: rows.length,
    standard_status: standardResult.status,
    discovery: {
      enabled: true,
      source: 'lmtW',
      static_seed_count: targets.length,
      dynamic_recognized_count: discovery.slots.length,
      unknown_player_like_slots: discovery.unknown,
      effective_target_count: effectiveTargets.length
    },
    calls,
    rows
  };
}'''

if old not in text:
    raise SystemExit('fetchBetflagTargets exact anchor block not found')
text = text.replace(old, new, 1)
PATH.write_text(text, encoding='utf-8')
print('installed RADAR_DYNAMIC_PLAYER_DISCOVERY_V1')
