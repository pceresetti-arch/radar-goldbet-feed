#!/usr/bin/env python3
"""Reusable hard gates for Radar player-value decisions.

These functions are deliberately small and dependency-free so workflows and
analysis builders can share the same BetFlag-only, minutes, correlation and
scorer-watch rules without reimplementing them inconsistently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

BETFLAG_DIRECT_SOURCE = "BETFLAG_AAMS_DIRECT"


@dataclass(frozen=True)
class PriceGateResult:
    verdict: str
    reason: str
    edge: float | None


@dataclass(frozen=True)
class ScorerWatchResult:
    status: str
    reason: str
    retain: bool


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


def scorer_watch_status(
    *,
    scouting_rank: int | None,
    in_official_xi: bool | None,
    expected_minutes: float | None,
    price_result: PriceGateResult | None,
    alternative_markets_available: bool,
    material_role_uncertainty: bool = False,
    max_watch_rank: int = 6,
    min_expected_minutes: float = 45.0,
    near_gate_ratio: float = 0.12,
) -> ScorerWatchResult:
    """Keep strong scorer candidates alive until a final explicit resolution.

    This gate separates *player retention* from the verdict on one specific
    market. A NO_BET anytime does not remove a strong player from the board.
    """
    if scouting_rank is None or scouting_rank < 1 or scouting_rank > max_watch_rank:
        return ScorerWatchResult("DROP_PLAYER", "OUTSIDE_SCOUTING_WATCH_RANGE", False)

    if in_official_xi is False:
        return ScorerWatchResult("DROP_PLAYER", "NOT_IN_OFFICIAL_XI", False)

    if expected_minutes is not None and expected_minutes < min_expected_minutes:
        return ScorerWatchResult("DROP_PLAYER", "EXPECTED_MINUTES_TOO_LOW", False)

    if material_role_uncertainty or in_official_xi is None:
        return ScorerWatchResult("WATCH_XI", "ROLE_OR_XI_NOT_FINAL", True)

    if price_result is None:
        return ScorerWatchResult("WATCH_PRICE", "NO_MARKET_PRICE_RESULT_YET", True)

    if price_result.verdict == "BET_ELIGIBLE":
        return ScorerWatchResult("BET", "BETFLAG_MARKET_ABOVE_GATE", True)

    if price_result.verdict == "ATTESA_QUOTA":
        return ScorerWatchResult("WATCH_PRICE", price_result.reason, True)

    if price_result.verdict == "NO_BET":
        # Preserve the player if the current market is close to gate or another
        # BetFlag market can fit the player's production profile better.
        if price_result.edge is not None:
            denominator = abs(price_result.edge) + 1.0
            # The exact gate is not carried in PriceGateResult; this normalized
            # proximity check intentionally errs on retention rather than drop.
            near_gate = abs(price_result.edge) / denominator <= near_gate_ratio
        else:
            near_gate = False
        if alternative_markets_available:
            return ScorerWatchResult("WATCH_MARKET", "ANYTIME_NO_BET_CHECK_ALTERNATIVES", True)
        if near_gate:
            return ScorerWatchResult("WATCH_PRICE", "PRICE_NEAR_GATE", True)
        return ScorerWatchResult("NO_BET_FINAL", "PRICE_BELOW_GATE_NO_ALT_MARKET", False)

    return ScorerWatchResult("NO_BET_FINAL", "UNHANDLED_PRICE_STATE", False)


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
    """Calculate conservative effective exposure for same-thesis selections."""
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
