import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.validate_radar_quote_consumer import validate


class QuoteConsumerPathTests(unittest.TestCase):
    def write(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_resolves_index_to_exact_fixture_file(self):
        now = datetime(2026, 9, 1, 17, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "feed/betflag-fixtures-index.json"
            fixture = root / "feed/betflag-fixtures/wolfsberger-lask-linz.json"
            self.write(index, {
                "generated_at": now.isoformat(),
                "source_class": "BETFLAG_AAMS_DIRECT",
                "source_healthy": True,
                "operationally_usable": True,
                "fixture_count": 1,
                "fixtures": [{"match": "Wolfsberger - LASK Linz", "file": "feed/betflag-fixtures/wolfsberger-lask-linz.json"}],
            })
            self.write(fixture, {
                "match": "Wolfsberger - LASK Linz",
                "source_class": "BETFLAG_AAMS_DIRECT",
                "source_healthy": True,
                "standard": [{"market": "1X2", "selection": "2", "odd": 1.4}],
                "players": [{"player": "Giacomo Vrioni", "markets": [{"market": "Marc", "quotes": [{"selection": "Si", "odd": 3.1}]}]}],
            })
            result = validate(index, "Wolfsberger - LASK Linz", now=now)
            self.assertEqual(result["status"], "READY")
            self.assertEqual(result["current_quote_status"], "CURRENT_BETFLAG_RECUPERATA")
            self.assertTrue(result["price_gate_source_eligible"])
            self.assertTrue(result["fixtures"][0]["source_provenance_eligible"])
            self.assertEqual(result["fixtures"][0]["player_quote_count"], 1)

    def test_rejects_external_or_proxy_source_for_price_gate(self):
        now = datetime(2026, 9, 1, 17, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "feed/betflag-fixtures-index.json"
            fixture = root / "feed/betflag-fixtures/example.json"
            self.write(index, {
                "generated_at": now.isoformat(),
                "source_class": "GOLDBET_PROXY",
                "source_healthy": True,
                "operationally_usable": True,
                "fixture_count": 1,
                "fixtures": [{"match": "Home - Away", "file": "feed/betflag-fixtures/example.json"}],
            })
            self.write(fixture, {
                "match": "Home - Away",
                "source_class": "GOLDBET_PROXY",
                "source_healthy": True,
                "standard": [{"market": "1X2", "selection": "1", "odd": 2.0}],
            })
            result = validate(index, "Home - Away", now=now)
            self.assertEqual(result["status"], "BETFLAG_PATH_READ_FAILURE")
            self.assertEqual(result["failure_stage"], "SOURCE_PROVENANCE")
            self.assertFalse(result["price_gate_source_eligible"])
            self.assertFalse(result["fixtures"][0]["price_gate_fixture_eligible"])

    def test_reports_exact_failure_stage(self):
        now = datetime(2026, 9, 1, 17, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "feed/betflag-fixtures-index.json"
            self.write(index, {
                "generated_at": now.isoformat(),
                "source_class": "BETFLAG_AAMS_DIRECT",
                "source_healthy": True,
                "operationally_usable": True,
                "fixture_count": 1,
                "fixtures": [{"match": "Wolfsberger - LASK Linz", "file": "feed/betflag-fixtures/missing.json"}],
            })
            result = validate(index, "Wolfsberger - LASK Linz", now=now)
            self.assertEqual(result["status"], "BETFLAG_PATH_READ_FAILURE")
            self.assertEqual(result["failure_stage"], "FIXTURE_FILE")


if __name__ == "__main__":
    unittest.main()
