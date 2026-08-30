#!/usr/bin/env python3
import json
import os
import re
import statistics
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BETFLAG_INDEX = ROOT / "feed" / "betflag-fixtures-index.json"
OUT = ROOT / "feed" / "information-move-current.json"
DETAIL_WORK = ROOT / "feed" / ".information-move-detail-working.json"

FLASH_FEED = "https://www.flashscore.com/x/feed/f_1_0_3_en_1"
ODDS_URL = "https://global.ds.lsapp.eu/odds/pq_graphql"
HEADERS = {
    "x-fsign": "SW9D1eZo",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Referer": "https://www.flashscore.com/",
    "Origin": "https://www.flashscore.com",
    "Accept": "*/*",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}
ITALY_PARAMS = {
    "_hash": "oce",
    "projectId": "2",
    "geoIpCode": "IT",
    "geoIpSubdivisionCode": "IT",
}
MAX_HOURS = 18
MAX_FIXTURES = 50
PARALLEL_WORKERS = 8
REQUEST_TIMEOUT = (4, 12)
MIN_BOOKS = 4
MIN_CONSENSUS = 0.65
PRIORITY_STANDARD_COUNT = 35


def atomic_write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if not payload or payload == "{}":
        raise RuntimeError(f"Refusing empty output for {path}")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    stop = {"fc", "cf", "ac", "sc", "afc", "calcio"}
    toks = [x for x in s.split() if x not in stop]
    aliases = {
        "internazionale": "inter",
        "inter milan": "inter",
        "manchester utd": "manchester united",
        "man utd": "manchester united",
        "psg": "paris saint germain",
    }
    out = " ".join(toks)
    return aliases.get(out, out)


def split_match(s):
    parts = re.split(r"\s+-\s+", str(s or ""), maxsplit=1)
    return (parts[0], parts[1]) if len(parts) == 2 else (str(s or ""), "")


def similarity_norm(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.94
    return SequenceMatcher(None, a, b).ratio()


def parse_flash_feed(raw):
    out = []
    for sec in raw.split("~"):
        d = {}
        for p in sec.split(chr(0xAC)):
            if chr(0xF7) in p:
                k, v = p.split(chr(0xF7), 1)
                d[k] = v
        if d.get("AA") and d.get("AE") and d.get("AF"):
            try:
                ts = int(d.get("AD") or 0)
            except Exception:
                ts = 0
            out.append({"event_id": d["AA"], "home": d["AE"], "away": d["AF"], "start_ts": ts})
    return out


def price(v):
    try:
        x = float(v)
        return x if x > 1.0 else None
    except Exception:
        return None


def prob_shift_pp(opening, current):
    if not opening or not current:
        return None
    return (1.0 / current - 1.0 / opening) * 100.0


def identity_rows(item):
    typ = str(item.get("bettingType") or "")
    scope = str(item.get("bettingScope") or "")
    odds = item.get("odds") or []
    rows = []
    if scope != "FULL_TIME":
        return rows
    if typ == "HOME_DRAW_AWAY":
        labels = ["HOME", "AWAY", "DRAW"]
        for i, o in enumerate(odds[:3]):
            rows.append(("1X2", labels[i], None, o))
    elif typ == "OVER_UNDER":
        for o in odds:
            sel = str(o.get("selection") or "").upper()
            line = (o.get("handicap") or {}).get("value")
            if sel in ("OVER", "UNDER") and line is not None:
                rows.append(("OVER_UNDER", sel, str(line), o))
    elif typ == "BOTH_TEAMS_TO_SCORE":
        for o in odds:
            b = o.get("bothTeamsToScore")
            if b is not None:
                rows.append(("BTTS", "YES" if b else "NO", None, o))
    elif typ == "DRAW_NO_BET":
        for i, o in enumerate(odds[:2]):
            rows.append(("DRAW_NO_BET", "HOME" if i == 0 else "AWAY", None, o))
    return rows


def fixture_priority(b):
    try:
        standard_count = int(b.get("standard_count") or 0)
    except Exception:
        standard_count = 0
    try:
        player_count = int(b.get("player_count") or b.get("player_props_count") or 0)
    except Exception:
        player_count = 0
    try:
        player_quotes = int(b.get("player_quote_count") or b.get("player_props_count") or 0)
    except Exception:
        player_quotes = 0
    if b.get("complete_for_full_scan") or player_count > 0 or player_quotes > 0:
        tier = 0
    elif standard_count >= PRIORITY_STANDARD_COUNT:
        tier = 1
    else:
        tier = 2
    return tier, -player_quotes, -standard_count


def move_score(gb_pp, median_pp, ratio, n_books):
    mag = min(40.0, max(0.0, gb_pp) * 8.0)
    consensus = 30.0 * max(0.0, min(1.0, ratio)) * min(1.0, n_books / 6.0)
    market = min(20.0, max(0.0, median_pp) * (20.0 / 3.0))
    breadth = min(10.0, max(0, n_books - 3) * 2.0)
    penalty = 0.0
    if ratio < 0.55:
        penalty += 20.0
    if median_pp <= 0:
        penalty += 15.0
    return round(max(0.0, min(100.0, mag + consensus + market + breadth - penalty)), 1)


def move_class(score):
    if score >= 80:
        return "INFORMATION_MOVE_A"
    if score >= 65:
        return "INFORMATION_MOVE_B"
    if score >= 50:
        return "INFORMATION_MOVE_C"
    return "NO_STRONG_INFORMATION_MOVE"


def process_candidate(candidate):
    _, match_score, ev, bf_ev = candidate
    params = dict(ITALY_PARAMS)
    params["eventId"] = ev["event_id"]
    entry = {
        "flashscore_event_id": ev["event_id"],
        "betflag_event_id": bf_ev.get("match_event_id"),
        "match": bf_ev.get("match"),
        "league": bf_ev.get("league"),
        "flashscore_match": f"{ev['home']} - {ev['away']}",
        "match_score": round(match_score, 3),
        "start_ts": ev["start_ts"],
        "start_time_utc": datetime.fromtimestamp(ev["start_ts"], tz=timezone.utc).isoformat(),
        "priority_tier": fixture_priority(bf_ev)[0],
        "markets": [],
    }
    try:
        rr = requests.get(ODDS_URL, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        entry["http_status"] = rr.status_code
        if not rr.ok:
            return entry, []
        fo = ((rr.json().get("data") or {}).get("findOddsByEventId") or {})
    except Exception as exc:
        entry["error"] = repr(exc)
        return entry, []

    bmap = {}
    for x in (fo.get("settings") or {}).get("bookmakers", []):
        b = (x or {}).get("bookmaker") or {}
        if b.get("id") is not None:
            bmap[str(b["id"])] = b.get("name")

    buckets = {}
    for item in fo.get("odds") or []:
        bn = bmap.get(str(item.get("bookmakerId", "")), "")
        if not bn:
            continue
        for market, selection, line, o in identity_rows(item):
            op, cur = price(o.get("opening")), price(o.get("value"))
            if op is None or cur is None:
                continue
            key = (market, selection, line)
            buckets.setdefault(key, []).append({
                "bookmaker": bn,
                "opening": op,
                "current": cur,
                "shift_pp": round(prob_shift_pp(op, cur), 3),
            })

    signals = []
    for (market, selection, line), books in buckets.items():
        gb = next((x for x in books if str(x["bookmaker"]).lower() == "goldbet"), None)
        if not gb:
            continue
        shifts = [x["shift_pp"] for x in books if x.get("shift_pp") is not None]
        if not shifts:
            continue
        gb_pp = gb["shift_pp"]
        direction = 1 if gb_pp > 0.15 else (-1 if gb_pp < -0.15 else 0)
        directional = [x for x in shifts if abs(x) >= 0.15]
        if direction == 0:
            same = 0
            ratio = 0.0
        else:
            same = sum(1 for x in directional if (x > 0) == (direction > 0))
            ratio = same / len(directional) if directional else 0.0
        med = statistics.median(shifts)
        score = move_score(gb_pp, med, ratio, len(books)) if gb_pp > 0 else 0.0
        cls = move_class(score)
        likely = (
            cls in ("INFORMATION_MOVE_A", "INFORMATION_MOVE_B")
            and gb_pp > 0
            and med >= 0.5
            and len(books) >= MIN_BOOKS
            and ratio >= MIN_CONSENSUS
        )
        rec = {
            "market": market,
            "selection": selection,
            "line": line,
            "goldbet_opening": gb["opening"],
            "goldbet_current": gb["current"],
            "goldbet_decimal_drop": round(gb["opening"] - gb["current"], 3),
            "goldbet_implied_prob_shift_pp": gb_pp,
            "books_with_open_current": len(books),
            "directional_books": len(directional),
            "same_direction_count": same,
            "consensus_ratio": round(ratio, 3),
            "median_implied_prob_shift_pp": round(med, 3),
            "information_move_score": score,
            "information_move_class": cls,
            "likely_information_move": likely,
            "requires_news_xi_recheck": likely,
            "radar_use": "PRIORITY_RECHECK_AND_LAG_TEST" if likely else "CONTEXT_ONLY",
            "book_moves": books,
        }
        entry["markets"].append(rec)
        if likely:
            signals.append({
                "match": entry["match"],
                "league": entry.get("league"),
                "betflag_event_id": entry["betflag_event_id"],
                **{k: rec[k] for k in rec if k != "book_moves"},
            })
    entry["markets"].sort(key=lambda x: -x["information_move_score"])
    return entry, signals


def compact_fixture(fx):
    keep = {
        "flashscore_event_id", "betflag_event_id", "match", "league",
        "match_score", "start_ts", "start_time_utc", "priority_tier",
        "http_status", "error",
    }
    out = {k: v for k, v in fx.items() if k in keep}
    out["markets"] = [
        {k: v for k, v in m.items() if k != "book_moves"}
        for m in (fx.get("markets") or [])
    ]
    return out


def main():
    started = datetime.now(timezone.utc)
    now = started
    try:
        bf = json.loads(BETFLAG_INDEX.read_text(encoding="utf-8"))
    except Exception:
        bf = {}
    bf_fixtures = bf.get("fixtures") or []

    r = requests.get(FLASH_FEED, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    flash = parse_flash_feed(r.text)

    bf_identity = []
    for b in bf_fixtures:
        bh, ba = split_match(b.get("match"))
        bf_identity.append((b, norm(bh), norm(ba)))

    candidates = []
    horizon = now + timedelta(hours=MAX_HOURS)
    for ev in flash:
        if not ev["start_ts"]:
            continue
        dt = datetime.fromtimestamp(ev["start_ts"], tz=timezone.utc)
        if dt < now - timedelta(minutes=10) or dt > horizon:
            continue
        eh, ea = norm(ev["home"]), norm(ev["away"])
        best = None
        for b, bh, ba in bf_identity:
            sh, sa = similarity_norm(eh, bh), similarity_norm(ea, ba)
            score = (sh + sa) / 2.0
            if min(sh, sa) >= 0.76 and (best is None or score > best[0]):
                best = (score, b)
        if best:
            candidates.append((ev["start_ts"], best[0], ev, best[1]))

    candidate_fixture_count_before_cap = len(candidates)
    candidates.sort(key=lambda x: (fixture_priority(x[3]), x[0]))
    candidates = candidates[:MAX_FIXTURES]

    fixtures_out = []
    all_signals = []
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        future_map = {executor.submit(process_candidate, c): c for c in candidates}
        for future in as_completed(future_map):
            try:
                entry, signals = future.result()
            except Exception as exc:
                c = future_map[future]
                _, match_score, ev, bf_ev = c
                entry = {
                    "flashscore_event_id": ev["event_id"],
                    "betflag_event_id": bf_ev.get("match_event_id"),
                    "match": bf_ev.get("match"),
                    "league": bf_ev.get("league"),
                    "match_score": round(match_score, 3),
                    "start_ts": ev["start_ts"],
                    "priority_tier": fixture_priority(bf_ev)[0],
                    "markets": [],
                    "error": repr(exc),
                }
                signals = []
            fixtures_out.append(entry)
            all_signals.extend(signals)

    fixtures_out.sort(key=lambda x: (x.get("start_ts") or 0, x.get("match") or ""))
    all_signals.sort(key=lambda x: -x["information_move_score"])
    finished = datetime.now(timezone.utc)
    duration_seconds = round((finished - started).total_seconds(), 3)

    common = {
        "schema_version": "radar-information-move-v4",
        "generated_at": finished.isoformat(),
        "source": "Flashscore/Diretta odds comparison historical opening + current",
        "primary_bookmaker": "GoldBet",
        "source_provenance": "GOLDBET_VIA_FLASHSCORE_HISTORICAL",
        "italy_odds_query": {"hash": "oce", "projectId": 2, "geoIpCode": "IT", "geoIpSubdivisionCode": "IT"},
        "policy": {
            "automatic_bet_from_move": False,
            "radar_probability_auto_adjustment": False,
            "final_gate_required": True,
            "advantage_definition": "Radar model agrees + strong cross-book information move + BetFlag price lag + BetFlag exact price clears unchanged final gate",
            "min_books": MIN_BOOKS,
            "min_consensus_ratio": MIN_CONSENSUS,
            "max_hours": MAX_HOURS,
            "max_fixtures": MAX_FIXTURES,
            "parallel_workers": PARALLEL_WORKERS,
            "fixture_priority": "tier0=full scan/player coverage; tier1=standard_count>=35; tier2=remaining fixtures",
        },
        "performance": {
            "duration_seconds": duration_seconds,
            "parallel_workers": PARALLEL_WORKERS,
            "request_timeout_connect_seconds": REQUEST_TIMEOUT[0],
            "request_timeout_read_seconds": REQUEST_TIMEOUT[1],
        },
        "betflag_index_generated_at": bf.get("generated_at"),
        "candidate_fixture_count_before_cap": candidate_fixture_count_before_cap,
        "candidate_fixture_count": len(candidates),
        "processed_fixture_count": len(fixtures_out),
        "likely_information_move_count": len(all_signals),
        "signals": all_signals,
    }

    if not fixtures_out:
        raise RuntimeError("No movement fixtures produced; preserving previous current feed")

    detail = dict(common)
    detail["feed_mode"] = "WORKING_DETAIL_NOT_PUBLISHED"
    detail["fixtures"] = fixtures_out
    compact = dict(common)
    compact["feed_mode"] = "COMPACT_OPERATIONAL"
    compact["fixtures"] = [compact_fixture(x) for x in fixtures_out]

    atomic_write_json(DETAIL_WORK, detail)
    atomic_write_json(OUT, compact)

    print(json.dumps({
        "duration_seconds": duration_seconds,
        "candidate_fixture_count_before_cap": candidate_fixture_count_before_cap,
        "processed_fixture_count": len(fixtures_out),
        "likely_information_move_count": len(all_signals),
        "operational_feed_bytes": OUT.stat().st_size,
        "detail_work_bytes": DETAIL_WORK.stat().st_size,
        "top_signals": all_signals[:10],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
