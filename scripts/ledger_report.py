#!/usr/bin/env python3
"""Radar Unico ledger reporting utility.

Reads data/ledger/YYYY-MM-DD.json files and produces historical performance
summaries over arbitrary date ranges. Standard-library only.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER_DIR = ROOT / "data" / "ledger"
BANKROLL_STATE = LEDGER_DIR / "bankroll_state.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_day(name: str) -> date | None:
    try:
        return date.fromisoformat(Path(name).stem)
    except ValueError:
        return None


def iter_ledgers(start: date | None, end: date | None):
    for path in sorted(LEDGER_DIR.glob("????-??-??.json")):
        day = parse_day(path.name)
        if day is None:
            continue
        if start and day < start:
            continue
        if end and day > end:
            continue
        yield day, path, load_json(path)


def bet_pl(bet: dict[str, Any]) -> float:
    if "pl_eur" in bet:
        return float(bet["pl_eur"])
    stake = float(bet.get("stake_eur", 0) or 0)
    ret = float(bet.get("return_eur", 0) or 0)
    return ret - stake


def report(start: date | None, end: date | None) -> dict[str, Any]:
    bets: list[dict[str, Any]] = []
    daily: list[dict[str, Any]] = []
    status_counts = Counter()
    by_market = defaultdict(lambda: {"bets": 0, "stake": 0.0, "pl": 0.0})
    by_bookmaker = defaultdict(lambda: {"bets": 0, "stake": 0.0, "pl": 0.0})

    for day, path, ledger in iter_ledgers(start, end):
        day_bets = ledger.get("bets", [])
        d_stake = d_returns = d_pl = 0.0
        for raw in day_bets:
            bet = dict(raw)
            bet["date"] = day.isoformat()
            bet["ledger"] = str(path.relative_to(ROOT))
            stake = float(bet.get("stake_eur", 0) or 0)
            ret = float(bet.get("return_eur", 0) or 0)
            pl = bet_pl(bet)
            d_stake += stake
            d_returns += ret
            d_pl += pl
            status = str(bet.get("status", "UNKNOWN")).upper()
            status_counts[status] += 1
            market = str(bet.get("market", "UNKNOWN"))
            bookmaker = str(bet.get("bookmaker", "UNKNOWN"))
            by_market[market]["bets"] += 1
            by_market[market]["stake"] += stake
            by_market[market]["pl"] += pl
            by_bookmaker[bookmaker]["bets"] += 1
            by_bookmaker[bookmaker]["stake"] += stake
            by_bookmaker[bookmaker]["pl"] += pl
            bets.append(bet)
        daily.append({
            "date": day.isoformat(),
            "bets": len(day_bets),
            "stake_eur": round(d_stake, 2),
            "returns_eur": round(d_returns, 2),
            "pl_eur": round(d_pl, 2),
            "roi_pct": round((d_pl / d_stake * 100), 2) if d_stake else None,
        })

    stake = sum(float(b.get("stake_eur", 0) or 0) for b in bets)
    returns = sum(float(b.get("return_eur", 0) or 0) for b in bets)
    pl = sum(bet_pl(b) for b in bets)
    settled = status_counts["WON"] + status_counts["LOST"]
    hit_rate = (status_counts["WON"] / settled * 100) if settled else None

    current_bankroll = None
    if BANKROLL_STATE.exists():
        current_bankroll = load_json(BANKROLL_STATE).get("bankroll_eur")

    def finalize(group: dict[str, dict[str, float]]):
        out = {}
        for key, v in sorted(group.items()):
            s = v["stake"]
            out[key] = {
                "bets": int(v["bets"]),
                "stake_eur": round(s, 2),
                "pl_eur": round(v["pl"], 2),
                "roi_pct": round(v["pl"] / s * 100, 2) if s else None,
            }
        return out

    return {
        "range": {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None},
        "summary": {
            "bets": len(bets),
            "stake_eur": round(stake, 2),
            "returns_eur": round(returns, 2),
            "pl_eur": round(pl, 2),
            "roi_pct": round(pl / stake * 100, 2) if stake else None,
            "wins": status_counts["WON"],
            "losses": status_counts["LOST"],
            "void_push_cancelled": status_counts["VOID"] + status_counts["PUSH"] + status_counts["CANCELLED"],
            "open_pending": status_counts["OPEN"] + status_counts["PENDING"],
            "hit_rate_pct": round(hit_rate, 2) if hit_rate is not None else None,
            "current_bankroll_eur": current_bankroll,
        },
        "daily": daily,
        "by_market": finalize(by_market),
        "by_bookmaker": finalize(by_bookmaker),
        "bets": bets,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=date.fromisoformat)
    p.add_argument("--end", type=date.fromisoformat)
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    data = report(args.start, args.end)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
