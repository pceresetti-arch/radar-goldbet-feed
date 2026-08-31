#!/usr/bin/env python3
import csv
import json
import math
import random
import runpy
from datetime import datetime, timezone
from pathlib import Path

OUTCOMES = ["H", "D", "A"]
DRAWS = 10000
SEED = 20260831
OUT = Path("feed/historical/cross-league/sweden-norway-oos-comparison-v1.json")
LEAGUES = {
    "Sweden": {
        "module": "tools/historical_model_sweden_structural.py",
        "data": "feed/historical/sweden/allsvenskan-2022-2025-regular.csv",
        "baseline": "feed/historical/sweden/baseline-benchmark.json"
    },
    "Norway": {
        "module": "tools/historical_model_norway_structural.py",
        "data": "feed/historical/norway/eliteserien-2022-2025-regular.csv",
        "baseline": "feed/historical/norway/baseline-benchmark.json"
    }
}
FEATURE_SETS = {
    "ELO_ONLY": ["elo_diff"],
    "ELO_PLUS_FORM": ["elo_diff", "form_ppg_diff", "goal_balance_diff"],
    "FULL_STRUCTURAL": ["elo_diff", "form_ppg_diff", "goal_balance_diff", "venue_ppg_diff", "opponent_elo_diff"]
}

def metrics(records):
    n = len(records)
    brier = []
    logloss = []
    correct = []
    buckets = {}
    confusion = {truth: {pick: 0 for pick in OUTCOMES} for truth in OUTCOMES}
    class_data = {outcome: {"prob_sum": 0.0, "obs_sum": 0, "sqerr_sum": 0.0, "bins": {}} for outcome in OUTCOMES}
    for row in records:
        y, probs = row["y"], row["probs"]
        brier.append(sum((p - (1.0 if k == y else 0.0)) ** 2 for k, p in enumerate(probs)))
        logloss.append(-math.log(max(probs[y], 1e-15)))
        pick = max(range(3), key=lambda k: probs[k])
        correct.append(int(pick == y))
        confusion[OUTCOMES[y]][OUTCOMES[pick]] += 1
        for k, outcome in enumerate(OUTCOMES):
            observed = int(k == y)
            p = probs[k]
            d = class_data[outcome]
            d["prob_sum"] += p
            d["obs_sum"] += observed
            d["sqerr_sum"] += (p - observed) ** 2
            lo_class = math.floor(p * 10) / 10
            key_class = f"{lo_class:.1f}-{min(1.0, lo_class + 0.1):.1f}"
            cb = d["bins"].setdefault(key_class, {"n": 0, "prob_sum": 0.0, "events": 0})
            cb["n"] += 1
            cb["prob_sum"] += p
            cb["events"] += observed
        confidence = probs[pick]
        lo = math.floor(confidence * 10) / 10
        key = f"{lo:.1f}-{min(1.0, lo + 0.1):.1f}"
        b = buckets.setdefault(key, {"n": 0, "confidence_sum": 0.0, "hits": 0})
        b["n"] += 1
        b["confidence_sum"] += confidence
        b["hits"] += int(pick == y)
    calibration = {}
    ece = 0.0
    for key, b in sorted(buckets.items()):
        mean_conf = b["confidence_sum"] / b["n"]
        hit_rate = b["hits"] / b["n"]
        ece += (b["n"] / n) * abs(hit_rate - mean_conf)
        calibration[key] = {"n": b["n"], "mean_confidence": mean_conf, "hit_rate": hit_rate}
    classwise = {}
    for outcome, d in class_data.items():
        reliability = {}
        class_ece = 0.0
        for key, b in sorted(d["bins"].items()):
            mean_p = b["prob_sum"] / b["n"]
            event_rate = b["events"] / b["n"]
            class_ece += (b["n"] / n) * abs(event_rate - mean_p)
            reliability[key] = {"n": b["n"], "mean_probability": mean_p, "event_rate": event_rate}
        observed_rate = d["obs_sum"] / n
        mean_probability = d["prob_sum"] / n
        classwise[outcome] = {
            "observed_rate": observed_rate,
            "mean_probability": mean_probability,
            "mean_probability_minus_observed": mean_probability - observed_rate,
            "one_vs_rest_brier": d["sqerr_sum"] / n,
            "ece_0_1_bins": class_ece,
            "reliability": reliability
        }
    argmax_counts = {outcome: sum(confusion[truth][outcome] for truth in OUTCOMES) for outcome in OUTCOMES}
    return {
        "n": n,
        "multiclass_brier_sum_mean": sum(brier) / n,
        "log_loss": sum(logloss) / n,
        "top_pick_accuracy": sum(correct) / n,
        "top_pick_ece_0_1_bins": ece,
        "top_pick_calibration": calibration,
        "confusion_truth_by_pick": confusion,
        "argmax_pick_counts": argmax_counts,
        "argmax_never_selected_classes": [outcome for outcome, count in argmax_counts.items() if count == 0],
        "classwise_probability_calibration": classwise
    }

def loss_vectors(records):
    return {
        "brier": [sum((p - (1.0 if k == r["y"] else 0.0)) ** 2 for k, p in enumerate(r["probs"])) for r in records],
        "log_loss": [-math.log(max(r["probs"][r["y"]], 1e-15)) for r in records]
    }

def stratified_paired_bootstrap(model_by_league, comparator_by_league, seed):
    rng = random.Random(seed)
    model = {league: loss_vectors(rows) for league, rows in model_by_league.items()}
    comp = {league: loss_vectors(comparator_by_league[league]) for league in model_by_league}
    total = sum(len(rows) for rows in model_by_league.values())
    samples = {"brier": [], "log_loss": []}
    for _ in range(DRAWS):
        sums = {metric: 0.0 for metric in samples}
        for league, rows in model_by_league.items():
            n = len(rows)
            for _ in range(n):
                i = rng.randrange(n)
                for metric in samples:
                    sums[metric] += comp[league][metric][i] - model[league][metric][i]
        for metric in samples:
            samples[metric].append(sums[metric] / total)
    out = {}
    for metric, values in samples.items():
        values.sort()
        point = sum(
            comp[league][metric][i] - model[league][metric][i]
            for league, rows in model_by_league.items() for i in range(len(rows))
        ) / total
        out[metric] = {
            "comparator_minus_model_point": point,
            "ci95_percentile": [values[int(0.025 * DRAWS)], values[int(0.975 * DRAWS) - 1]],
            "bootstrap_probability_model_better": sum(v > 0 for v in values) / DRAWS
        }
    return out

def independent_league_drift(sweden, norway, seed):
    rng = random.Random(seed)
    s = loss_vectors(sweden)
    n = loss_vectors(norway)
    out = {}
    for metric in ("brier", "log_loss"):
        draws = []
        for _ in range(DRAWS):
            sm = sum(s[metric][rng.randrange(len(sweden))] for _ in sweden) / len(sweden)
            nm = sum(n[metric][rng.randrange(len(norway))] for _ in norway) / len(norway)
            draws.append(sm - nm)
        draws.sort()
        point = sum(s[metric]) / len(sweden) - sum(n[metric]) / len(norway)
        out[metric] = {
            "sweden_minus_norway_point": point,
            "ci95_percentile": [draws[int(0.025 * DRAWS)], draws[int(0.975 * DRAWS) - 1]],
            "interpretation": "Positive means higher loss in Sweden."
        }
    return out

def build_league(config):
    ns = runpy.run_path(config["module"])
    with Path(config["data"]).open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    rows.sort(key=lambda r: (r["source_date"], r.get("source_time", ""), r["home_team"], r["away_team"]))
    featured = ns["build_features"](rows)
    dev = [r for r in featured if r["split"] == "DEVELOPMENT"]
    holdout = [r for r in featured if r["split"] == "HOLDOUT"]
    baseline = json.loads(Path(config["baseline"]).read_text(encoding="utf-8"))
    records = {}
    for name, features in FEATURE_SETS.items():
        train_rows, test_rows, _, _ = ns["prepare"](dev, holdout, features)
        weights = ns["train"](train_rows, len(features) + 1)
        records[name] = ns["predict"](test_rows, weights)
    priors = [baseline["development_outcome_prior"][outcome] for outcome in OUTCOMES]
    records["DEVELOPMENT_PRIOR"] = [{"y": OUTCOMES.index(r["result"]), "probs": priors} for r in holdout]
    market = []
    for r in holdout:
        inv = [1.0 / float(r["avg_close_home"]), 1.0 / float(r["avg_close_draw"]), 1.0 / float(r["avg_close_away"])]
        total = sum(inv)
        market.append({"y": OUTCOMES.index(r["result"]), "probs": [v / total for v in inv]})
    records["EXTERNAL_MARKET_CLOSE"] = market
    return records

def main():
    by_league = {league: build_league(config) for league, config in LEAGUES.items()}
    models = list(next(iter(by_league.values())).keys())
    league_metrics = {
        league: {model: metrics(records[model]) for model in models}
        for league, records in by_league.items()
    }
    pooled_metrics = {
        model: metrics(by_league["Sweden"][model] + by_league["Norway"][model])
        for model in models
    }
    comparisons = {
        "ELO_ONLY_VS_DEVELOPMENT_PRIOR": stratified_paired_bootstrap(
            {l: by_league[l]["ELO_ONLY"] for l in by_league},
            {l: by_league[l]["DEVELOPMENT_PRIOR"] for l in by_league}, SEED + 1),
        "ELO_PLUS_FORM_VS_ELO_ONLY": stratified_paired_bootstrap(
            {l: by_league[l]["ELO_PLUS_FORM"] for l in by_league},
            {l: by_league[l]["ELO_ONLY"] for l in by_league}, SEED + 2),
        "FULL_STRUCTURAL_VS_ELO_ONLY": stratified_paired_bootstrap(
            {l: by_league[l]["FULL_STRUCTURAL"] for l in by_league},
            {l: by_league[l]["ELO_ONLY"] for l in by_league}, SEED + 3),
        "EXTERNAL_MARKET_CLOSE_VS_ELO_ONLY": stratified_paired_bootstrap(
            {l: by_league[l]["EXTERNAL_MARKET_CLOSE"] for l in by_league},
            {l: by_league[l]["ELO_ONLY"] for l in by_league}, SEED + 4),
        "EXTERNAL_MARKET_CLOSE_VS_ELO_PLUS_FORM": stratified_paired_bootstrap(
            {l: by_league[l]["EXTERNAL_MARKET_CLOSE"] for l in by_league},
            {l: by_league[l]["ELO_PLUS_FORM"] for l in by_league}, SEED + 5)
    }
    drift = {
        model: independent_league_drift(by_league["Sweden"][model], by_league["Norway"][model], SEED + 100 + i)
        for i, model in enumerate(models)
    }
    report = {
        "schema_version": "radar-historical-cross-league-sweden-norway-oos-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "design": {
            "leagues": ["Sweden", "Norway"],
            "development_seasons": ["2022", "2023", "2024"],
            "holdout_seasons": ["2025"],
            "holdout_n_per_league": 240,
            "pooled_holdout_n": 480,
            "specification": "Sweden v1 feature sets and hyperparameters frozen before Norway evaluation.",
            "holdout_retuning": False,
            "same_date_results_used": False,
            "closing_class": "EXTERNAL_HISTORICAL_MARKET_BENCHMARK_NOT_GOLDBET"
        },
        "league_metrics": league_metrics,
        "pooled_metrics": pooled_metrics,
        "stratified_paired_bootstrap": {
            "draws": DRAWS,
            "seed": SEED,
            "positive_comparator_minus_model_means_model_better": True,
            "comparisons": comparisons
        },
        "league_drift_independent_bootstrap": {
            "draws": DRAWS,
            "interpretation": "Descriptive independent match bootstrap; league schedules induce dependence and no causal league claim is made.",
            "models": drift
        },
        "decisions": {
            "elo_vs_naive_prior": "SUPPORTED_ON_BOTH_LEAGUES_AND_POOLED_HOLDOUT",
            "form_increment_beyond_elo": "NOT_SUPPORTED_PAIRED_INTERVAL_INCLUDES_ZERO",
            "full_structural_increment_beyond_elo": "REJECTED_NO_RELIABLE_GAIN",
            "external_close_vs_structural": "BENCHMARK_SUPERIOR_POOLED_NOT_OPERATIONAL_EDGE",
            "operational_promotion": False,
            "mms_status": "NOT_TESTED_NO_GOLDBET_TRUE_OPEN"
        },
        "limitations": [
            "Only two leagues and one holdout season per league.",
            "Match bootstrap does not remove within-season schedule dependence.",
            "External closing odds are near-kickoff benchmarks, not GoldBet TRUE OPEN or an executable historical strategy.",
            "No XI, player props, T-30 or intermediate snapshots are reconstructed."
        ]
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["decisions"], indent=2))

if __name__ == "__main__":
    main()
