#!/usr/bin/env python3
"""Reusable hard gates for Radar player-value decisions.

These functions are deliberately small and dependency-free so workflows and
analysis builders can share the same BetFlag-only, minutes and correlation
rules without reimplementing them inconsistently.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import prod
from typing import Iterable, Mapping

BETFLAG_DIRECT_SOURCE = "BETFLAG_AAMS_DIRECT"


@dataclass(frozen=True)
class PriceGateResult:
    verdict: str
    reason: str
    edge: float | None


def price_gate_verdict(
    *,
    current_price: float | None,
    final_gate: float | None,
    source_class: str | None,
    fresh: bool,
    exact_identity: bool,
    unique_match: bool = True,
) -> PriceGateResult:
    """Return the operational verdict allowed by the BetFlag-only price gate."""
    if source_class != BETFLAG_DIRECT_SOURCE:
        return PriceGateResult("ATTESA_QUOTA", "NON_BETFLAG_OPERATIONAL_SOURCE", None)
    if not fresh:
        return PriceGateResult("ATTESA_QUOTA", "BETFLAG_STALE", None)
    if not exact_identity or not unique_match:
        return PriceGateResult("ATTESA_QUOTA", "AMBIGUOUS_MARKET_IDENTITY", None)
    if current_price is None or final_gate is None or current_price <= 1 or final_gate <= 1:
        return PriceGateResult("ATTESA_QUOTA", "PRICE_OR_GATE_MISSING", None)
    edge = round(current_price - final_gate, 4)
    if current_price >= final_gate:
        return PriceGateResult("BET_ELIGIBLE", "BETFLAG_PRICE_AT_OR_ABOVE_GATE", edge)
    return PriceGateResult("NO_BET", "BETFLAG_PRICE_BELOW_GATE", edge)


def minutes_adjusted_event_probability(
    *,
    full_match_probability: float,
    minute_distribution: Mapping[str, float],
    minute_buckets: Mapping[str, float] | None = None,
) -> float:
    """Approximate event P after explicit uncertainty over playing time.

    `full_match_probability` is the player's event probability conditional on
    a full 90-minute exposure. Minute buckets are exposure fractions of 90.
    We convert the full-match P to a constant hazard and integrate over the
    supplied distribution. This is intentionally transparent and auditable.
    """
    if not 0 <= full_match_probability < 1:
        raise ValueError("full_match_probability must be in [0, 1)")
    default_buckets = {
        "le_45": 0.45,
        "46_65": 0.62,
        "66_80": 0.81,
        "gt_80": 0.96,
    }
    buckets = dict(default_buckets)
    if minute_buckets:
        buckets.update(minute_buckets)
    required = set(default_buckets)
    if set(minute_distribution) != required:
        raise ValueError(f"minute_distribution keys must be {sorted(required)}")
    total_weight = sum(float(v) for v in minute_distribution.values())
    if abs(total_weight - 1.0) > 1e-6:
        raise ValueError("minute_distribution probabilities must sum to 1")
    survival_90 = 1.0 - full_match_probability
    adjusted = 0.0
    for key, weight in minute_distribution.items():
        exposure = float(buckets[key])
        if not 0 <= exposure <= 1:
            raise ValueError("minute bucket exposure must be in [0, 1]")
        p_at_exposure = 1.0 - survival_90**exposure
        adjusted += float(weight) * p_at_exposure
    return round(adjusted, 6)


def correlation_cluster_exposure(
    stakes: Iterable[float],
    *,
    correlation_level: str,
    single_thesis_cap: float,
) -> dict:
    """Calculate conservative effective exposure for same-thesis selections.

    The multipliers are risk controls, not statistical correlation estimates.
    They intentionally prevent HIGH/VERY_HIGH clusters from masquerading as
    diversified tickets. The hard cap remains the controlling rule.
    """
    multipliers = {
        "LOW": 0.35,
        "MEDIUM": 0.60,
        "HIGH": 0.85,
        "VERY_HIGH": 1.00,
    }
    level = str(correlation_level).upper()
    if level not in multipliers:
        raise ValueError(f"unsupported correlation_level: {correlation_level}")
    values = [float(x) for x in stakes]
    if any(x < 0 for x in values):
        raise ValueError("stakes cannot be negative")
    nominal = round(sum(values), 2)
    if not values:
        effective = 0.0
    else:
        largest = max(values)
        remainder = nominal - largest
        effective = round(largest + multipliers[level] * remainder, 2)
    return {
        "correlation_level": level,
        "nominal_stake": nominal,
        "effective_exposure": effective,
        "single_thesis_cap": round(float(single_thesis_cap), 2),
        "cap_exceeded": effective > float(single_thesis_cap) + 1e-9,
    }


def scouting_hit(pre_match_ranked_players: Iterable[str], actual_scorers: Iterable[str], *, top_n: int = 3) -> bool:
    ranked = [str(x).strip().casefold() for x in pre_match_ranked_players if str(x).strip()]
    scorers = {str(x).strip().casefold() for x in actual_scorers if str(x).strip()}
    return bool(set(ranked[:top_n]) & scorers)
