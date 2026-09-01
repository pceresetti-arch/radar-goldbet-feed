#!/usr/bin/env python3
"""Exact-ID GoldBet TRUE OPEN -> T-30 -> outcome pilot.

Anti-hindsight:
- fixture identity is Flashscore event id only;
- prices are GoldBet same-bookmaker snapshots captured before kickoff;
- T-30 must be an actual persisted checkpoint/snapshot within +/-5 minutes;
- outcome is fetched after the match and joined only after price features are frozen;
- post-kickoff snapshots are never read as candidate prices.
"""
from __future__ import annotations
import hashlib, json, math, re, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "feed/goldbet-diretta-movement-state.json"
OUT = ROOT / "feed/historical/open-close/goldbet-t30-outcome-pilot-v1.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "x-fsign": "SW9D1eZo",
    "referer": "https://www.flashscore.com/",
}
PRIMARY = {"HOME_DRAW_AWAY", "OVER_UNDER", "BOTH_TEAMS_TO_SCORE"}

def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def parse_score(raw: bytes):
    text = raw.decode("utf-8", "replace")
    periods = []
    for section in text.split("~"):
        fields = {}
        for part in section.split("¬"):
            if "÷" in part:
                k, v = part.split("÷", 1)
                fields[k] = v
        if fields.get("AC") in {"1st Half", "2nd Half"}:
            try:
                periods.append({"period": fields["AC"], "home": int(fields["IG"]), "away": int(fields["IH"])})
            except (KeyError, ValueError):
                pass
    by = {p["period"]: p for p in periods}
    if set(by) != {"1st Half", "2nd Half"}:
        return None, periods
    return (by["1st Half"]["home"] + by["2nd Half"]["home"],
            by["1st Half"]["away"] + by["2nd Half"]["away"]), periods

def verified_pre_kickoff(rec, captured, mins):
    if mins is None or mins < 0 or not captured or not rec.get("start_time"):
        return False
    try:
        return datetime.fromisoformat(captured.replace("Z", "+00:00")) < datetime.fromisoformat(rec["start_time"].replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False

def checkpoint_t30(rec):
    candidates = []
    for name, cp in (rec.get("checkpoints") or {}).items():
        if not isinstance(cp, dict):
            continue
        mins = cp.get("minutes_to_start")
        price = cp.get("price")
        if mins is None:
            m = re.search(r"(\d+(?:\.\d+)?)", str(name))
            mins = float(m.group(1)) if m else None
        try:
            mins, price = float(mins), float(price)
        except (TypeError, ValueError):
            continue
        target = cp.get("target_minutes")
        is_t30 = str(name).upper().replace("_", "-") == "T-30" or target == 30
        # Preserve the watcher checkpoint classification. A T-30 fallback can
        # be slightly outside +/-5 minutes; exact distance and quality remain explicit.
        captured = cp.get("captured_at")
        if is_t30 and abs(mins-30) <= 10 and verified_pre_kickoff(rec, captured, mins):
            candidates.append((abs(mins-30), mins, price, captured,
                               f"checkpoint:{name}:{cp.get('quality','UNCLASSIFIED')}"))
    for s in rec.get("snapshots") or []:
        try:
            mins, price = float(s["minutes_to_start"]), float(s["price"])
        except (KeyError, TypeError, ValueError):
            continue
        captured = s.get("captured_at")
        if 25 <= mins <= 35 and verified_pre_kickoff(rec, captured, mins):
            candidates.append((abs(mins-30), mins, price, captured, "snapshot"))
    if not candidates:
        return None
    _, mins, price, captured, source = min(candidates)
    return {"price": price, "minutes_to_start": mins, "captured_at": captured, "source": source}

def won(rec, hg, ag):
    market, sel = rec.get("market"), rec.get("selection")
    if market == "HOME_DRAW_AWAY":
        result = "HOME" if hg > ag else "AWAY" if ag > hg else "DRAW"
        return sel == result
    if market == "OVER_UNDER":
        line = rec.get("line")
        if line is None: return None
        total = hg + ag
        if math.isclose(total, float(line)): return None
        return (total > float(line)) if sel == "OVER" else (total < float(line))
    if market == "BOTH_TEAMS_TO_SCORE":
        yes = hg > 0 and ag > 0
        return yes if sel in {"YES", "GOAL"} else (not yes) if sel in {"NO", "NO_GOAL"} else None
    return None

def main():
    raw_state = STATE.read_bytes()
    state = json.loads(raw_state)
    records = list((state.get("records") or {}).values())
    events = {}
    for r in records:
        events.setdefault(r["flashscore_event_id"], {
            "event": r.get("event"), "start_time": r.get("start_time"), "tournament": r.get("tournament")
        })

    outcomes = {}
    failures = []
    for eid, meta in events.items():
        url = f"https://www.flashscore.com/x/feed/df_sui_1_{eid}"
        try:
            raw = fetch(url)
            score, periods = parse_score(raw)
            if score is None:
                failures.append({"flashscore_event_id": eid, "reason": "two_regular_halves_not_parseable",
                                 "sha256": hashlib.sha256(raw).hexdigest()})
                continue
            outcomes[eid] = {"home_goals": score[0], "away_goals": score[1],
                             "periods": periods, "endpoint": url,
                             "raw_sha256": hashlib.sha256(raw).hexdigest()}
        except Exception as e:
            failures.append({"flashscore_event_id": eid, "reason": type(e).__name__ + ":" + str(e)})

    frozen = []
    groups = defaultdict(list)
    for r in records:
        if r.get("true_open_status") != "TRUE_OPEN_CERTIFIED" or r.get("market") not in PRIMARY:
            continue
        t30 = checkpoint_t30(r)
        if not t30 or r["flashscore_event_id"] not in outcomes:
            continue
        groups[(r["flashscore_event_id"], r.get("market"), r.get("period"), str(r.get("line")))].append((r,t30))

    for gkey, rows in groups.items():
        open_over = sum(1/float(r["true_open_price"]) for r,_ in rows)
        t30_over = sum(1/float(t["price"]) for _,t in rows)
        if open_over <= 0 or t30_over <= 0:
            continue
        for r,t in rows:
            out = outcomes[r["flashscore_event_id"]]
            open_p = (1/float(r["true_open_price"])) / open_over
            t30_p = (1/float(t["price"])) / t30_over
            result = won(r, out["home_goals"], out["away_goals"])
            frozen.append({
                "flashscore_event_id": r["flashscore_event_id"], "event": r.get("event"),
                "tournament": r.get("tournament"), "start_time": r.get("start_time"),
                "market": r.get("market"), "period": r.get("period"), "line": r.get("line"),
                "selection": r.get("selection"), "true_open_price": float(r["true_open_price"]),
                "t30_price": t["price"], "t30_minutes_to_start": t["minutes_to_start"],
                "t30_captured_at": t["captured_at"], "t30_source": t["source"],
                "open_devig_probability": round(open_p, 8),
                "t30_devig_probability": round(t30_p, 8),
                "movement_probability_pp": round((t30_p-open_p)*100, 6),
                "home_goals": out["home_goals"], "away_goals": out["away_goals"],
                "won": result,
            })

    thresholds = []
    for pp in (1.0, 2.0, 3.0):
        selected = [x for x in frozen if x["movement_probability_pp"] >= pp and x["won"] is not None]
        profit = sum((x["t30_price"]-1) if x["won"] else -1 for x in selected)
        thresholds.append({
            "shortening_threshold_pp": pp, "selection_rows": len(selected),
            "fixture_count": len({x["flashscore_event_id"] for x in selected}),
            "wins": sum(bool(x["won"]) for x in selected),
            "hit_rate": round(sum(bool(x["won"]) for x in selected)/len(selected), 6) if selected else None,
            "flat_stake_roi_at_t30": round(profit/len(selected), 6) if selected else None,
            "decision": "DIAGNOSTIC_ONLY_TINY_SAMPLE_NO_PROMOTION",
        })

    event_rows = []
    for eid, meta in events.items():
        event_rows.append({**meta, "flashscore_event_id": eid, "outcome": outcomes.get(eid),
                           "t30_record_count": sum(x["flashscore_event_id"] == eid for x in frozen)})

    report = {
        "schema_version": "radar-goldbet-t30-outcome-pilot-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methodology": {
            "identity_join": "EXACT_FLASHSCORE_EVENT_ID",
            "bookmaker": "GoldBet", "same_bookmaker": True,
            "opening": "TRUE_OPEN_CERTIFIED",
            "t30_definition": "persisted T-30 checkpoint within +/-10 minutes (quality retained), otherwise snapshot within +/-5 minutes; both minutes_to_start >= 0 and captured_at < kickoff are mandatory",
            "outcome_join_order": "price features frozen before outcome attachment",
            "post_kickoff_prices_used": False,
            "limitations": [
                "Only fixtures present in the persisted movement-state archive are eligible.",
                "This pilot is too small for threshold inference, calibration, or promotion.",
                "T-30 is an observed checkpoint, not a certified final close."
            ],
        },
        "source_state": {"path": str(STATE.relative_to(ROOT)), "sha256": hashlib.sha256(raw_state).hexdigest(),
                         "record_count": len(records), "event_count": len(events)},
        "coverage": {
            "exact_outcomes": len(outcomes), "outcome_failures": len(failures),
            "events_with_eligible_t30_rows": len({x["flashscore_event_id"] for x in frozen}),
            "eligible_t30_selection_rows": len(frozen),
        },
        "events": event_rows, "outcome_failures": failures,
        "threshold_diagnostics": thresholds,
        "rows": frozen,
        "decision": "NO_RULE_PROMOTED_SAMPLE_INSUFFICIENT",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["coverage"], ensure_ascii=False))

if __name__ == "__main__":
    main()
