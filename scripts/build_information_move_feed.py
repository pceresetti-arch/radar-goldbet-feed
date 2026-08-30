#!/usr/bin/env python3
import json
import math
import re
import statistics
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
BETFLAG_INDEX = ROOT / "feed" / "betflag-fixtures-index.json"
OUT = ROOT / "feed" / "information-move-current.json"

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
ROME = ZoneInfo("Europe/Rome")
MAX_HOURS = 18
MAX_FIXTURES = 80
MIN_BOOKS = 4
MIN_CONSENSUS = 0.65
PRIORITY_STANDARD_COUNT = 35


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


def similarity(a, b):
    a, b = norm(a), norm(b)
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
    """Prioritize Radar-quality fixtures before minor/reserve fixtures.

    The BetFlag index already exposes coverage depth. Full-scan/player-prop
    fixtures are normally the competitions where the Radar can complete the
    deepest analysis; broad standard-market coverage is the second tier.
    """
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
    # Score is intentionally conservative: movement cannot create a BET by itself.
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


def main():
    now = datetime.now(timezone.utc)
    try:
        bf = json.loads(BETFLAG_INDEX.read_text(encoding="utf-8"))
    except Exception:
        bf = {}
    bf_fixtures = bf.get("fixtures") or []

    sess = requests.Session()
    r = sess.get(FLASH_FEED, headers=HEADERS, timeout=25)
    r.raise_for_status()
    flash = parse_flash_feed(r.text)

    candidates = []
    horizon = now + timedelta(hours=MAX_HOURS)
    for ev in flash:
        if not ev["start_ts"]:
            continue
        dt = datetime.fromtimestamp(ev["start_ts"], tz=timezone.utc)
        if dt < now - timedelta(minutes=10) or dt > horizon:
            continue
        best = None
        for b in bf_fixtures:
            bh, ba = split_match(b.get("match"))
            sh, sa = similarity(ev["home"], bh), similarity(ev["away"], ba)
            score = (sh + sa) / 2.0
            if min(sh, sa) >= 0.76 and (best is None or score > best[0]):
                best = (score, b)
        if best:
            candidates.append((ev["start_ts"], best[0], ev, best[1]))

    candidate_fixture_count_before_cap = len(candidates)
    candidates.sort(key=lambda x: (fixture_priority(x[3]), x[0]))
    candidates = candidates[:MAX_FIXTURES]
    # Keep the output human-friendly after the priority selection.
    candidates.sort(key=lambda x: x[0])

    fixtures_out = []
    all_signals = []

    for _, match_score, ev, bf_ev in candidates:
        params = dict(ITALY_PARAMS)
        params["eventId"] = ev["event_id"]
        priority_tier = fixture_priority(bf_ev)[0]
        entry = {
            "flashscore_event_id": ev["event_id"],
            "betflag_event_id": bf_ev.get("match_event_id"),
            "match": bf_ev.get("match"),
            "league": bf_ev.get("league"),
            "flashscore_match": f"{ev['home']} - {ev['away']}",
            "match_score": round(match_score, 3),
            "start_ts": ev["start_ts"],
            "start_time_utc": datetime.fromtimestamp(ev["start_ts"], tz=timezone.utc).isoformat(),
            "priority_tier": priority_tier,
            "markets": [],
        }
        try:
            rr = sess.get(ODDS_URL, params=params, headers=HEADERS, timeout=25)
            entry["http_status"] = rr.status_code
            if not rr.ok:
                fixtures_out.append(entry)
                continue
            fo = ((rr.json().get("data") or {}).get("findOddsByEventId") or {})
        except Exception as exc:
            entry["error"] = repr(exc)
            fixtures_out.append(entry)
            continue

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

        for (market, selection, line), books in buckets.items():
            gb = next((x for x in books if str(x["bookmaker"]).lower() == "goldbet"), None)
            if not gb:
                continue
            shifts = [x["shift_pp"] for x in books if x.get("shift_pp") is not None]
            if not shifts:
                continue
            gb_pp = gb["shift_pp"]
            # Same-direction consensus is measured against GoldBet's direction.
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
                all_signals.append({
                    "match": entry["match"],
                    "league": entry.get("league"),
                    "betflag_event_id": entry["betflag_event_id"],
                    **{k: rec[k] for k in rec if k != "book_moves"},
                })
        entry["markets"].sort(key=lambda x: -x["information_move_score"])
        fixtures_out.append(entry)
        time.sleep(0.05)

    all_signals.sort(key=lambda x: -x["information_move_score"])
    out = {
        "schema_version": "radar-information-move-v2",
        "generated_at": now.isoformat(),
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
            "fixture_priority": "tier0=full scan/player coverage; tier1=standard_count>=35; tier2=remaining fixtures",
        },
        "betflag_index_generated_at": bf.get("generated_at"),
        "candidate_fixture_count_before_cap": candidate_fixture_count_before_cap,
        "candidate_fixture_count": len(candidates),
        "processed_fixture_count": len(fixtures_out),
        "likely_information_move_count": len(all_signals),
        "signals": all_signals,
        "fixtures": fixtures_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({
        "candidate_fixture_count_before_cap": candidate_fixture_count_before_cap,
        "processed_fixture_count": len(fixtures_out),
        "likely_information_move_count": len(all_signals),
        "top_signals": all_signals[:10],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
