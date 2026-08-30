#!/usr/bin/env python3
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SRC = ROOT / "feed" / "information-move-current.json"
DETAIL_SRC = ROOT / "feed" / ".information-move-detail-working.json"
OUT = ROOT / "feed" / "market-xg-shift-current.json"

MIN_BOOKS = 4
PREFERRED_TOTAL_LINE = 2.5
MAX_RAW_TEAM_DELTA = 0.75
MAX_RADAR_ADJUSTMENT = 0.25


def f(v):
    try:
        return float(v)
    except Exception:
        return None


def median_price(book_moves, field):
    vals = [f(x.get(field)) for x in book_moves or []]
    vals = [x for x in vals if x and x > 1.0]
    return statistics.median(vals) if vals else None


def normalize_probs(odds):
    inv = [1.0 / x for x in odds]
    s = sum(inv)
    return [x / s for x in inv] if s > 0 else None


def poisson_probs(lam, max_goals=12):
    p = [math.exp(-lam)]
    for k in range(1, max_goals + 1):
        p.append(p[-1] * lam / k)
    tail = max(0.0, 1.0 - sum(p))
    p[-1] += tail
    return p


def model_probs(lh, la, total_line=2.5):
    ph = poisson_probs(lh)
    pa = poisson_probs(la)
    home = draw = away = over = 0.0
    cutoff = int(math.floor(total_line))
    for i, pi in enumerate(ph):
        for j, pj in enumerate(pa):
            p = pi * pj
            if i > j:
                home += p
            elif i == j:
                draw += p
            else:
                away += p
            if i + j > cutoff:
                over += p
    return home, draw, away, over


def solve_xg(target_home, target_draw, target_away, target_over, total_line):
    best = None

    def score(lh, la):
        h, d, a, o = model_probs(lh, la, total_line)
        err = (
            (h - target_home) ** 2
            + (d - target_draw) ** 2
            + (a - target_away) ** 2
            + 1.5 * (o - target_over) ** 2
        )
        return err, (h, d, a, o)

    x = 0.20
    while x <= 4.50 + 1e-9:
        y = 0.20
        while y <= 4.50 + 1e-9:
            err, probs = score(x, y)
            if best is None or err < best[0]:
                best = (err, x, y, probs)
            y += 0.10
        x += 0.10

    _, bh, ba, _ = best
    start_h = max(0.10, bh - 0.16)
    end_h = min(5.00, bh + 0.16)
    start_a = max(0.10, ba - 0.16)
    end_a = min(5.00, ba + 0.16)
    x = start_h
    while x <= end_h + 1e-9:
        y = start_a
        while y <= end_a + 1e-9:
            err, probs = score(x, y)
            if err < best[0]:
                best = (err, x, y, probs)
            y += 0.01
        x += 0.01

    err, lh, la, probs = best
    rmse = math.sqrt(err / 4.5)
    return {
        "lambda_home": round(lh, 3),
        "lambda_away": round(la, 3),
        "lambda_total": round(lh + la, 3),
        "fit_rmse": round(rmse, 4),
        "fitted_probs": {
            "home": round(probs[0], 4),
            "draw": round(probs[1], 4),
            "away": round(probs[2], 4),
            "over": round(probs[3], 4),
        },
    }


def classify(delta):
    if delta >= 0.25:
        return "GOAL_CAPACITY_UP_STRONG"
    if delta >= 0.10:
        return "GOAL_CAPACITY_UP"
    if delta <= -0.25:
        return "GOAL_CAPACITY_DOWN_STRONG"
    if delta <= -0.10:
        return "GOAL_CAPACITY_DOWN"
    return "GOAL_CAPACITY_STABLE"


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def confidence(book_count, fit_rmse, move_strength):
    breadth = clamp((book_count - 3) / 7.0, 0.0, 1.0)
    fit = clamp(1.0 - fit_rmse / 0.08, 0.0, 1.0)
    move = clamp(move_strength / 7.0, 0.0, 1.0)
    return round(0.35 * breadth + 0.40 * fit + 0.25 * move, 3)


def main():
    now = datetime.now(timezone.utc)
    src = DETAIL_SRC if DETAIL_SRC.exists() else PUBLIC_SRC
    data = json.loads(src.read_text(encoding="utf-8"))
    out_rows = []

    for fx in data.get("fixtures") or []:
        markets = fx.get("markets") or []
        by_key = {}
        for m in markets:
            key = (str(m.get("market")), str(m.get("selection")), str(m.get("line")))
            by_key[key] = m

        one_h = by_key.get(("1X2", "HOME", "None"))
        one_d = by_key.get(("1X2", "DRAW", "None"))
        one_a = by_key.get(("1X2", "AWAY", "None"))
        if not all((one_h, one_d, one_a)):
            continue

        total_lines = []
        for m in markets:
            if str(m.get("market")) == "OVER_UNDER" and str(m.get("selection")) == "OVER":
                line = f(m.get("line"))
                if line is None:
                    continue
                under = by_key.get(("OVER_UNDER", "UNDER", str(m.get("line"))))
                if under:
                    total_lines.append((abs(line - PREFERRED_TOTAL_LINE), line, m, under))
        if not total_lines:
            continue
        total_lines.sort(key=lambda x: x[0])
        _, total_line, over_m, under_m = total_lines[0]

        legs = [one_h, one_d, one_a, over_m, under_m]
        book_counts = [len(x.get("book_moves") or []) for x in legs]
        if min(book_counts) < MIN_BOOKS:
            continue

        open_1x2 = [
            median_price(one_h.get("book_moves"), "opening"),
            median_price(one_d.get("book_moves"), "opening"),
            median_price(one_a.get("book_moves"), "opening"),
        ]
        cur_1x2 = [
            median_price(one_h.get("book_moves"), "current"),
            median_price(one_d.get("book_moves"), "current"),
            median_price(one_a.get("book_moves"), "current"),
        ]
        open_ou = [
            median_price(over_m.get("book_moves"), "opening"),
            median_price(under_m.get("book_moves"), "opening"),
        ]
        cur_ou = [
            median_price(over_m.get("book_moves"), "current"),
            median_price(under_m.get("book_moves"), "current"),
        ]
        if any(x is None for x in open_1x2 + cur_1x2 + open_ou + cur_ou):
            continue

        op_1 = normalize_probs(open_1x2)
        cu_1 = normalize_probs(cur_1x2)
        op_ou = normalize_probs(open_ou)
        cu_ou = normalize_probs(cur_ou)
        if not all((op_1, cu_1, op_ou, cu_ou)):
            continue

        opening = solve_xg(op_1[0], op_1[1], op_1[2], op_ou[0], total_line)
        current = solve_xg(cu_1[0], cu_1[1], cu_1[2], cu_ou[0], total_line)

        dh = clamp(current["lambda_home"] - opening["lambda_home"], -MAX_RAW_TEAM_DELTA, MAX_RAW_TEAM_DELTA)
        da = clamp(current["lambda_away"] - opening["lambda_away"], -MAX_RAW_TEAM_DELTA, MAX_RAW_TEAM_DELTA)
        dt = current["lambda_total"] - opening["lambda_total"]

        shift_candidates = [
            abs(f(x.get("median_implied_prob_shift_pp")) or 0.0)
            for x in (one_h, one_a, over_m, under_m)
        ]
        move_strength = max(shift_candidates) if shift_candidates else 0.0
        fit_rmse = max(opening["fit_rmse"], current["fit_rmse"])
        conf = confidence(min(book_counts), fit_rmse, move_strength)

        weight = 0.50 * conf
        adj_h = clamp(dh * weight, -MAX_RADAR_ADJUSTMENT, MAX_RADAR_ADJUSTMENT)
        adj_a = clamp(da * weight, -MAX_RADAR_ADJUSTMENT, MAX_RADAR_ADJUSTMENT)

        out_rows.append({
            "match": fx.get("match"),
            "betflag_event_id": fx.get("betflag_event_id"),
            "start_time_utc": fx.get("start_time_utc"),
            "source": "cross-book opening/current consensus via Diretta/Flashscore",
            "source_feed": src.name,
            "total_line_used": total_line,
            "book_count_floor": min(book_counts),
            "market_probabilities_opening": {
                "home": round(op_1[0], 4),
                "draw": round(op_1[1], 4),
                "away": round(op_1[2], 4),
                "over": round(op_ou[0], 4),
            },
            "market_probabilities_current": {
                "home": round(cu_1[0], 4),
                "draw": round(cu_1[1], 4),
                "away": round(cu_1[2], 4),
                "over": round(cu_ou[0], 4),
            },
            "market_implied_xg_opening": opening,
            "market_implied_xg_current": current,
            "market_xg_delta": {
                "home": round(dh, 3),
                "away": round(da, 3),
                "total": round(dt, 3),
            },
            "home_goal_capacity_signal": classify(dh),
            "away_goal_capacity_signal": classify(da),
            "confidence": conf,
            "recommended_radar_xg_adjustment": {
                "home": round(adj_h, 3),
                "away": round(adj_a, 3),
                "method": "market_delta * (0.50 * confidence), capped at +/-0.25 xG",
                "apply_only_if_base_model_is_independent_of_current_market": True,
            },
            "requires_reanalysis": abs(dh) >= 0.10 or abs(da) >= 0.10,
            "priority_reanalysis": abs(dh) >= 0.20 or abs(da) >= 0.20,
        })

    out_rows.sort(
        key=lambda x: max(abs(x["market_xg_delta"]["home"]), abs(x["market_xg_delta"]["away"])),
        reverse=True,
    )
    out = {
        "schema_version": "radar-market-xg-shift-v1",
        "generated_at": now.isoformat(),
        "input_generated_at": data.get("generated_at"),
        "input_source_file": src.name,
        "definition": "Market-implied change in team scoring capacity derived from de-vigged cross-book 1X2 + nearest full-time O/U line.",
        "policy": {
            "raw_market_xg_replaces_radar_model": False,
            "market_shift_can_trigger_reanalysis": True,
            "market_shift_can_modify_team_xg": True,
            "max_radar_adjustment_per_team": MAX_RADAR_ADJUSTMENT,
            "final_gate_still_required": True,
        },
        "fixture_count": len(out_rows),
        "signals": out_rows,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({
        "input_source_file": src.name,
        "fixture_count": len(out_rows),
        "top": [
            {
                "match": x["match"],
                "delta": x["market_xg_delta"],
                "confidence": x["confidence"],
                "radar_adjustment": x["recommended_radar_xg_adjustment"],
            }
            for x in out_rows[:10]
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
