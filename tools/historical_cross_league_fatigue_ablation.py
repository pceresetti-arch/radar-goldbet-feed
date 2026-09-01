#!/usr/bin/env python3
"""Frozen cross-league OOS ablation for schedule-derived freshness/fatigue."""
import csv
import json
import math
import random
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

OUTCOMES = ["H", "D", "A"]
L2 = 0.01
LEARNING_RATE = 0.08
ITERATIONS = 1800
BOOTSTRAP_DRAWS = 10000
SEED = 20260901

LEAGUES = {
    "sweden": "feed/historical/sweden/allsvenskan-2022-2025-features.csv",
    "norway": "feed/historical/norway/eliteserien-2022-2025-features.csv",
    "denmark": "feed/historical/denmark/superliga-2022-2026-features.csv",
    "netherlands": "feed/historical/netherlands/eredivisie-2022-2026-features.csv",
    "portugal": "feed/historical/portugal/primeira-liga-2022-2026-features.csv",
    "germany2": "feed/historical/germany2/2-bundesliga-2022-2026-features.csv",
    "germany1": "feed/historical/germany1/bundesliga-2022-2026-features.csv",
    "spain1": "feed/historical/spain1/laliga-2022-2026-features.csv",
    "england1": "feed/historical/england1/premier-league-2022-2026-features.csv",
    "scotland1": "feed/historical/scotland1/scottish-premiership-2022-2026-features.csv",
}
OUT = Path("feed/historical/fatigue/cross-league-fatigue-ablation-v1.json")
FATIGUE_FEATURES = [
    "rest_days_diff",
    "matches_prior_7d_diff",
    "matches_prior_14d_diff",
    "matches_prior_21d_diff",
]

def avg(xs):
    return sum(xs) / len(xs) if xs else 0.0

def softmax(scores):
    m = max(scores)
    ex = [math.exp(x - m) for x in scores]
    total = sum(ex)
    return [x / total for x in ex]

def add_schedule_features(rows):
    """Only strictly prior calendar dates are visible; current-day batches update together."""
    history = defaultdict(list)
    by_day = defaultdict(list)
    for row in rows:
        by_day[row["source_date"]].append(row)
    out = []
    for day_text in sorted(by_day):
        current = date.fromisoformat(day_text)
        batch = sorted(by_day[day_text], key=lambda r: (r.get("source_time", ""), r["home_team"], r["away_team"]))
        for row in batch:
            feat = dict(row)
            snapshots = {}
            for side, team in (("home", row["home_team"]), ("away", row["away_team"])):
                prior = history.get(team, [])
                deltas = [(current - d).days for d in prior]
                strictly_prior = [x for x in deltas if x > 0]
                snapshots[side] = {
                    "rest": min(30, min(strictly_prior)) if strictly_prior else None,
                    "m7": sum(1 for x in strictly_prior if x <= 7),
                    "m14": sum(1 for x in strictly_prior if x <= 14),
                    "m21": sum(1 for x in strictly_prior if x <= 21),
                }
            h, a = snapshots["home"], snapshots["away"]
            feat["home_rest_days_capped_30"] = h["rest"]
            feat["away_rest_days_capped_30"] = a["rest"]
            feat["rest_days_diff"] = None if h["rest"] is None or a["rest"] is None else h["rest"] - a["rest"]
            feat["matches_prior_7d_diff"] = h["m7"] - a["m7"]
            feat["matches_prior_14d_diff"] = h["m14"] - a["m14"]
            feat["matches_prior_21d_diff"] = h["m21"] - a["m21"]
            feat["fatigue_same_date_information_used"] = False
            out.append(feat)
        for row in batch:
            history[row["home_team"]].append(current)
            history[row["away_team"]].append(current)
    return out

def prepare(dev, holdout, features):
    means, scales = {}, {}
    for name in features:
        vals = [float(r[name]) for r in dev if r.get(name) not in (None, "")]
        means[name] = avg(vals)
        variance = avg([(x - means[name]) ** 2 for x in vals])
        scales[name] = math.sqrt(variance) if variance > 1e-12 else 1.0
    def vector(row):
        vals = []
        for name in features:
            raw = row.get(name)
            value = means[name] if raw in (None, "") else float(raw)
            vals.append((value - means[name]) / scales[name])
        return [1.0] + vals
    def encoded(rows):
        return [(vector(r), OUTCOMES.index(r["result"])) for r in rows]
    return encoded(dev), encoded(holdout), means, scales

def train(rows, width):
    weights = [[0.0] * width for _ in OUTCOMES]
    n = len(rows)
    for _ in range(ITERATIONS):
        grad = [[0.0] * width for _ in OUTCOMES]
        for x, y in rows:
            probs = softmax([sum(wj * xj for wj, xj in zip(w, x)) for w in weights])
            for k in range(3):
                err = probs[k] - (1.0 if k == y else 0.0)
                for j, xj in enumerate(x):
                    grad[k][j] += err * xj
        for k in range(3):
            for j in range(width):
                penalty = 0.0 if j == 0 else L2 * weights[k][j]
                weights[k][j] -= LEARNING_RATE * (grad[k][j] / n + penalty)
    return weights

def predict(rows, weights):
    return [{"y": y, "probs": softmax([sum(wj * xj for wj, xj in zip(w, x)) for w in weights])} for x, y in rows]

def losses(records):
    return {
        "brier": [sum((p - (1.0 if k == r["y"] else 0.0)) ** 2 for k, p in enumerate(r["probs"])) for r in records],
        "log_loss": [-math.log(max(r["probs"][r["y"]], 1e-15)) for r in records],
    }

def metrics(records):
    lv = losses(records)
    return {
        "n": len(records),
        "multiclass_brier_sum_mean": avg(lv["brier"]),
        "multiclass_brier_class_mean": avg(lv["brier"]) / 3.0,
        "log_loss": avg(lv["log_loss"]),
        "top_pick_accuracy": sum(max(range(3), key=lambda k: r["probs"][k]) == r["y"] for r in records) / len(records),
    }

def paired_bootstrap(model, comparator, seed):
    ml, cl = losses(model), losses(comparator)
    n = len(model)
    rng = random.Random(seed)
    result = {}
    for metric in ("brier", "log_loss"):
        diffs = [cl[metric][i] - ml[metric][i] for i in range(n)]
        draws = []
        for _ in range(BOOTSTRAP_DRAWS):
            draws.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
        draws.sort()
        result[metric] = {
            "elo_minus_elo_plus_fatigue_point": avg(diffs),
            "ci95_percentile": [draws[int(0.025 * BOOTSTRAP_DRAWS)], draws[int(0.975 * BOOTSTRAP_DRAWS) - 1]],
            "bootstrap_probability_fatigue_better": sum(x > 0 for x in draws) / BOOTSTRAP_DRAWS,
        }
    return result

def main():
    per_league = {}
    pooled_elo, pooled_fatigue = [], []
    data_quality = {}
    for offset, (league, path_text) in enumerate(LEAGUES.items()):
        path = Path(path_text)
        with path.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        rows.sort(key=lambda r: (r["source_date"], r.get("source_time", ""), r["home_team"], r["away_team"]))
        featured = add_schedule_features(rows)
        dev = [r for r in featured if r["split"] == "DEVELOPMENT"]
        holdout = [r for r in featured if r["split"] == "HOLDOUT"]
        specs = {"ELO_ONLY": ["elo_diff"], "ELO_PLUS_FATIGUE": ["elo_diff"] + FATIGUE_FEATURES}
        predictions, fitted = {}, {}
        for name, features in specs.items():
            train_rows, test_rows, means, scales = prepare(dev, holdout, features)
            weights = train(train_rows, len(features) + 1)
            predictions[name] = predict(test_rows, weights)
            fitted[name] = {
                "features": features,
                "development_only_imputation_means": means,
                "development_only_standardization_scales": scales,
                "holdout_metrics": metrics(predictions[name]),
                "weights_by_outcome": {OUTCOMES[k]: weights[k] for k in range(3)},
            }
        comparison = paired_bootstrap(predictions["ELO_PLUS_FATIGUE"], predictions["ELO_ONLY"], SEED + offset)
        per_league[league] = {
            "dataset": path_text,
            "sample": {"development": len(dev), "holdout": len(holdout)},
            "models": fitted,
            "paired_holdout_comparison": comparison,
        }
        pooled_elo.extend(predictions["ELO_ONLY"])
        pooled_fatigue.extend(predictions["ELO_PLUS_FATIGUE"])
        data_quality[league] = {
            "rows": len(rows),
            "missing_source_date": sum(not r.get("source_date") for r in rows),
            "holdout_missing_rest_diff_imputed_from_development": sum(r.get("rest_days_diff") is None for r in holdout),
        }

    pooled = paired_bootstrap(pooled_fatigue, pooled_elo, SEED + 100)
    positive_leagues = {
        metric: sum(per_league[x]["paired_holdout_comparison"][metric]["elo_minus_elo_plus_fatigue_point"] > 0 for x in per_league)
        for metric in ("brier", "log_loss")
    }
    significant_harm = []
    for league, block in per_league.items():
        for metric in ("brier", "log_loss"):
            if block["paired_holdout_comparison"][metric]["ci95_percentile"][1] < 0:
                significant_harm.append({"league": league, "metric": metric})
    pooled_robust = all(pooled[m]["ci95_percentile"][0] > 0 for m in ("brier", "log_loss"))
    direction_gate = all(positive_leagues[m] >= 7 for m in ("brier", "log_loss"))
    promoted = pooled_robust and direction_gate and not significant_harm
    report = {
        "schema_version": "radar-historical-cross-league-fatigue-ablation-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {"leagues": list(LEAGUES), "total_development": sum(x["sample"]["development"] for x in per_league.values()), "total_holdout": len(pooled_elo)},
        "anti_hindsight": {
            "schedule_features_use_strictly_prior_calendar_dates_only": True,
            "same_date_results_or_schedule_updates_used": False,
            "outcomes_used_for_fatigue_features": False,
            "holdout_used_for_training_imputation_standardization_or_tuning": False,
            "split": "existing frozen per-league chronological development/2025-or-2025-26 holdout",
            "kickoff_time_limitation": "source timezone is not verified; calendar-date ordering only, and same-day information is excluded",
        },
        "feature_contract_frozen_before_evaluation": {
            "rest_days": "calendar days since prior accepted league fixture, capped at 30; first observation missing and imputed with development mean",
            "congestion": "count of accepted league fixtures strictly before current date within 7, 14 and 21 calendar days",
            "comparison": "ELO_ONLY versus ELO_PLUS_FATIGUE on identical holdout rows",
            "training": {"l2": L2, "learning_rate": LEARNING_RATE, "iterations": ITERATIONS},
            "promotion_gate": "both pooled paired-bootstrap CI95 lower bounds > 0, positive point direction in >=7/10 leagues for both metrics, and no single-league significant harm",
        },
        "unsupported_not_invented": {
            "travel_distance": "NOT_AVAILABLE",
            "cross_competition_fixtures": "NOT_AVAILABLE_DATASETS_CONTAIN_LEAGUE_FIXTURES_ONLY",
            "extra_time": "NOT_AVAILABLE",
            "player_minutes": "NOT_AVAILABLE",
            "lineup_rotation": "NOT_AVAILABLE",
            "injury_recovery": "NOT_AVAILABLE",
        },
        "data_quality": data_quality,
        "per_league": per_league,
        "pooled_holdout": {
            "elo_only_metrics": metrics(pooled_elo),
            "elo_plus_fatigue_metrics": metrics(pooled_fatigue),
            "paired_comparison": pooled,
            "positive_point_direction_leagues_out_of_10": positive_leagues,
            "significant_harm_cells": significant_harm,
        },
        "decision": {
            "module_promoted": promoted,
            "classification": "PROMOTED_FOR_STRUCTURAL_RESEARCH" if promoted else "NOT_PROMOTED",
            "operational_rule_promoted": False,
            "reason": "Frozen promotion gate passed." if promoted else "Frozen promotion gate not fully passed.",
        },
        "economic_metrics": {
            "roi_yield_drawdown": "NOT_CALCULATED_NO_EX_ANTE_BETTING_RULE",
            "clv": "NOT_CALCULABLE_NO_SAME_BOOKMAKER_OPEN_CLOSE_JOIN",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"decision": report["decision"], "pooled_holdout": report["pooled_holdout"]}, indent=2))

if __name__ == "__main__":
    main()
