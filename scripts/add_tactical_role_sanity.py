#!/usr/bin/env python3
import argparse
import json
import pathlib
from collections import Counter

USUAL_GROUP = {
    0: "GK",
    1: "DEF",
    2: "MID",
    3: "FWD",
}

ROLE_ACCEPTS = {
    "GK": {"GK"},
    "CB": {"DEF"},
    "FB": {"DEF"},
    "DEF": {"DEF"},
    "WB": {"DEF", "MID"},
    "DM": {"MID"},
    "CM": {"MID"},
    "MID": {"MID"},
    "WM": {"MID", "FWD"},
    "AM": {"MID", "FWD"},
    "W": {"MID", "FWD"},
    "ST": {"FWD"},
    "ATT": {"FWD"},
}


def classify(player):
    raw = player.get("usual_position_id")
    try:
        raw = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        raw = None
    usual = USUAL_GROUP.get(raw, "UNKNOWN")
    family = player.get("role_family") or "UNKNOWN"
    accepted = ROLE_ACCEPTS.get(family)

    if usual == "UNKNOWN" or not accepted:
        status = "UNKNOWN"
    elif usual not in accepted:
        status = "OUT_OF_USUAL_LINE"
    elif len(accepted) > 1:
        status = "FLEX_ROLE_ALIGNED"
    else:
        status = "ALIGNED"

    player["usual_position_group"] = usual
    player["role_vs_usual"] = status
    player["role_sanity_source"] = "provider_usual_position_id_vs_inferred_tactical_role"
    return status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="feed/lineups-tactical-current.json")
    ap.add_argument("--summary", default="feed/lineups-tactical-current-summary.json")
    args = ap.parse_args()

    path = pathlib.Path(args.input)
    if not path.exists():
        raise SystemExit(f"missing {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    total = Counter()

    for match in payload.get("matches", []):
        mc = Counter()
        for team in match.get("teams", []):
            tc = Counter()
            for p in team.get("starters", []):
                s = classify(p)
                tc[s] += 1
                mc[s] += 1
                total[s] += 1
            team["role_sanity_counts"] = dict(tc)
            team["out_of_usual_line"] = [
                {"id": p.get("id"), "name": p.get("name"), "role_code": p.get("role_code"),
                 "role_family": p.get("role_family"), "usual_position_group": p.get("usual_position_group")}
                for p in team.get("starters", []) if p.get("role_vs_usual") == "OUT_OF_USUAL_LINE"
            ]
        match["role_sanity_counts"] = dict(mc)
        match["out_of_usual_line_count"] = mc.get("OUT_OF_USUAL_LINE", 0)
        if mc.get("OUT_OF_USUAL_LINE", 0) >= 3:
            match.setdefault("warnings", []).append(
                "Multiple starters are outside their provider usual broad position; verify tactical graphic/role before strong spatial conclusions."
            )
            match["positioning_confidence"] = round(max(0.0, float(match.get("positioning_confidence") or 0) - 0.08), 2)

    payload["role_sanity_method"] = "usual-position-v1"
    payload["role_sanity_counts"] = dict(total)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_path = pathlib.Path(args.summary)
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {k: v for k, v in payload.items() if k != "matches"}
        summary["matches"] = []
    summary["role_sanity_method"] = "usual-position-v1"
    summary["role_sanity_counts"] = dict(total)
    by_id = {m.get("match_market_id"): m for m in payload.get("matches", [])}
    for row in summary.get("matches", []):
        m = by_id.get(row.get("match_market_id"))
        if m:
            row["role_sanity_counts"] = m.get("role_sanity_counts", {})
            row["out_of_usual_line_count"] = m.get("out_of_usual_line_count", 0)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"role_sanity_method":"usual-position-v1","role_sanity_counts":dict(total)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
