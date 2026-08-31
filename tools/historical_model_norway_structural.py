#!/usr/bin/env python3
import csv
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA = Path("feed/historical/norway/eliteserien-2022-2025-regular.csv")
BASELINE = Path("feed/historical/norway/baseline-benchmark.json")
FEATURES_OUT = Path("feed/historical/norway/eliteserien-2022-2025-features.csv")
REPORT_OUT = Path("feed/historical/norway/structural-oos-v1.json")
OUTCOMES = ["H", "D", "A"]
K_FACTOR = 20.0
HOME_ELO_ADVANTAGE = 60.0
SEASON_MEAN_REVERSION = 0.50
ROLLING_WINDOW = 5
L2 = 0.01
LEARNING_RATE = 0.08
ITERATIONS = 1800

def avg(values):
    return sum(values) / len(values) if values else None

def elo_expected(home_rating, away_rating):
    return 1.0 / (1.0 + 10.0 ** (-(home_rating + HOME_ELO_ADVANTAGE - away_rating) / 400.0))

def softmax(scores):
    m = max(scores)
    ex = [math.exp(s - m) for s in scores]
    total = sum(ex)
    return [x / total for x in ex]

def feature_snapshot(team, histories, venue=None):
    hist = histories.get(team, [])
    recent = hist[-ROLLING_WINDOW:]
    venue_rows = [x for x in hist if x["venue"] == venue][-ROLLING_WINDOW:] if venue else recent
    return {
        "form_ppg": avg([x["points"] for x in recent]),
        "goal_balance": avg([x["gf"] - x["ga"] for x in recent]),
        "venue_ppg": avg([x["points"] for x in venue_rows]),
        "opponent_elo": avg([x["opponent_elo"] for x in recent]),
        "prior_matches": len(hist)
    }

def difference(a, b):
    return None if a is None or b is None else a - b

def build_features(rows):
    ratings = {}
    histories = defaultdict(list)
    generated = []
    season = None
    by_date = defaultdict(list)
    for row in rows:
        by_date[row["source_date"]].append(row)

    for date in sorted(by_date):
        batch = sorted(by_date[date], key=lambda x: (x.get("source_time", ""), x["home_team"], x["away_team"]))
        batch_season = batch[0]["season"]
        if season is None:
            season = batch_season
        elif batch_season != season:
            ratings = {team: 1500.0 + (rating - 1500.0) * SEASON_MEAN_REVERSION for team, rating in ratings.items()}
            season = batch_season

        pending = []
        for row in batch:
            home, away = row["home_team"], row["away_team"]
            hr, ar = ratings.get(home, 1500.0), ratings.get(away, 1500.0)
            hs = feature_snapshot(home, histories, "H")
            a_s = feature_snapshot(away, histories, "A")
            feat = dict(row)
            feat.update({
                "home_elo_pre": hr,
                "away_elo_pre": ar,
                "elo_diff": hr - ar,
                "form_ppg_diff": difference(hs["form_ppg"], a_s["form_ppg"]),
                "goal_balance_diff": difference(hs["goal_balance"], a_s["goal_balance"]),
                "venue_ppg_diff": difference(hs["venue_ppg"], a_s["venue_ppg"]),
                "opponent_elo_diff": difference(hs["opponent_elo"], a_s["opponent_elo"]),
                "home_prior_matches": hs["prior_matches"],
                "away_prior_matches": a_s["prior_matches"],
                "same_date_information_used": False
            })
            generated.append(feat)
            pending.append((row, hr, ar))

        for row, hr, ar in pending:
            home, away = row["home_team"], row["away_team"]
            hg, ag = int(row["home_goals"]), int(row["away_goals"])
            result = row["result"]
            actual = 1.0 if result == "H" else (0.0 if result == "A" else 0.5)
            expected = elo_expected(hr, ar)
            ratings[home] = hr + K_FACTOR * (actual - expected)
            ratings[away] = ar + K_FACTOR * ((1.0 - actual) - (1.0 - expected))
            home_points = 3 if result == "H" else (1 if result == "D" else 0)
            away_points = 3 if result == "A" else (1 if result == "D" else 0)
            histories[home].append({"points": home_points, "gf": hg, "ga": ag, "venue": "H", "opponent_elo": ar})
            histories[away].append({"points": away_points, "gf": ag, "ga": hg, "venue": "A", "opponent_elo": hr})
    return generated

def prepare(dev, test, feature_names):
    means = {}
    scales = {}
    for name in feature_names:
        values = [float(r[name]) for r in dev if r.get(name) not in (None, "")]
        means[name] = avg(values) if values else 0.0
        variance = avg([(v - means[name]) ** 2 for v in values]) if values else 0.0
        scales[name] = math.sqrt(variance) if variance and variance > 1e-12 else 1.0

    def vector(row):
        vals = []
        for name in feature_names:
            raw = row.get(name)
            value = means[name] if raw in (None, "") else float(raw)
            vals.append((value - means[name]) / scales[name])
        return [1.0] + vals
    return [(vector(r), OUTCOMES.index(r["result"])) for r in dev], [(vector(r), OUTCOMES.index(r["result"])) for r in test], means, scales

def train(train_rows, width):
    weights = [[0.0] * width for _ in OUTCOMES]
    n = len(train_rows)
    for _ in range(ITERATIONS):
        grad = [[0.0] * width for _ in OUTCOMES]
        for x, y in train_rows:
            probs = softmax([sum(wj * xj for wj, xj in zip(w, x)) for w in weights])
            for k in range(3):
                error = probs[k] - (1.0 if k == y else 0.0)
                for j, xj in enumerate(x):
                    grad[k][j] += error * xj
        for k in range(3):
            for j in range(width):
                penalty = 0.0 if j == 0 else L2 * weights[k][j]
                weights[k][j] -= LEARNING_RATE * (grad[k][j] / n + penalty)
    return weights

def predict(rows, weights):
    return [
        {"y": y, "probs": softmax([sum(wj * xj for wj, xj in zip(w, x)) for w in weights])}
        for x, y in rows
    ]

def loss_vectors(records):
    return {
        "brier": [
            sum((p - (1.0 if k == row["y"] else 0.0)) ** 2 for k, p in enumerate(row["probs"]))
            for row in records
        ],
        "log_loss": [-math.log(max(row["probs"][row["y"]], 1e-15)) for row in records]
    }

def paired_bootstrap(model_records, comparator_records, seed, draws=10000):
    model_losses = loss_vectors(model_records)
    comparator_losses = loss_vectors(comparator_records)
    n = len(model_records)
    rng = random.Random(seed)
    samples = {"brier": [], "log_loss": []}
    for _ in range(draws):
        idx = [rng.randrange(n) for _ in range(n)]
        for metric in samples:
            samples[metric].append(sum(
                comparator_losses[metric][i] - model_losses[metric][i] for i in idx
            ) / n)
    result = {}
    for metric, values in samples.items():
        values.sort()
        point = sum(
            comparator_losses[metric][i] - model_losses[metric][i] for i in range(n)
        ) / n
        result[metric] = {
            "comparator_minus_model_point": point,
            "ci95_percentile": [values[int(0.025 * draws)], values[int(0.975 * draws) - 1]],
            "bootstrap_probability_model_better": sum(v > 0 for v in values) / draws
        }
    return result

def evaluate(rows, weights):
    brier = logloss = 0.0
    correct = 0
    calibration = {}
    for x, y in rows:
        probs = softmax([sum(wj * xj for wj, xj in zip(w, x)) for w in weights])
        brier += sum((p - (1.0 if k == y else 0.0)) ** 2 for k, p in enumerate(probs))
        logloss += -math.log(max(probs[y], 1e-15))
        pick = max(range(3), key=lambda k: probs[k])
        correct += int(pick == y)
        confidence = probs[pick]
        lo = math.floor(confidence * 10) / 10
        key = f"{lo:.1f}-{min(1.0, lo + 0.1):.1f}"
        b = calibration.setdefault(key, {"n": 0, "confidence_sum": 0.0, "hits": 0})
        b["n"] += 1
        b["confidence_sum"] += confidence
        b["hits"] += int(pick == y)
    n = len(rows)
    for b in calibration.values():
        b["mean_confidence"] = b.pop("confidence_sum") / b["n"]
        b["hit_rate"] = b["hits"] / b["n"]
    return {
        "n": n,
        "multiclass_brier_sum_mean": brier / n,
        "multiclass_brier_class_mean": brier / (3 * n),
        "log_loss": logloss / n,
        "top_pick_accuracy": correct / n,
        "top_pick_calibration": dict(sorted(calibration.items()))
    }

def main():
    with DATA.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    rows.sort(key=lambda r: (r["source_date"], r.get("source_time", ""), r["home_team"], r["away_team"]))
    featured = build_features(rows)
    dev = [r for r in featured if r["split"] == "DEVELOPMENT"]
    holdout = [r for r in featured if r["split"] == "HOLDOUT"]

    feature_sets = {
        "ELO_ONLY": ["elo_diff"],
        "ELO_PLUS_FORM": ["elo_diff", "form_ppg_diff", "goal_balance_diff"],
        "FULL_STRUCTURAL": ["elo_diff", "form_ppg_diff", "goal_balance_diff", "venue_ppg_diff", "opponent_elo_diff"]
    }
    results = {}
    holdout_predictions = {}
    for name, names in feature_sets.items():
        train_rows, test_rows, means, scales = prepare(dev, holdout, names)
        weights = train(train_rows, len(names) + 1)
        results[name] = {
            "features": names,
            "imputation": "DEVELOPMENT_MEAN_ONLY",
            "standardization": {"means": means, "scales": scales},
            "fixed_training": {"l2": L2, "learning_rate": LEARNING_RATE, "iterations": ITERATIONS},
            "weights_by_outcome": {OUTCOMES[k]: weights[k] for k in range(3)},
            "holdout_metrics": evaluate(test_rows, weights)
        }
        holdout_predictions[name] = predict(test_rows, weights)

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    priors = [baseline["development_outcome_prior"][outcome] for outcome in OUTCOMES]
    prior_records = [{"y": OUTCOMES.index(r["result"]), "probs": priors} for r in holdout]
    market_records = []
    for r in holdout:
        inverse = [1.0 / float(r["avg_close_home"]), 1.0 / float(r["avg_close_draw"]), 1.0 / float(r["avg_close_away"])]
        total = sum(inverse)
        market_records.append({"y": OUTCOMES.index(r["result"]), "probs": [v / total for v in inverse]})
    uncertainty = {}
    seed = 20260831
    for offset, name in enumerate(feature_sets):
        uncertainty[name] = {
            "vs_development_prior": paired_bootstrap(holdout_predictions[name], prior_records, seed + offset * 10),
            "vs_external_market_close": paired_bootstrap(holdout_predictions[name], market_records, seed + offset * 10 + 1)
        }
    uncertainty["incremental_vs_elo_only"] = {
        "ELO_PLUS_FORM": paired_bootstrap(holdout_predictions["ELO_PLUS_FORM"], holdout_predictions["ELO_ONLY"], seed + 101),
        "FULL_STRUCTURAL": paired_bootstrap(holdout_predictions["FULL_STRUCTURAL"], holdout_predictions["ELO_ONLY"], seed + 102)
    }

    feature_fields = list(rows[0].keys()) + [
        "home_elo_pre", "away_elo_pre", "elo_diff", "form_ppg_diff", "goal_balance_diff",
        "venue_ppg_diff", "opponent_elo_diff", "home_prior_matches", "away_prior_matches",
        "same_date_information_used"
    ]
    with FEATURES_OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=feature_fields)
        writer.writeheader()
        for row in featured:
            writer.writerow({k: "" if row.get(k) is None else row.get(k, "") for k in feature_fields})

    report = {
        "schema_version": "radar-historical-norway-structural-oos-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(DATA),
        "feature_dataset": str(FEATURES_OUT),
        "anti_hindsight": {
            "outcomes_used_for_current_match_features": False,
            "same_date_results_used": False,
            "features_updated_after_complete_date_batch": True,
            "development_seasons": ["2022", "2023", "2024"],
            "holdout_seasons": ["2025"],
            "holdout_used_for_training_or_tuning": False,
            "missing_feature_imputation": "development mean only",
            "hyperparameters": "copied unchanged from Sweden v1 before Norway holdout evaluation",
            "specification_source": "SWEDEN_V1_FROZEN_NO_NORWAY_HOLDOUT_TUNING"
        },
        "feature_rules": {
            "elo": {"initial": 1500, "k": K_FACTOR, "home_advantage": HOME_ELO_ADVANTAGE, "season_mean_reversion": SEASON_MEAN_REVERSION},
            "rolling_window_matches": ROLLING_WINDOW,
            "form": "points per game from prior five matches",
            "goal_balance": "goals for minus against per prior match",
            "home_away": "home team's prior home PPG minus away team's prior away PPG",
            "opponent_quality": "mean pre-match Elo of prior five opponents"
        },
        "sample": {"development": len(dev), "holdout": len(holdout)},
        "ablation_same_holdout": results,
        "paired_match_bootstrap": {
            "draws": 10000,
            "seed": seed,
            "unit": "match",
            "interpretation": "Diagnostic paired uncertainty on the frozen 2025 holdout; single-season dependence and lack of league replication prevent operational promotion.",
            "positive_comparator_minus_model_means_model_better": True,
            "comparisons": uncertainty
        },
        "references": {
            "development_prior_baseline": baseline["holdout_metrics"]["development_prior_baseline"],
            "devigged_external_average_close_benchmark": baseline["holdout_metrics"]["devigged_average_market_close_benchmark"]
        },
        "economic_metrics": {
            "clv": "NOT_CALCULABLE_NO_OPEN_PRICE",
            "roi_yield": "NOT_CALCULATED_NO_EX_ANTE_STRATEGY",
            "drawdown": "NOT_CALCULATED_NO_EX_ANTE_STRATEGY"
        },
        "promotion_gate": "NO_AUTOMATIC_PROMOTION_REQUIRES_ROBUST_IMPROVEMENT_AND_REPLICATION",
        "mms": "NOT_TESTED_NO_GOLDBET_TRUE_OPEN"
    }
    REPORT_OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({name: value["holdout_metrics"] for name, value in results.items()}, indent=2))

if __name__ == "__main__":
    main()
