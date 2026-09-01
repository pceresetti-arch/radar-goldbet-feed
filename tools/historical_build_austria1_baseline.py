#!/usr/bin/env python3
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RAW = Path("feed/historical/austria1/football-data-AUT.csv")
OUT = Path("feed/historical/austria1")
NORMALIZED = OUT / "austrian-bundesliga-2022-2026-regular.csv"
REPORT = OUT / "baseline-benchmark.json"
SEASONS = ["2022/2023", "2023/2024", "2024/2025", "2025/2026"]
DEVELOPMENT = {"2022/2023", "2023/2024", "2024/2025"}
HOLDOUT = {"2025/2026"}
TEAM_ALIASES = {}

def iso_date(value):
    return datetime.strptime(value.strip(), "%d/%m/%Y").date().isoformat()

def f(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def probabilities(odds):
    inv = [1.0 / x for x in odds]
    total = sum(inv)
    return [x / total for x in inv], total

def metrics(rows, probs_fn):
    brier_sum = log_sum = 0.0
    correct = 0
    n = 0
    calibration = {}
    outcomes = ["H", "D", "A"]
    for row in rows:
        probs = probs_fn(row)
        if probs is None:
            continue
        y = outcomes.index(row["result"])
        brier_sum += sum((p - (1.0 if i == y else 0.0)) ** 2 for i, p in enumerate(probs))
        log_sum += -math.log(max(probs[y], 1e-15))
        pick = max(range(3), key=lambda i: probs[i])
        correct += int(pick == y)
        confidence = probs[pick]
        lo = math.floor(confidence * 10) / 10
        key = f"{lo:.1f}-{min(1.0, lo + 0.1):.1f}"
        bucket = calibration.setdefault(key, {"n": 0, "confidence_sum": 0.0, "hits": 0})
        bucket["n"] += 1
        bucket["confidence_sum"] += confidence
        bucket["hits"] += int(pick == y)
        n += 1
    for bucket in calibration.values():
        bucket["mean_confidence"] = bucket.pop("confidence_sum") / bucket["n"]
        bucket["hit_rate"] = bucket["hits"] / bucket["n"]
    return {
        "n": n,
        "multiclass_brier_sum_mean": brier_sum / n if n else None,
        "multiclass_brier_class_mean": brier_sum / (3 * n) if n else None,
        "log_loss": log_sum / n if n else None,
        "top_pick_accuracy": correct / n if n else None,
        "top_pick_calibration": dict(sorted(calibration.items()))
    }

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with RAW.open("r", encoding="utf-8-sig", newline="") as fh:
        source = list(csv.DictReader(fh))

    alias_corrections = []
    for row in source:
        for side in ("Home", "Away"):
            original = row.get(side, "")
            canonical = TEAM_ALIASES.get(original, original)
            row[f"_source_{side.lower()}"] = original
            row[side] = canonical
            if canonical != original:
                alias_corrections.append({"side": side, "source": original, "canonical": canonical})

    selected = [r for r in source if r.get("Season") in SEASONS and r.get("League") == "Bundesliga"]
    appearances = {}
    for season in SEASONS:
        counts = Counter()
        for r in selected:
            if r["Season"] == season:
                counts[r["Home"]] += 1
                counts[r["Away"]] += 1
        appearances[season] = dict(sorted(counts.items()))

    regular = []
    excluded = []
    regular_teams = {}
    for season in SEASONS:
        season_rows = [r for r in selected if r["Season"] == season]
        season_rows.sort(key=lambda r: (iso_date(r["Date"]), r.get("Time", ""), r["Home"], r["Away"]))
        teams = sorted({r["Home"] for r in season_rows} | {r["Away"] for r in season_rows})
        regular_teams[season] = teams
        accepted_appearances = Counter()
        for r in season_rows:
            if accepted_appearances[r["Home"]] < 32 and accepted_appearances[r["Away"]] < 32:
                regular.append(r)
                accepted_appearances[r["Home"]] += 1
                accepted_appearances[r["Away"]] += 1
            else:
                excluded.append({
                    "season": season, "date": r["Date"], "home": r["Home"], "away": r["Away"],
                    "reason": "CHRONOLOGICALLY_SUBSEQUENT_EUROPEAN_PLAYOFF_AFTER_BALANCED_192_MATCH_CORE"
                })
        if len(teams) != 12 or any(accepted_appearances[t] != 32 for t in teams):
            raise ValueError(f"Austria season integrity failed for {season}: teams={len(teams)}, appearances={dict(accepted_appearances)}")

    regular.sort(key=lambda r: (iso_date(r["Date"]), r.get("Time", ""), r["Home"], r["Away"]))
    fields = [
        "fixture_key", "competition", "season", "split", "source_date", "source_time",
        "source_time_semantics", "kickoff_utc", "kickoff_utc_status",
        "home_team", "away_team", "home_goals", "away_goals", "result",
        "outcome_usage", "avg_close_home", "avg_close_draw", "avg_close_away",
        "close_source_class", "open_price_status", "goldbet_status", "source_row_sha256"
    ]
    normalized = []
    for r in regular:
        canonical = "|".join(r.get(k, "") for k in ["Country", "League", "Season", "Date", "Time", "Home", "Away"])
        normalized.append({
            "fixture_key": hashlib.sha256(canonical.encode()).hexdigest()[:24],
            "competition": "Bundesliga",
            "season": r["Season"],
            "split": "DEVELOPMENT" if r["Season"] in DEVELOPMENT else "HOLDOUT",
            "source_date": iso_date(r["Date"]),
            "source_time": r.get("Time", ""),
            "source_time_semantics": "MATCH_KICKOFF_TIME_TIMEZONE_NOT_STATED_BY_SOURCE",
            "kickoff_utc": "",
            "kickoff_utc_status": "NOT_VERIFIED_DO_NOT_INFER",
            "home_team": r["Home"],
            "away_team": r["Away"],
            "home_goals": r["HG"],
            "away_goals": r["AG"],
            "result": r["Res"],
            "outcome_usage": "EVALUATION_ONLY_JOIN_AFTER_PREMATCH_FEATURE_FREEZE",
            "avg_close_home": r["AvgCH"],
            "avg_close_draw": r["AvgCD"],
            "avg_close_away": r["AvgCA"],
            "close_source_class": "EXTERNAL_HISTORICAL_MARKET_BENCHMARK",
            "open_price_status": "NOT_AVAILABLE",
            "goldbet_status": "NOT_GOLDBET",
            "source_row_sha256": hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()
        })

    with NORMALIZED.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(normalized)

    dev = [r for r in normalized if r["split"] == "DEVELOPMENT"]
    holdout = [r for r in normalized if r["split"] == "HOLDOUT"]
    dev_counts = Counter(r["result"] for r in dev)
    dev_total = sum(dev_counts.values())
    prior = [dev_counts[x] / dev_total for x in ["H", "D", "A"]]

    def prior_probs(row):
        return prior

    def market_probs(row):
        odds = [f(row["avg_close_home"]), f(row["avg_close_draw"]), f(row["avg_close_away"])]
        if any(x is None or x <= 1 for x in odds):
            return None
        return probabilities(odds)[0]

    overrounds = []
    for r in holdout:
        odds = [f(r["avg_close_home"]), f(r["avg_close_draw"]), f(r["avg_close_away"])]
        if all(x is not None and x > 1 for x in odds):
            overrounds.append(probabilities(odds)[1])

    report = {
        "schema_version": "radar-historical-austria1-baseline-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": str(RAW),
        "normalized_dataset": str(NORMALIZED),
        "selection_rule_frozen_before_evaluation": "Latest four completed source seasons 2022/2023-2025/2026; 12-team Superliga with 32 league matches per club; post-season European playoffs excluded chronologically after the 32-match cap.",
        "seasons": SEASONS,
        "split": {"development": sorted(DEVELOPMENT), "holdout": sorted(HOLDOUT)},
        "sample": {
            "source_selected_rows": len(selected),
            "regular_rows": len(normalized),
            "development_rows": len(dev),
            "holdout_rows": len(holdout),
            "excluded_playoff_rows": len(excluded),
            "excluded": excluded,
            "regular_team_counts": {s: len(regular_teams[s]) for s in SEASONS},
            "team_alias_map": TEAM_ALIASES,
            "team_alias_field_corrections": len(alias_corrections),
            "season_match_cap_per_team": 32
        },
        "data_quality": {
            "normalized_duplicate_fixture_keys": len(normalized) - len({r["fixture_key"] for r in normalized}),
            "identity_integrity": "Each frozen season must contain exactly 12 clubs and 32 accepted league matches per club; any subsequent playoff row is excluded chronologically without using its result.",
            "missing_avg_close_triplets": sum(not all(r[x] for x in ["avg_close_home", "avg_close_draw", "avg_close_away"]) for r in normalized),
            "kickoff_utc_verified_rows": 0,
            "kickoff_policy": "No UTC conversion is performed because the source documents Time as kickoff time but does not state timezone. Rolling structural features must use strictly prior source dates, excluding same-date information."
        },
        "development_outcome_prior": {"H": prior[0], "D": prior[1], "A": prior[2]},
        "holdout_metrics": {
            "development_prior_baseline": metrics(holdout, prior_probs),
            "devigged_average_market_close_benchmark": metrics(holdout, market_probs),
            "average_market_close_overround": sum(overrounds) / len(overrounds) if overrounds else None
        },
        "economic_metrics": {
            "clv": "NOT_CALCULABLE_NO_OPEN_PRICE",
            "roi_yield": "NOT_CALCULATED_NO_EX_ANTE_STRATEGY",
            "drawdown": "NOT_CALCULATED_NO_EX_ANTE_STRATEGY"
        },
        "mms": {
            "goldbet_primary_eligible": False,
            "open_to_close_eligible": False,
            "reason": "Only external closing 1X2 benchmark odds are present; no GoldBet TRUE OPEN or same-book OPEN series."
        },
        "rule_decision": "BENCHMARK_ONLY_NO_OPERATIONAL_PROMOTION"
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"regular_rows": len(normalized), "development": len(dev), "holdout": len(holdout), "excluded": len(excluded)}, indent=2))

if __name__ == "__main__":
    main()
