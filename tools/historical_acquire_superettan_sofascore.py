#!/usr/bin/env python3
import csv
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path("feed/historical/superettan")
OUT.mkdir(parents=True, exist_ok=True)
TOURNAMENT_ID = 46
TARGET_YEARS = [2022, 2023, 2024, 2025]
BASE = "https://api.sofascore.com/api/v1"


def fetch_json(url):
    errors = []
    for attempt in range(1, 5):
        try:
            req = Request(url, headers={"User-Agent": "radar-historical-backtest/1.0"})
            with urlopen(req, timeout=45) as response:
                body = response.read()
                return json.loads(body), body, getattr(response, "status", 200), attempt, errors
        except Exception as exc:
            errors.append(repr(exc))
            if attempt < 4:
                time.sleep(attempt * 3)
    raise RuntimeError(json.dumps({"url": url, "errors": errors}))


def season_year(season):
    for key in ("year", "name"):
        value = str(season.get(key, ""))
        for year in TARGET_YEARS:
            if str(year) in value:
                return year
    return None


def main():
    generated = datetime.now(timezone.utc).isoformat()
    seasons_url = f"{BASE}/unique-tournament/{TOURNAMENT_ID}/seasons"
    seasons_payload, seasons_body, status, attempt, prior_errors = fetch_json(seasons_url)
    available = seasons_payload.get("seasons", [])
    selected = {}
    for season in available:
        year = season_year(season)
        if year in TARGET_YEARS and year not in selected:
            selected[year] = season
    missing = sorted(set(TARGET_YEARS) - set(selected))
    if missing:
        raise RuntimeError(f"missing target seasons: {missing}")

    normalized = []
    season_reports = []
    for year in TARGET_YEARS:
        season = selected[year]
        season_id = season["id"]
        raw_events = []
        page_hashes = []
        for page in range(20):
            url = f"{BASE}/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/events/last/{page}"
            payload, body, page_status, page_attempt, page_errors = fetch_json(url)
            events = payload.get("events", [])
            raw_events.extend(events)
            page_hashes.append({
                "page": page, "url": url, "http_status": page_status,
                "attempt": page_attempt, "prior_errors": page_errors,
                "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                "events": len(events)
            })
            if not payload.get("hasNextPage", False):
                break
        else:
            raise RuntimeError(f"pagination cap reached for {year}")

        by_id = {}
        for event in raw_events:
            event_id = event.get("id")
            if event_id is not None:
                by_id[event_id] = event
        raw_path = OUT / f"sofascore-superettan-{year}-raw.json"
        raw_text = json.dumps({
            "source_url_pattern": f"{BASE}/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/events/last/{{page}}",
            "tournament_id": TOURNAMENT_ID, "season": season,
            "pages": page_hashes, "events": list(by_id.values())
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        raw_path.write_text(raw_text, encoding="utf-8")

        accepted = []
        excluded = Counter()
        for event in by_id.values():
            if event.get("tournament", {}).get("uniqueTournament", {}).get("id") != TOURNAMENT_ID:
                excluded["wrong_tournament"] += 1
                continue
            if event.get("season", {}).get("id") != season_id:
                excluded["wrong_season"] += 1
                continue
            round_number = event.get("roundInfo", {}).get("round")
            if not isinstance(round_number, int) or not (1 <= round_number <= 30):
                excluded["outside_rounds_1_30"] += 1
                continue
            if event.get("status", {}).get("type") != "finished":
                excluded["not_finished"] += 1
                continue
            home_score = event.get("homeScore", {}).get("current")
            away_score = event.get("awayScore", {}).get("current")
            if not isinstance(home_score, int) or not isinstance(away_score, int):
                excluded["missing_final_score"] += 1
                continue
            start = event.get("startTimestamp")
            if not isinstance(start, int):
                excluded["missing_start_timestamp"] += 1
                continue
            home = event.get("homeTeam", {})
            away = event.get("awayTeam", {})
            accepted.append({
                "season": str(year), "event_id": event["id"],
                "kickoff_utc": datetime.fromtimestamp(start, tz=timezone.utc).isoformat(),
                "round": round_number,
                "home_team_id": home.get("id"), "home_team": home.get("name"),
                "away_team_id": away.get("id"), "away_team": away.get("name"),
                "home_goals": home_score, "away_goals": away_score,
                "result": "H" if home_score > away_score else ("A" if away_score > home_score else "D"),
                "source": "Sofascore public API", "odds_available": False
            })
        accepted.sort(key=lambda row: (row["kickoff_utc"], row["event_id"]))
        apps = Counter()
        keys = []
        for row in accepted:
            apps[(row["home_team_id"], row["home_team"])] += 1
            apps[(row["away_team_id"], row["away_team"])] += 1
            keys.append(row["event_id"])
        normalized.extend(accepted)
        season_reports.append({
            "season": str(year), "sofascore_season_id": season_id,
            "raw_unique_events": len(by_id), "accepted_regular_events": len(accepted),
            "excluded": dict(sorted(excluded.items())), "clubs": len(apps),
            "appearance_values": sorted(set(apps.values())),
            "team_appearances": {f"{team_id}:{name}": count for (team_id, name), count in sorted(apps.items())},
            "duplicate_event_ids": len(keys) - len(set(keys)),
            "raw_snapshot": str(raw_path),
            "raw_snapshot_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            "pages": page_hashes
        })

    expected_ok = all(
        item["accepted_regular_events"] == 240
        and item["clubs"] == 16
        and item["appearance_values"] == [30]
        and item["duplicate_event_ids"] == 0
        for item in season_reports
    )
    csv_path = OUT / "superettan-2022-2025-results.csv"
    fields = [
        "season", "event_id", "kickoff_utc", "round", "home_team_id", "home_team",
        "away_team_id", "away_team", "home_goals", "away_goals", "result", "source", "odds_available"
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(normalized)
    csv_bytes = csv_path.read_bytes()

    report = {
        "schema_version": "radar-historical-superettan-source-profile-v1",
        "generated_at": generated,
        "competition": "Superettan", "country": "Sweden",
        "source_provider": "Sofascore public API",
        "source_class": "PUBLIC_FIXTURE_RESULT_SOURCE_NO_HISTORICAL_ODDS",
        "source_seasons_endpoint": seasons_url,
        "source_seasons_http_status": status,
        "source_seasons_fetch_attempt": attempt,
        "source_seasons_prior_errors": prior_errors,
        "source_seasons_sha256": hashlib.sha256(seasons_body).hexdigest(),
        "selection_rule_frozen_before_outcome_join": {
            "unique_tournament_id": TOURNAMENT_ID,
            "target_seasons": TARGET_YEARS,
            "regular_rounds_inclusive": [1, 30],
            "finished_status_required": True,
            "no_result_or_odds_based_selection": True
        },
        "seasons": season_reports,
        "normalized_dataset": str(csv_path),
        "normalized_rows": len(normalized),
        "normalized_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "development_rows_if_frozen": sum(row["season"] in {"2022", "2023", "2024"} for row in normalized),
        "holdout_rows_if_frozen": sum(row["season"] == "2025" for row in normalized),
        "historical_odds_rows": 0,
        "market_benchmark_allowed": False,
        "same_bookmaker_open_close_allowed": False,
        "anti_hindsight": {
            "outcomes_used_for_source_or_phase_selection": False,
            "model_built": False, "holdout_evaluated": False,
            "missing_odds_invented": False, "playoffs_included": False
        },
        "status": "ACCEPTED_STRUCTURAL_RESULTS_READY_NO_ODDS" if expected_ok else "QUARANTINED_STRUCTURE_GATE_FAILED",
        "decision": "Freeze 2022-2024 development and 2025 holdout only if every season passes 240 fixtures, 16 clubs and 30 appearances per club. Closing-market comparisons remain forbidden because this source contains no historical prices."
    }
    (OUT / "source-profile-v1.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "rows": len(normalized), "seasons": season_reports}, indent=2, ensure_ascii=False))
    if not expected_ok:
        raise RuntimeError("Superettan structural source failed frozen 240/16/30 gate")


if __name__ == "__main__":
    main()
