#!/usr/bin/env python3
"""Normalize the live residential BetFlag fixture index for the deep-readiness builder.

This adapter is deliberately lossless for identity and freshness metadata. It prevents the
readiness gate from relying on a stale main-branch aggregate when fresher data exists on
`betflag-live`.
"""
import json
import pathlib
import sys

FEED = pathlib.Path("feed")
SRC = FEED / "betflag-residential-fixtures-index.json"
DST = FEED / "betflag-fixtures-index.json"

if not SRC.exists():
    print(f"missing live BetFlag index: {SRC}", file=sys.stderr)
    raise SystemExit(2)

try:
    raw = json.loads(SRC.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"invalid live BetFlag index: {exc}", file=sys.stderr)
    raise SystemExit(3)

if not raw.get("source_healthy"):
    print("live BetFlag index is not healthy", file=sys.stderr)
    raise SystemExit(4)

fixtures = []
for row in raw.get("fixtures") or []:
    if not isinstance(row, dict):
        continue
    ids = [str(x) for x in (row.get("match_market_ids") or []) if x not in (None, "")]
    props = int(row.get("player_props_count") or 0)
    fixtures.append({
        "match": row.get("match"),
        "match_start": row.get("match_start"),
        "match_market_id": ids[0] if ids else None,
        "match_market_ids": ids,
        "standard_count": int(row.get("standard_count") or 0),
        # Compatibility fields consumed by build_deep_analysis_readiness.py.
        "player_count": props,
        "player_quote_count": props,
        "player_props_count": props,
        "identity_consistent": bool(row.get("identity_consistent")),
        "price_gate_fixture_eligible": bool(row.get("price_gate_fixture_eligible")),
        "file": row.get("file"),
        # Preserve movement evidence only when the live producer explicitly supplies it.
        "movement_certification": row.get("movement_certification"),
        "movement_status": row.get("movement_status"),
    })

out = {
    "schema_version": "radar-betflag-readiness-index-v2-live-adapter",
    "generated_at": raw.get("generated_at"),
    "player_source_generated_at": raw.get("player_source_generated_at"),
    "standard_source_generated_at": raw.get("standard_source_generated_at"),
    "source_class": raw.get("source_class") or "BETFLAG_AAMS_DIRECT",
    "source_healthy": bool(raw.get("source_healthy")),
    "fixture_count": len(fixtures),
    "gate_eligible_fixture_count": sum(1 for x in fixtures if x["price_gate_fixture_eligible"]),
    "runtime_branch": "betflag-live",
    "runtime_source_file": str(SRC),
    "fixtures": fixtures,
}

DST.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
print(f"hydrated {len(fixtures)} live BetFlag fixtures -> {DST}")
