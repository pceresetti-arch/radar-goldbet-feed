import unittest

from scripts.radar_player_value_gates import (
    correlation_cluster_exposure,
    minutes_adjusted_event_probability,
    price_gate_verdict,
    scouting_hit,
)


class RadarPlayerValueGateTests(unittest.TestCase):
    def test_external_price_can_never_be_operational_bet(self):
        result = price_gate_verdict(
            current_price=3.5,
            final_gate=2.8,
            source_class="GOLDBET_PROXY",
            fresh=True,
            exact_identity=True,
        )
        self.assertEqual(result.verdict, "ATTESA_QUOTA")
        self.assertEqual(result.reason, "NON_BETFLAG_OPERATIONAL_SOURCE")

    def test_verified_betflag_price_above_gate_is_eligible(self):
        result = price_gate_verdict(
            current_price=3.05,
            final_gate=2.85,
            source_class="BETFLAG_AAMS_DIRECT",
            fresh=True,
            exact_identity=True,
        )
        self.assertEqual(result.verdict, "BET_ELIGIBLE")
        self.assertAlmostEqual(result.edge, 0.20)

    def test_stale_betflag_price_is_wait_not_bet(self):
        result = price_gate_verdict(
            current_price=3.05,
            final_gate=2.85,
            source_class="BETFLAG_AAMS_DIRECT",
            fresh=False,
            exact_identity=True,
        )
        self.assertEqual(result.verdict, "ATTESA_QUOTA")

    def test_game_state_minutes_risk_reduces_player_probability(self):
        full_match_p = 0.35
        safe = minutes_adjusted_event_probability(
            full_match_probability=full_match_p,
            minute_distribution={"le_45": 0.05, "46_65": 0.10, "66_80": 0.25, "gt_80": 0.60},
        )
        risky = minutes_adjusted_event_probability(
            full_match_probability=full_match_p,
            minute_distribution={"le_45": 0.35, "46_65": 0.30, "66_80": 0.25, "gt_80": 0.10},
        )
        self.assertLess(risky, safe)
        self.assertLess(risky, full_match_p)

    def test_highly_correlated_triple_breaches_single_thesis_cap(self):
        result = correlation_cluster_exposure(
            [5, 5, 5], correlation_level="VERY_HIGH", single_thesis_cap=5
        )
        self.assertEqual(result["nominal_stake"], 15.0)
        self.assertEqual(result["effective_exposure"], 15.0)
        self.assertTrue(result["cap_exceeded"])

    def test_scorer_audit_tracks_top_n_discovery(self):
        self.assertTrue(scouting_hit(["Tabakovic", "Konate", "Kara"], ["Tabakovic"], top_n=3))
        self.assertFalse(scouting_hit(["Kara", "Adamsen"], ["Tabakovic"], top_n=2))


if __name__ == "__main__":
    unittest.main()
