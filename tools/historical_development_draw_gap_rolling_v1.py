#!/usr/bin/env python3
"""Development-only rolling-origin audit for a draw-aware Elo-gap feature.

The already-inspected final holdout is never loaded into training, validation,
feature choice, or candidate scoring.
"""
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

OUT = Path("feed/historical/calibration/development-draw-gap-rolling-v1.json")
OUTCOMES = ["H", "D", "A"]
REPORTS = [
    "feed/historical/sweden/structural-oos-v1.json",
    "feed/historical/norway/structural-oos-v1.json",
    "feed/historical/denmark/structural-oos-v1.json",
    "feed/historical/netherlands/structural-oos-v1.json",
    "feed/historical/portugal/structural-oos-v1.json",
    "feed/historical/germany2/structural-oos-v1.json",
    "feed/historical/germany1/structural-oos-v1.json",
    "feed/historical/spain1/structural-oos-v1.json",
    "feed/historical/england1/structural-oos-v1.json",
    "feed/historical/scotland1/structural-oos-v1.json",
    "feed/historical/austria1/structural-oos-v1.json",
]
LEAGUE_NAMES = {
    "sweden": "Allsvenskan", "norway": "Eliteserien", "denmark": "Superliga",
    "netherlands": "Eredivisie", "portugal": "Primeira Liga",
    "germany2": "2. Bundesliga", "germany1": "Bundesliga",
    "spain1": "LaLiga", "england1": "Premier League",
    "scotland1": "Scottish Premiership", "austria1": "Austrian Bundesliga",
}
FEATURE_SETS = {
    "ELO_ONLY": ["elo_diff"],
    "ELO_PLUS_ABS_GAP": ["elo_diff", "abs_elo_diff"],
}
L2 = 0.01
LEARNING_RATE = 0.08
ITERATIONS = 1800
DRAWS = 20000
SEED = 20260902

def prepare(train, test, names):
    means, scales = {}, {}
    for name in names:
        values = np.array([float(r[name]) for r in train], dtype=float)
        means[name] = float(values.mean())
        scale = float(values.std())
        scales[name] = scale if scale > 1e-12 else 1.0
    def matrix(rows):
        cols = [np.ones(len(rows))]
        for name in names:
            cols.append(np.array([(float(r[name]) - means[name]) / scales[name] for r in rows]))
        return np.column_stack(cols)
    return matrix(train), np.array([OUTCOMES.index(r["result"]) for r in train]), matrix(test), np.array([OUTCOMES.index(r["result"]) for r in test]), means, scales

def train_model(x, y):
    n, width = x.shape
    weights = np.zeros((3, width), dtype=float)
    onehot = np.eye(3)[y]
    for _ in range(ITERATIONS):
        scores = x @ weights.T
        scores -= scores.max(axis=1, keepdims=True)
        probs = np.exp(scores)
        probs /= probs.sum(axis=1, keepdims=True)
        grad = (probs - onehot).T @ x / n
        penalty = L2 * weights
        penalty[:, 0] = 0.0
        weights -= LEARNING_RATE * (grad + penalty)
    return weights

def predict(x, weights):
    scores = x @ weights.T
    scores -= scores.max(axis=1, keepdims=True)
    probs = np.exp(scores)
    return probs / probs.sum(axis=1, keepdims=True)

def metrics(records, key):
    p = np.array([r[key] for r in records])
    y = np.array([r["y"] for r in records])
    oh = np.eye(3)[y]
    brier = ((p - oh) ** 2).sum(axis=1)
    logloss = -np.log(np.maximum(p[np.arange(len(y)), y], 1e-15))
    picks = p.argmax(axis=1)
    counts = {o: int((picks == k).sum()) for k, o in enumerate(OUTCOMES)}
    realized = {o: int((y == k).sum()) for k, o in enumerate(OUTCOMES)}
    return {
        "n": len(records),
        "brier": float(brier.mean()),
        "log_loss": float(logloss.mean()),
        "accuracy": float((picks == y).mean()),
        "top_pick_counts": counts,
        "realized_counts": realized,
        "draw_top_pick_precision": float(((y[picks == 1] == 1).mean())) if counts["D"] else None,
        "draw_top_pick_recall": float(((picks[y == 1] == 1).mean())) if realized["D"] else None,
    }

def paired_uncertainty(records):
    groups = defaultdict(list)
    league_delta = defaultdict(list)
    for r in records:
        y = r["y"]
        oh = np.eye(3)[y]
        base, cand = np.array(r["ELO_ONLY"]), np.array(r["ELO_PLUS_ABS_GAP"])
        delta = (
            float(((base - oh) ** 2).sum() - ((cand - oh) ** 2).sum()),
            float(-math.log(max(base[y], 1e-15)) + math.log(max(cand[y], 1e-15))),
        )
        groups[r["group"]].append(delta)
        league_delta[r["league"]].append(delta)
    rng = np.random.default_rng(SEED)
    stratified = [[], []]
    equal_league = [[], []]
    group_arrays = [np.array(v) for v in groups.values()]
    league_means = np.array([[np.mean([x[j] for x in v]) for j in (0, 1)] for v in league_delta.values()])
    total_n = len(records)
    for _ in range(DRAWS):
        sums = np.zeros(2)
        for arr in group_arrays:
            idx = rng.integers(0, len(arr), len(arr))
            sums += arr[idx].sum(axis=0)
        vals = sums / total_n
        stratified[0].append(vals[0]); stratified[1].append(vals[1])
        picked = league_means[rng.integers(0, len(league_means), len(league_means))]
        lm = picked.mean(axis=0)
        equal_league[0].append(lm[0]); equal_league[1].append(lm[1])
    all_delta = np.array([x for v in groups.values() for x in v])
    out = {}
    for j, name in enumerate(("brier", "log_loss")):
        ss = np.sort(stratified[j]); ls = np.sort(equal_league[j])
        out[name] = {
            "elo_only_minus_candidate_point": float(all_delta[:, j].mean()),
            "stratified_league_fold_fixture_ci95": [float(ss[int(.025*DRAWS)]), float(ss[int(.975*DRAWS)-1])],
            "equal_league_point": float(league_means[:, j].mean()),
            "league_bootstrap_ci95": [float(ls[int(.025*DRAWS)]), float(ls[int(.975*DRAWS)-1])],
            "positive_means_candidate_better": True,
        }
    return out

def main():
    records, folds = [], []
    for report_path in REPORTS:
        league_key = Path(report_path).parts[-2]
        league = LEAGUE_NAMES[league_key]
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
        with Path(report["feature_dataset"]).open("r", encoding="utf-8", newline="") as fh:
            dev = [r for r in csv.DictReader(fh) if r["split"] == "DEVELOPMENT"]
        for r in dev:
            r["abs_elo_diff"] = abs(float(r["elo_diff"]))
        seasons = sorted({r["season"] for r in dev})
        if len(seasons) != 3:
            raise RuntimeError(f"{league}: expected three development seasons, got {seasons}")
        for test_pos in (1, 2):
            train_seasons, test_season = seasons[:test_pos], seasons[test_pos]
            train_rows = [r for r in dev if r["season"] in train_seasons]
            test_rows = [r for r in dev if r["season"] == test_season]
            fold_records = [{"league": league, "group": f"{league}|{test_season}", "y": OUTCOMES.index(r["result"])} for r in test_rows]
            model_details = {}
            for model_name, names in FEATURE_SETS.items():
                xtr, ytr, xte, yte, means, scales = prepare(train_rows, test_rows, names)
                weights = train_model(xtr, ytr)
                probs = predict(xte, weights)
                if not np.array_equal(yte, np.array([r["y"] for r in fold_records])):
                    raise RuntimeError("row order mismatch")
                for item, p in zip(fold_records, probs):
                    item[model_name] = [float(v) for v in p]
                model_details[model_name] = {
                    "features": names, "means": means, "scales": scales,
                    "weights_by_outcome": {o: [float(v) for v in weights[k]] for k, o in enumerate(OUTCOMES)},
                }
            folds.append({
                "league": league, "train_seasons": train_seasons, "validation_season": test_season,
                "train_n": len(train_rows), "validation_n": len(test_rows),
                "models": model_details,
                "metrics": {name: metrics(fold_records, name) for name in FEATURE_SETS},
            })
            records.extend(fold_records)

    uncertainty = paired_uncertainty(records)
    base = metrics(records, "ELO_ONLY")
    candidate = metrics(records, "ELO_PLUS_ABS_GAP")
    candidate_robust = all(
        uncertainty[m]["stratified_league_fold_fixture_ci95"][0] > 0
        and uncertainty[m]["league_bootstrap_ci95"][0] > 0
        for m in ("brier", "log_loss")
    )
    draw_coverage = candidate["top_pick_counts"]["D"] > 0
    decision = "FREEZE_FOR_FUTURE_INDEPENDENT_HOLDOUT" if candidate_robust and draw_coverage else "REJECT_CANDIDATE"
    report = {
        "schema_version": "radar-historical-development-draw-gap-rolling-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "anti_hindsight": {
            "final_holdout_rows_loaded": False,
            "eligible_rows": "DEVELOPMENT only",
            "rolling_origin": "train prior development seasons; validate next development season",
            "current_2025_or_2025_2026_holdout_used_for_candidate_choice": False,
            "candidate_rationale": "absolute pre-match Elo gap permits draw probability to peak for closely matched teams",
            "features_known_pre_kickoff": True,
        },
        "training": {"l2": L2, "learning_rate": LEARNING_RATE, "iterations": ITERATIONS, "models": FEATURE_SETS},
        "sample": {"leagues": 11, "folds": len(folds), "validation_fixtures": len(records)},
        "pooled": {"ELO_ONLY": base, "ELO_PLUS_ABS_GAP": candidate},
        "paired_uncertainty": {"draws": DRAWS, "seed": SEED, "results": uncertainty},
        "folds": folds,
        "decision": {
            "status": decision,
            "robust_brier_and_log_loss_improvement": candidate_robust,
            "nonzero_draw_top_pick_coverage": draw_coverage,
            "operational_rule_promoted": False,
            "final_holdout_evaluated": False,
            "next_gate": "A candidate may only be judged on a new temporal block not used to discover the zero-draw failure.",
        },
        "economic_metrics": {"roi_clv_yield_drawdown": "NOT_CALCULATED_NO_PRICE_RULE_AND_DEVELOPMENT_ONLY_MODEL_AUDIT"},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"sample": report["sample"], "pooled": report["pooled"], "uncertainty": uncertainty, "decision": report["decision"]}, indent=2))

if __name__ == "__main__":
    main()
