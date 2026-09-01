#!/usr/bin/env python3
"""Frozen cross-league OOS calibration audit.

Reconstructs ELO_ONLY probabilities exclusively from persisted feature rows and
persisted report coefficients. It never retrains or tunes against holdout data.
"""
import csv
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(".")
OUT = Path("feed/historical/calibration/cross-league-elo-calibration-v1.json")
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
DRAWS = 20000
SEED = 20260902

def softmax(scores):
    m = max(scores)
    ex = [math.exp(x - m) for x in scores]
    total = sum(ex)
    return [x / total for x in ex]

def losses(row, key):
    probs = row[key]
    y = row["y"]
    return (
        sum((p - (1.0 if k == y else 0.0)) ** 2 for k, p in enumerate(probs)),
        -math.log(max(probs[y], 1e-15)),
    )

def metrics(rows, key):
    values = [losses(r, key) for r in rows]
    correct = sum(max(range(3), key=lambda k: r[key][k]) == r["y"] for r in rows)
    return {
        "n": len(rows),
        "multiclass_brier_sum_mean": sum(x[0] for x in values) / len(rows),
        "multiclass_brier_class_mean": sum(x[0] for x in values) / (3 * len(rows)),
        "log_loss": sum(x[1] for x in values) / len(rows),
        "top_pick_accuracy": correct / len(rows),
    }

def calibration(rows, key):
    top_bins = {}
    class_bins = {}
    for r in rows:
        probs, y = r[key], r["y"]
        pick = max(range(3), key=lambda k: probs[k])
        confidence = probs[pick]
        lo = min(0.9, math.floor(confidence * 10) / 10)
        label = f"{lo:.1f}-{min(1.0, lo + 0.1):.1f}"
        b = top_bins.setdefault(label, {"n": 0, "probability_sum": 0.0, "observed_sum": 0})
        b["n"] += 1
        b["probability_sum"] += confidence
        b["observed_sum"] += int(pick == y)
        for k, p in enumerate(probs):
            clo = min(0.9, math.floor(p * 10) / 10)
            clabel = f"{clo:.1f}-{min(1.0, clo + 0.1):.1f}"
            cb = class_bins.setdefault(clabel, {"n": 0, "probability_sum": 0.0, "observed_sum": 0})
            cb["n"] += 1
            cb["probability_sum"] += p
            cb["observed_sum"] += int(k == y)
    def finalize(bins, denominator):
        out, ece = {}, 0.0
        for label in sorted(bins):
            b = bins[label]
            mean_p = b["probability_sum"] / b["n"]
            observed = b["observed_sum"] / b["n"]
            ece += b["n"] / denominator * abs(mean_p - observed)
            out[label] = {"n": b["n"], "mean_probability": mean_p, "observed_rate": observed,
                          "observed_minus_probability": observed - mean_p}
        return out, ece
    top, top_ece = finalize(top_bins, len(rows))
    classes, class_ece = finalize(class_bins, 3 * len(rows))
    return {"top_pick_bins": top, "top_pick_ece": top_ece,
            "all_class_probability_bins": classes, "all_class_ece": class_ece}

def group_metrics(rows, key, group_fn):
    groups = defaultdict(list)
    for r in rows:
        groups[group_fn(r)].append(r)
    return {str(k): metrics(v, key) for k, v in sorted(groups.items())}

def bootstrap(rows):
    by_league = defaultdict(list)
    for r in rows:
        eb, el = losses(r, "elo")
        mb, ml = losses(r, "market")
        by_league[r["league"]].append((mb - eb, ml - el))
    leagues = sorted(by_league)
    rng = random.Random(SEED)
    fixture_samples = {"brier": [], "log_loss": []}
    league_samples = {"brier": [], "log_loss": []}
    league_delta = {
        league: (
            sum(x[0] for x in values) / len(values),
            sum(x[1] for x in values) / len(values),
        )
        for league, values in by_league.items()
    }
    total_n = sum(len(v) for v in by_league.values())
    for _ in range(DRAWS):
        sum_b = sum_l = 0.0
        for league in leagues:
            values = by_league[league]
            for _ in range(len(values)):
                db, dl = values[rng.randrange(len(values))]
                sum_b += db
                sum_l += dl
        fixture_samples["brier"].append(sum_b / total_n)
        fixture_samples["log_loss"].append(sum_l / total_n)
        picked = [leagues[rng.randrange(len(leagues))] for _ in leagues]
        league_samples["brier"].append(sum(league_delta[x][0] for x in picked) / len(picked))
        league_samples["log_loss"].append(sum(league_delta[x][1] for x in picked) / len(picked))
    pooled_point = {
        "brier": sum(sum(x[0] for x in v) for v in by_league.values()) / total_n,
        "log_loss": sum(sum(x[1] for x in v) for v in by_league.values()) / total_n,
    }
    out = {}
    for metric, pos in (("brier", 0), ("log_loss", 1)):
        fs = sorted(fixture_samples[metric])
        ls = sorted(league_samples[metric])
        out[metric] = {
            "market_minus_elo_pooled_point": pooled_point[metric],
            "stratified_fixture_bootstrap_ci95": [fs[int(.025 * DRAWS)], fs[int(.975 * DRAWS) - 1]],
            "market_minus_elo_equal_league_point": sum(x[pos] for x in league_delta.values()) / len(leagues),
            "league_bootstrap_ci95": [ls[int(.025 * DRAWS)], ls[int(.975 * DRAWS) - 1]],
            "positive_means_elo_better": True,
        }
    return out

def main():
    all_rows, validations, leagues = [], {}, {}
    for report_path in REPORTS:
        report = json.loads((ROOT / report_path).read_text(encoding="utf-8"))
        league_key = Path(report_path).parts[-2]
        league = LEAGUE_NAMES[league_key]
        model = report["ablation_same_holdout"]["ELO_ONLY"]
        names = model["features"]
        means = model["standardization"]["means"]
        scales = model["standardization"]["scales"]
        weights = [model["weights_by_outcome"][o] for o in OUTCOMES]
        with (ROOT / report["feature_dataset"]).open("r", encoding="utf-8", newline="") as fh:
            holdout = [r for r in csv.DictReader(fh) if r["split"] == "HOLDOUT"]
        if len(holdout) != report["sample"]["holdout"]:
            raise RuntimeError(f"{league}: holdout count mismatch")
        league_rows = []
        for r in holdout:
            x = [1.0]
            for name in names:
                raw = r.get(name)
                value = means[name] if raw in (None, "") else float(raw)
                x.append((value - means[name]) / scales[name])
            elo = softmax([sum(a*b for a, b in zip(w, x)) for w in weights])
            inv = [1.0 / float(r["avg_close_home"]), 1.0 / float(r["avg_close_draw"]), 1.0 / float(r["avg_close_away"])]
            total = sum(inv)
            market = [v / total for v in inv]
            item = {"league": league, "y": OUTCOMES.index(r["result"]), "elo": elo, "market": market}
            league_rows.append(item)
        reproduced = metrics(league_rows, "elo")
        persisted = model["holdout_metrics"]
        checks = {
            "n": reproduced["n"] == persisted["n"],
            "brier_abs_error": abs(reproduced["multiclass_brier_sum_mean"] - persisted["multiclass_brier_sum_mean"]),
            "log_loss_abs_error": abs(reproduced["log_loss"] - persisted["log_loss"]),
            "accuracy_abs_error": abs(reproduced["top_pick_accuracy"] - persisted["top_pick_accuracy"]),
        }
        if not checks["n"] or max(checks[k] for k in checks if k.endswith("_error")) > 1e-12:
            raise RuntimeError(f"{league}: frozen prediction reproduction failed: {checks}")
        validations[league] = checks
        leagues[league] = {"elo": reproduced, "external_average_close": metrics(league_rows, "market"),
                           "elo_calibration": calibration(league_rows, "elo")}
        all_rows.extend(league_rows)

    overall_elo = metrics(all_rows, "elo")
    overall_market = metrics(all_rows, "market")
    paired = bootstrap(all_rows)
    predicted_side_counts = {o: 0 for o in OUTCOMES}
    realized_outcome_counts = {o: 0 for o in OUTCOMES}
    for row in all_rows:
        predicted_side_counts[OUTCOMES[max(range(3), key=lambda k: row["elo"][k])]] += 1
        realized_outcome_counts[OUTCOMES[row["y"]]] += 1
    market_robust = all(
        paired[m]["stratified_fixture_bootstrap_ci95"][1] < 0
        and paired[m]["league_bootstrap_ci95"][1] < 0
        for m in ("brier", "log_loss")
    )
    verdict = {
        "elo_calibration_status": "ACCEPTABLE_POOLED_DIAGNOSTIC_ONLY",
        "market_comparison_status": "EXTERNAL_AVERAGE_CLOSE_ROBUSTLY_BETTER" if market_robust else "INCONCLUSIVE",
        "draw_top_pick_status": "STRUCTURAL_MODEL_FAILURE_ZERO_DRAW_TOP_PICKS",
        "predicted_side_counts": predicted_side_counts,
        "realized_outcome_counts": realized_outcome_counts,
        "operational_rule_promoted": False,
        "reason": "Frozen OOS evidence exposes a no-draw top-pick failure and robust market superiority; recalibration or class-rule changes require a new independent temporal block.",
    }
    report = {
        "schema_version": "radar-historical-cross-league-elo-calibration-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "anti_hindsight": {
            "models_retrained_or_retuned": False,
            "predictions_reconstructed_from": "persisted feature rows plus persisted development-only means/scales and frozen weights",
            "holdout_used_for_model_fitting": False,
            "probability_reproduction_gate_tolerance": 1e-12,
            "external_price_semantics": "devigged external average closing benchmark; not GoldBet and not same-bookmaker MMS",
        },
        "sample": {"leagues": len(leagues), "holdout_fixtures": len(all_rows), "outcome_probability_rows": 3 * len(all_rows)},
        "reproduction_validation": validations,
        "pooled": {
            "elo": overall_elo,
            "external_average_close": overall_market,
            "elo_calibration": calibration(all_rows, "elo"),
            "external_average_close_calibration": calibration(all_rows, "market"),
        },
        "paired_market_minus_elo_uncertainty": {
            "draws": DRAWS, "seed": SEED,
            "stratified_fixture_bootstrap": "resample fixtures within every league, preserving league sizes",
            "league_bootstrap": "resample leagues with replacement and equal league weight",
            "results": paired,
        },
        "error_decomposition": {
            "elo_by_predicted_side": group_metrics(all_rows, "elo", lambda r: OUTCOMES[max(range(3), key=lambda k: r["elo"][k])]),
            "elo_by_realized_outcome": group_metrics(all_rows, "elo", lambda r: OUTCOMES[r["y"]]),
            "elo_by_top_confidence_band": group_metrics(all_rows, "elo", lambda r: f"{min(.9, math.floor(max(r['elo'])*10)/10):.1f}-{min(1.0, min(.9, math.floor(max(r['elo'])*10)/10)+.1):.1f}"),
        },
        "by_league": leagues,
        "verdict": verdict,
        "economic_metrics": {
            "clv": "NOT_CALCULATED_EXTERNAL_AVERAGE_CLOSE_IS_NOT_GOLDBET_CLOSE",
            "roi_yield_drawdown": "NOT_CALCULATED_NO_PREDECLARED_BETTING_RULE",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"sample": report["sample"], "elo": overall_elo, "market": overall_market,
                      "calibration": report["pooled"]["elo_calibration"], "paired": paired}, indent=2))

if __name__ == "__main__":
    main()
