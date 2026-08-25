#!/usr/bin/env python3
import argparse
import json
import math
import pathlib
from collections import Counter
from datetime import datetime, timezone


def clamp01(v):
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return None


def get_xy(player):
    """FotMob vertical layout: x=lateral, y=depth from own goal.
    Horizontal layout is the same geometry rotated: x=depth, y=lateral.
    """
    v = player.get("vertical_layout") or {}
    x, y = clamp01(v.get("x")), clamp01(v.get("y"))
    source = "vertical_layout"
    if x is None or y is None:
        h = player.get("horizontal_layout") or {}
        x, y = clamp01(h.get("y")), clamp01(h.get("x"))
        source = "horizontal_layout_rotated"
    return x, y, source if x is not None and y is not None else None


def cluster_depth_rows(players, tolerance=0.07):
    rows = []
    for p in sorted((p for p in players if p.get("tactical_y") is not None), key=lambda z: z["tactical_y"]):
        y = p["tactical_y"]
        if not rows or abs(y - rows[-1]["mean_y"]) > tolerance:
            rows.append({"mean_y": y, "players": [p]})
        else:
            rows[-1]["players"].append(p)
            rows[-1]["mean_y"] = sum(x["tactical_y"] for x in rows[-1]["players"]) / len(rows[-1]["players"])
    return rows


def side_bucket(x):
    if x is None:
        return "UNKNOWN"
    if x < 0.34:
        return "LEFT"
    if x > 0.66:
        return "RIGHT"
    return "CENTRE"


def lane_bucket(x):
    if x is None:
        return "UNKNOWN"
    if x < 0.20:
        return "LEFT_WIDE"
    if x < 0.40:
        return "LEFT_HALFSPACE"
    if x <= 0.60:
        return "CENTRAL"
    if x <= 0.80:
        return "RIGHT_HALFSPACE"
    return "RIGHT_WIDE"


def depth_bucket(y):
    if y is None:
        return "UNKNOWN"
    if y <= 0.18:
        return "GOALKEEPER"
    if y < 0.47:
        return "DEFENSIVE_LINE"
    if y < 0.73:
        return "MIDFIELD_LINE"
    return "ATTACKING_LINE"


def slot_labels(prefix, n):
    lookup = {
        1: [prefix],
        2: ["L" + prefix, "R" + prefix],
        3: ["L" + prefix, prefix, "R" + prefix],
        4: ["L" + prefix, "LC" + prefix, "RC" + prefix, "R" + prefix],
        5: ["L" + prefix, "LC" + prefix, "C" + prefix, "RC" + prefix, "R" + prefix],
    }
    return lookup.get(n, [f"{prefix}{i+1}" for i in range(n)])


def infer_roles(rows, formation):
    """Infer functional starting roles from provider geometry + listed formation.
    This is explicitly an inference layer, never a claim of event-tracking truth.
    """
    non_gk = [r for r in rows if r["mean_y"] > 0.18]
    counts = [len(r["players"]) for r in non_gk]
    listed = []
    try:
        listed = [int(x) for x in str(formation or "").split("-") if str(x).isdigit()]
    except Exception:
        listed = []
    shape_match = bool(listed and listed == counts)
    total = len(non_gk)

    for line_idx, row in enumerate(non_gk, start=1):
        ps = sorted(row["players"], key=lambda z: z.get("tactical_x", 0.5))
        n = len(ps)
        is_def = line_idx == 1
        is_att = line_idx == total
        is_penultimate = line_idx == total - 1

        if is_def:
            if n == 3:
                roles = ["LCB", "CB", "RCB"]
                families = ["CB"] * 3
            elif n == 4:
                roles = ["LB", "LCB", "RCB", "RB"]
                families = ["FB", "CB", "CB", "FB"]
            elif n == 5:
                roles = ["LWB", "LCB", "CB", "RCB", "RWB"]
                families = ["WB", "CB", "CB", "CB", "WB"]
            else:
                roles = slot_labels("DEF", n)
                families = ["DEF"] * n
        elif is_att:
            if n == 1:
                roles, families = ["ST"], ["ST"]
            elif n == 2:
                roles, families = ["LST", "RST"], ["ST", "ST"]
            elif n == 3:
                roles, families = ["LW", "ST", "RW"], ["W", "ST", "W"]
            elif n == 4:
                roles, families = ["LW", "LST", "RST", "RW"], ["W", "ST", "ST", "W"]
            else:
                roles, families = slot_labels("ATT", n), ["ATT"] * n
        else:
            # 4-2-3-1 / 3-4-2-1 style: the line immediately behind a single striker
            # is treated as an attacking-midfield line when it has 2-3 players.
            next_count = len(non_gk[line_idx]["players"]) if line_idx < total else 0
            if is_penultimate and next_count == 1 and n == 3:
                roles, families = ["LAM", "AM", "RAM"], ["AM", "AM", "AM"]
            elif is_penultimate and next_count == 1 and n == 2:
                roles, families = ["LAM", "RAM"], ["AM", "AM"]
            elif n == 2:
                roles, families = ["LDM", "RDM"], ["DM", "DM"]
            elif n == 3:
                roles, families = ["LCM", "CM", "RCM"], ["CM", "CM", "CM"]
            elif n == 4 and listed and listed[0] == 3:
                roles, families = ["LWB", "LCM", "RCM", "RWB"], ["WB", "CM", "CM", "WB"]
            elif n == 4:
                roles, families = ["LM", "LCM", "RCM", "RM"], ["WM", "CM", "CM", "WM"]
            elif n == 5:
                roles, families = ["LWB", "LCM", "CM", "RCM", "RWB"], ["WB", "CM", "CM", "CM", "WB"]
            else:
                roles, families = slot_labels("MID", n), ["MID"] * n

        for rank, p in enumerate(ps):
            p["formation_line"] = line_idx
            p["line_size"] = n
            p["line_slot"] = rank + 1
            p["role_code"] = roles[rank]
            p["role_family"] = families[rank]
            p["role_inference_confidence"] = 0.94 if shape_match else 0.82
            p["role_source"] = "provider_layout+listed_formation" if formation else "provider_layout"

    # Goalkeeper(s)
    for r in rows:
        if r["mean_y"] <= 0.18:
            for p in r["players"]:
                p["formation_line"] = 0
                p["line_size"] = len(r["players"])
                p["line_slot"] = 1
                p["role_code"] = "GK"
                p["role_family"] = "GK"
                p["role_inference_confidence"] = 0.99
                p["role_source"] = "provider_layout"

    return counts, listed, shape_match


def enrich_team(team, side):
    starters = []
    for raw in team.get("starters") or []:
        p = dict(raw)
        x, y, coord_source = get_xy(p)
        p["tactical_x"] = None if x is None else round(x, 4)
        p["tactical_y"] = None if y is None else round(y, 4)
        p["coordinate_source"] = coord_source
        p["tactical_side"] = side_bucket(x)
        p["tactical_lane"] = lane_bucket(x)
        p["tactical_depth"] = depth_bucket(y)
        if x is not None and y is not None:
            # Shared physical pitch coordinates: home attacks 0->1, away attacks 1->0.
            cx, cy = (x, y) if side == "HOME" else (1 - x, 1 - y)
            p["common_pitch_x"] = round(cx, 4)
            p["common_pitch_y"] = round(cy, 4)
        else:
            p["common_pitch_x"] = None
            p["common_pitch_y"] = None
        starters.append(p)

    rows = cluster_depth_rows(starters)
    detected, listed, shape_match = infer_roles(rows, team.get("formation"))
    coverage = sum(1 for p in starters if p.get("tactical_x") is not None and p.get("tactical_y") is not None) / max(1, len(starters))
    detected_shape = "-".join(str(x) for x in detected) if detected else None
    return {
        "team_id": team.get("team_id"),
        "team_name": team.get("team_name"),
        "side": side,
        "listed_formation": team.get("formation"),
        "detected_shape": detected_shape,
        "shape_match": shape_match,
        "coordinate_coverage": round(coverage, 3),
        "starters": starters,
        "bench": team.get("bench") or [],
    }


def add_direct_opponents(home, away):
    all_players = home["starters"] + away["starters"]
    by_side = {"HOME": home["starters"], "AWAY": away["starters"]}
    for p in all_players:
        px, py = p.get("common_pitch_x"), p.get("common_pitch_y")
        if px is None or py is None or p.get("role_family") == "GK":
            p["direct_opponents"] = []
            continue
        opp_side = "AWAY" if p in by_side["HOME"] else "HOME"
        candidates = []
        for q in by_side[opp_side]:
            qx, qy = q.get("common_pitch_x"), q.get("common_pitch_y")
            if qx is None or qy is None or q.get("role_family") == "GK":
                continue
            # Lateral separation is weighted more heavily: same-lane duels matter most.
            dist = math.sqrt(((px - qx) * 1.35) ** 2 + (py - qy) ** 2)
            candidates.append((dist, q))
        candidates.sort(key=lambda z: z[0])
        p["direct_opponents"] = [
            {
                "name": q.get("name"),
                "id": q.get("id"),
                "role_code": q.get("role_code"),
                "role_family": q.get("role_family"),
                "zone_distance": round(dist, 4),
            }
            for dist, q in candidates[:2]
        ]


def enrich_match(match):
    line = match.get("lineup") or {}
    teams = line.get("teams") or []
    base = {k: match.get(k) for k in (
        "match_market_id", "match_event_id", "match", "start_time", "start_utc",
        "league", "minutes_to_start", "status", "source", "fotmob_match"
    )}
    if len(teams) < 2:
        return {
            **base,
            "positioning_status": "NO_POSITION_DATA",
            "positioning_confidence": 0.0,
            "provider_source": line.get("provider_source"),
            "lineup_type": line.get("lineup_type"),
            "teams": [],
            "warnings": ["Starting XI/position geometry not available from provider"],
        }

    home = enrich_team(teams[0], "HOME")
    away = enrich_team(teams[1], "AWAY")
    add_direct_opponents(home, away)
    coverage = min(home["coordinate_coverage"], away["coordinate_coverage"])
    xi_complete = all(len(t["starters"]) == 11 for t in (home, away))
    shape_ok = home["shape_match"] and away["shape_match"]

    if xi_complete and coverage >= 0.98 and shape_ok:
        status, conf = "PROVIDER_TACTICAL_CONFIRMED", 0.94
    elif xi_complete and coverage >= 0.90:
        status, conf = "PROVIDER_TACTICAL_AVAILABLE", 0.86
    elif xi_complete:
        status, conf = "XI_WITH_PARTIAL_POSITIONING", 0.68
    else:
        status, conf = "PARTIAL_XI_POSITIONING", 0.50

    warnings = [
        "Tactical role codes are inferred from provider lineup geometry and listed formation; they are not continuous tracking data."
    ]
    if not shape_ok:
        warnings.append("Detected depth-row shape does not exactly match the listed formation; lower role confidence.")
    if coverage < 1:
        warnings.append("Some starters lack provider tactical coordinates.")

    return {
        **base,
        "positioning_status": status,
        "positioning_confidence": conf,
        "provider_source": line.get("provider_source"),
        "lineup_type": line.get("lineup_type"),
        "coordinate_semantics": {
            "provider_vertical_x": "lateral 0=left, 1=right from team perspective",
            "provider_vertical_y": "depth 0=own goal, 1=opponent goal from team perspective",
            "common_pitch": "away x/y mirrored so both teams share one physical-pitch frame",
        },
        "teams": [home, away],
        "warnings": warnings,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="feed/lineups-current.json")
    ap.add_argument("--output", default="feed/lineups-tactical-current.json")
    ap.add_argument("--summary", default="feed/lineups-tactical-current-summary.json")
    args = ap.parse_args()

    src = pathlib.Path(args.input)
    payload = json.loads(src.read_text(encoding="utf-8")) if src.exists() else {"matches": []}
    matches = [enrich_match(m) for m in payload.get("matches", [])]
    counts = Counter(m["positioning_status"] for m in matches)
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_lineup_generated_at": payload.get("generated_at"),
        "source_strategy": "FotMob XI + provider tactical layout; deterministic role/zone enrichment",
        "method_version": "tactical-position-v1",
        "match_count": len(matches),
        "positioning_status_counts": dict(counts),
        "matches": matches,
    }
    pathlib.Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: v for k, v in out.items() if k != "matches"}
    summary["matches"] = [
        {
            "match_market_id": m.get("match_market_id"),
            "match": m.get("match"),
            "start_time": m.get("start_time"),
            "positioning_status": m.get("positioning_status"),
            "positioning_confidence": m.get("positioning_confidence"),
            "formations": [t.get("listed_formation") for t in m.get("teams", [])],
            "detected_shapes": [t.get("detected_shape") for t in m.get("teams", [])],
            "coordinate_coverage": [t.get("coordinate_coverage") for t in m.get("teams", [])],
        }
        for m in matches
    ]
    pathlib.Path(args.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
