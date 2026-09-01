#!/usr/bin/env python3
import csv
import hashlib
import json
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path("feed/historical/spain1")
OUT.mkdir(parents=True, exist_ok=True)
RAW = OUT / "football-data-ESP1.csv"
PROFILE = OUT / "source-profile.json"
SOURCES = [
    ("2022/2023", "https://www.football-data.co.uk/mmz4281/2223/SP1.csv"),
    ("2023/2024", "https://www.football-data.co.uk/mmz4281/2324/SP1.csv"),
    ("2024/2025", "https://www.football-data.co.uk/mmz4281/2425/SP1.csv"),
    ("2025/2026", "https://www.football-data.co.uk/mmz4281/2526/SP1.csv"),
]
OUT_FIELDS = ["Season","League","Date","Time","Home","Away","HG","AG","Res","AvgCH","AvgCD","AvgCA"]
REQUIRED_SOURCE = ["Date","HomeTeam","AwayTeam","FTHG","FTAG","FTR","AvgCH","AvgCD","AvgCA"]

def fetch(url):
    req = Request(url, headers={"User-Agent":"radar-historical-backtest/1.0"})
    with urlopen(req, timeout=45) as r:
        data = r.read()
        return data, getattr(r, "status", 200), dict(r.headers.items())

def main():
    all_rows = []
    files = []
    failures = []
    for season, url in SOURCES:
        try:
            data, status, headers = fetch(url)
            text = data.decode("utf-8-sig")
            rows = list(csv.DictReader(StringIO(text)))
            missing = [k for k in REQUIRED_SOURCE if k not in (rows[0].keys() if rows else [])]
            if missing:
                raise ValueError(f"missing columns {missing}")
            if len(rows) != 380:
                raise ValueError(f"expected 380 LaLiga fixtures, got {len(rows)}")
            source_path = OUT / f"football-data-SP1-{season.replace('/','-')}.csv"
            source_path.write_bytes(data)
            for r in rows:
                all_rows.append({
                    "Season": season,
                    "League": "LaLiga",
                    "Date": r.get("Date",""),
                    "Time": r.get("Time",""),
                    "Home": r.get("HomeTeam",""),
                    "Away": r.get("AwayTeam",""),
                    "HG": r.get("FTHG",""),
                    "AG": r.get("FTAG",""),
                    "Res": r.get("FTR",""),
                    "AvgCH": r.get("AvgCH",""),
                    "AvgCD": r.get("AvgCD",""),
                    "AvgCA": r.get("AvgCA",""),
                })
            files.append({
                "season": season, "url": url, "http_status": status, "rows": len(rows),
                "sha256": hashlib.sha256(data).hexdigest(),
                "last_modified": headers.get("Last-Modified"),
                "path": str(source_path),
            })
        except Exception as exc:
            failures.append({"season": season, "url": url, "error": repr(exc)})
    if failures:
        raise RuntimeError(json.dumps(failures, ensure_ascii=False))
    with RAW.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(all_rows)
    profile = {
        "schema_version": "radar-historical-spain1-source-profile-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_class": "EXTERNAL_HISTORICAL_MARKET_BENCHMARK",
        "source_provider": "Football-Data",
        "competition": "LaLiga",
        "files": files,
        "combined_path": str(RAW),
        "combined_rows": len(all_rows),
        "combined_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
        "quality": {
            "expected_rows": 1520,
            "row_count_ok": len(all_rows) == 1520,
            "failures": failures,
            "timezone_claimed": False,
        },
        "provenance_limits": {
            "goldbet_true_open": False,
            "same_bookmaker_open_close": False,
            "closing_columns": "Football-Data average closing odds; external benchmark only",
        },
    }
    PROFILE.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"source_files":len(files),"rows":len(all_rows),"failures":len(failures)}, indent=2))

if __name__ == "__main__":
    main()
