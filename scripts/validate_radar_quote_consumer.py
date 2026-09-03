#!/usr/bin/env python3
"""Validate the exact BetFlag quote path consumed by Radar runs.

The producer being healthy is not enough: consumers must be able to resolve
index -> fixture file -> markets and the source must remain BetFlag/AAMS direct.
External/cross-brand data is never price-gate eligible.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

BETFLAG_DIRECT_SOURCE = "BETFLAG_AAMS_DIRECT"


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def age_minutes(value, now):
    parsed = parse_dt(value)
    return None if parsed is None else round((now - parsed).total_seconds() / 60, 2)


def norm(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "FILE_NOT_FOUND"
    except json.JSONDecodeError as exc:
        return None, f"INVALID_JSON:{exc.lineno}:{exc.colno}"
    except OSError as exc:
        return None, f"READ_ERROR:{type(exc).__name__}"


def player_quote_count(fixture):
    direct = fixture.get("player_props") or []
    if isinstance(direct, list) and direct:
        return len(direct)
    total = 0
    for player in fixture.get("players") or []:
        for market in player.get("markets") or []:
            total += len(market.get("quotes") or [])
    return total


def validate(index_path, fixture_query=None, max_age_minutes=12.0, now=None):
    now = now or datetime.now(timezone.utc)
    index, index_error = load_json(index_path)
    result = {
        "schema_version": "radar-quote-consumer-health-v2",
        "generated_at": now.isoformat(),
        "status": "BETFLAG_PATH_READ_FAILURE",
        "current_quote_status": "QUOTA_CURRENT_NON_RECUPERATA",
        "failure_stage": "INDEX",
        "read_contract": {
            "repository": "pceresetti-arch/radar-goldbet-feed",
            "branch": "main",
            "required_source_class": BETFLAG_DIRECT_SOURCE,
            "index": str(index_path).replace("\\", "/"),
            "resolution": "read BetFlag index -> use fixture.file exactly -> read fixture -> use BetFlag current prices only",
            "external_price_fallback_allowed": False,
        },
        "fixture_query": fixture_query,
        "validated_fixture_count": 0,
        "fixtures": [],
        "failures": [],
    }
    if index_error:
        result["failures"].append({"stage": "INDEX", "error": index_error})
        return result

    result["index_generated_at"] = index.get("generated_at")
    result["index_age_minutes"] = age_minutes(index.get("generated_at"), now)
    result["index_source_healthy"] = bool(index.get("source_healthy"))
    result["index_operationally_usable"] = index.get("operationally_usable")
    result["index_fixture_count"] = int(index.get("fixture_count") or 0)
    result["index_source_class"] = index.get("source_class")
    result["price_gate_source_eligible"] = result["index_source_class"] == BETFLAG_DIRECT_SOURCE

    if result["index_source_class"] != BETFLAG_DIRECT_SOURCE:
        result["failures"].append({
            "stage": "SOURCE_PROVENANCE",
            "error": "NON_BETFLAG_OPERATIONAL_SOURCE",
            "observed_source_class": result["index_source_class"],
            "required_source_class": BETFLAG_DIRECT_SOURCE,
        })
    if not result["index_source_healthy"]:
        result["failures"].append({"stage": "INDEX", "error": "SOURCE_UNHEALTHY"})
    if result["index_operationally_usable"] is False:
        result["failures"].append({"stage": "INDEX", "error": "NOT_OPERATIONALLY_USABLE"})
    age = result["index_age_minutes"]
    if age is None or age > max_age_minutes:
        result["failures"].append({"stage": "INDEX", "error": "STALE_INDEX", "age_minutes": age})

    fixtures = index.get("fixtures") or []
    if fixture_query:
        needle = norm(fixture_query)
        exact = [row for row in fixtures if norm(row.get("match")) == needle]
        candidates = exact or [row for row in fixtures if needle in norm(row.get("match"))]
        if not candidates:
            result["failure_stage"] = "FIXTURE_LOOKUP"
            result["failures"].append({"stage": "FIXTURE_LOOKUP", "error": "FIXTURE_NOT_FOUND"})
            return result
        fixtures = candidates

    if not fixtures and not result["failures"]:
        result.update(
            status="NO_PREMATCH_FIXTURES_AVAILABLE",
            current_quote_status="NESSUNA_FIXTURE_PREMATCH",
            failure_stage=None,
        )
        return result

    root = index_path.parent.parent if index_path.parent.name == "feed" else index_path.parent
    for row in fixtures:
        rel = row.get("file")
        if not rel:
            result["failures"].append({"stage": "FIXTURE_FILE", "match": row.get("match"), "error": "MISSING_FILE_POINTER"})
            continue
        path = root / rel
        fixture, error = load_json(path)
        if error:
            result["failures"].append({"stage": "FIXTURE_FILE", "match": row.get("match"), "file": rel, "error": error})
            continue
        standard_count = len(fixture.get("standard") or [])
        pquote_count = player_quote_count(fixture)
        identity_ok = norm(fixture.get("match")) == norm(row.get("match"))
        healthy = bool(fixture.get("source_healthy", index.get("source_healthy")))
        fixture_source_class = fixture.get("source_class", index.get("source_class"))
        source_ok = fixture_source_class == BETFLAG_DIRECT_SOURCE
        eligible = fixture.get("price_gate_fixture_eligible")
        if eligible is None:
            eligible = healthy and identity_ok and source_ok and (standard_count > 0 or pquote_count > 0)
        else:
            eligible = bool(eligible) and source_ok
        item = {
            "match": row.get("match"),
            "file": rel,
            "identity_consistent": identity_ok,
            "source_healthy": healthy,
            "source_class": fixture_source_class,
            "source_provenance_eligible": source_ok,
            "price_gate_fixture_eligible": bool(eligible),
            "standard_count": standard_count,
            "player_quote_count": pquote_count,
        }
        result["fixtures"].append(item)
        if not source_ok:
            result["failures"].append({
                "stage": "SOURCE_PROVENANCE",
                "match": row.get("match"),
                "file": rel,
                "error": "NON_BETFLAG_OPERATIONAL_SOURCE",
                "observed_source_class": fixture_source_class,
            })
        elif not identity_ok:
            result["failures"].append({"stage": "FIXTURE_IDENTITY", "match": row.get("match"), "file": rel, "error": "IDENTITY_MISMATCH"})
        elif not healthy:
            result["failures"].append({"stage": "FIXTURE_HEALTH", "match": row.get("match"), "file": rel, "error": "SOURCE_UNHEALTHY"})
        elif standard_count <= 0 and pquote_count <= 0:
            result["failures"].append({"stage": "MARKETS", "match": row.get("match"), "file": rel, "error": "NO_CURRENT_QUOTES"})
        else:
            result["validated_fixture_count"] += 1

    if result["failures"]:
        result["failure_stage"] = result["failures"][0]["stage"]
        return result

    result.update(
        status="READY",
        current_quote_status="CURRENT_BETFLAG_RECUPERATA",
        failure_stage=None,
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="feed/betflag-fixtures-index.json")
    parser.add_argument("--fixture")
    parser.add_argument("--max-age-minutes", type=float, default=12.0)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    result = validate(Path(args.index), args.fixture, args.max_age_minutes)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["status"] in {"READY", "NO_PREMATCH_FIXTURES_AVAILABLE"} else 1


if __name__ == "__main__":
    sys.exit(main())
