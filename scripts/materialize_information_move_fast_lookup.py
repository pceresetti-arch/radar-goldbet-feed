#!/usr/bin/env python3
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "feed" / "information-move-current.json"
INDEX = ROOT / "feed" / "information-move-index.json"
OUTDIR = ROOT / "feed" / "information-move-fixtures"


def slugify(value: str) -> str:
    s = unicodedata.normalize("NFKD", str(value or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:120]


def slim_market(m):
    keep = (
        "market", "selection", "line",
        "goldbet_opening", "goldbet_current",
        "goldbet_decimal_drop", "goldbet_implied_prob_shift_pp",
        "books_with_open_current", "directional_books",
        "same_direction_count", "consensus_ratio",
        "median_implied_prob_shift_pp", "information_move_score",
        "information_move_class", "likely_information_move",
        "radar_use",
    )
    return {k: m.get(k) for k in keep if k in m}


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    OUTDIR.mkdir(parents=True, exist_ok=True)

    entries = []
    live_slugs = set()
    for fx in data.get("fixtures") or []:
        match = fx.get("match")
        if not match:
            continue
        slug = slugify(match)
        if not slug:
            continue
        live_slugs.add(slug)
        markets = [slim_market(m) for m in (fx.get("markets") or [])]
        markets.sort(key=lambda x: -(x.get("information_move_score") or 0))
        payload = {
            "schema_version": "radar-information-move-fixture-v1",
            "generated_at": data.get("generated_at"),
            "source": data.get("source"),
            "source_provenance": data.get("source_provenance"),
            "match": match,
            "betflag_event_id": fx.get("betflag_event_id"),
            "flashscore_event_id": fx.get("flashscore_event_id"),
            "start_time_utc": fx.get("start_time_utc"),
            "market_count": len(markets),
            "likely_information_move_count": sum(1 for m in markets if m.get("likely_information_move")),
            "markets": markets,
        }
        (OUTDIR / f"{slug}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        top = markets[:5]
        entries.append({
            "match": match,
            "slug": slug,
            "file": f"feed/information-move-fixtures/{slug}.json",
            "betflag_event_id": fx.get("betflag_event_id"),
            "start_time_utc": fx.get("start_time_utc"),
            "market_count": len(markets),
            "likely_information_move_count": payload["likely_information_move_count"],
            "top_moves": top,
        })

    # Remove stale per-fixture files so lookups cannot accidentally use old matches.
    for p in OUTDIR.glob("*.json"):
        if p.stem not in live_slugs:
            p.unlink()

    entries.sort(key=lambda x: (x.get("start_time_utc") or "", x.get("match") or ""))
    idx = {
        "schema_version": "radar-information-move-index-v1",
        "generated_at": data.get("generated_at"),
        "source": data.get("source"),
        "source_provenance": data.get("source_provenance"),
        "fixture_count": len(entries),
        "lookup_policy": "Use this index first, then fetch only the matching per-fixture file. Do not parse information-move-current.json for routine fixture lookups.",
        "fixtures": entries,
    }
    INDEX.write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"fixture_count": len(entries), "index": str(INDEX), "outdir": str(OUTDIR)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
