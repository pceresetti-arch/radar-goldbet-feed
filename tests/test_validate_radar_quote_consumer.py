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
                "source_healthy": True,
                "operationally_usable": True,
                "fixture_count": 1,
                "fixtures": [{"match": "Wolfsberger - LASK Linz", "file": "feed/betflag-fixtures/wolfsberger-lask-linz.json"}],
            })
            self.write(fixture, {
                "match": "Wolfsberger - LASK Linz",
                "source_healthy": True,
                "standard": [{"market": "1X2", "selection": "2", "odd": 1.4}],
                "players": [{"player": "Giacomo Vrioni", "markets": [{"market": "Marc", "quotes": [{"selection": "Si", "odd": 3.1}]}]}],
            })
            result = validate(index, "Wolfsberger - LASK Linz", now=now)
            self.assertEqual(result["status"], "READY")
            self.assertEqual(result["current_quote_status"], "CURRENT_BETFLAG_RECUPERATA")
            self.assertEqual(result["fixtures"][0]["player_quote_count"], 1)

    def test_reports_exact_failure_stage(self):
        now = datetime(2026, 9, 1, 17, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "feed/betflag-fixtures-index.json"
            self.write(index, {
                "generated_at": now.isoformat(),
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
