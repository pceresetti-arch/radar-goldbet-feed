#!/usr/bin/env python3
import json
import math
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://radar-goldbet.p-ceresetti.workers.dev/odds"
PAGE_SIZE = 2000
MAX_PAGES = int(os.environ.get("GOLDBET_MAX_PAGES", "12"))
MAX_RETRIES = int(os.environ.get("GOLDBET_MAX_RETRIES", "5"))
BETWEEN_PAGES_SECONDS = float(os.environ.get("GOLDBET_PAGE_DELAY", "2.5"))
HORIZON_HOURS = int(os.environ.get("GOLDBET_HORIZON_HOURS", "72"))

OUT = pathlib.Path("feed/goldbet-standard-safe-current.json")
HEALTH = pathlib.Path("feed/goldbet-standard-safe-health.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

now = datetime.now(timezone.utc)
now_iso = now.isoformat()
token = os.environ.get("BRIDGE_TOKEN", "").strip()
if not token:
    raise SystemExit("Missing BRIDGE_TOKEN")

def parse_dt(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None

def retry_after_seconds(headers, attempt):
    raw = headers.get("Retry-After") if headers else None
    if raw:
        try:
            return max(1.0, min(float(raw), 60.0))
        except Exception:
            pass
    return min(2.0 * (2 ** attempt), 30.0)

def fetch_page(offset):
    params = urllib.parse.urlencode({
        "token": token,
        "bookmakers": "goldbet",
        "state": "prematch",
        "limit": str(PAGE_SIZE),
        "offset": str(offset),
    })
    url = BASE + "?" + params
    last_error = None
    attempts = []
    for attempt in range(MAX_RETRIES):
        started = time.monotonic()
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "RadarGoldBetSafe/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=75) as response:
                body = response.read().decode("utf-8", "replace")
                payload = json.loads(body)
                elapsed = round(time.monotonic() - started, 3)
                attempts.append({"attempt": attempt + 1, "http": response.status, "seconds": elapsed})
                return {
                    "ok": True,
                    "offset": offset,
                    "count": payload.get("count"),
                    "rows": payload.get("odds") or [],
                    "attempts": attempts,
                    "error": None,
                }
        except urllib.error.HTTPError as exc:
            elapsed = round(time.monotonic() - started, 3)
            attempts.append({"attempt": attempt + 1, "http": exc.code, "seconds": elapsed})
            last_error = f"HTTP {exc.code}"
            if exc.code != 429 or attempt == MAX_RETRIES - 1:
                break
            time.sleep(retry_after_seconds(exc.headers, attempt))
        except Exception as exc:
            elapsed = round(time.monotonic() - started, 3)
            attempts.append({"attempt": attempt + 1, "error": type(exc).__name__, "seconds": elapsed})
            last_error = f"{type(exc).__name__}: {str(exc)[:160]}"
            if attempt == MAX_RETRIES - 1:
                break
            time.sleep(min(2.0 * (2 ** attempt), 20.0))
    return {
        "ok": False,
        "offset": offset,
        "count": None,
        "rows": [],
        "attempts": attempts,
        "error": last_error or "unknown error",
    }

def market_relevant(name):
    s = str(name or "").lower()
    tokens = (
        "1x2", "over", "under", "goal", "btts", "both teams",
        "double", "doppia", "draw no bet", "dnb", "handicap",
        "total", "totale",
    )
    return any(token in s for token in tokens)

def goldbet_bookmaker(record):
    books = record.get("bookmakers") or []
    if isinstance(books, list):
        return next(
            (b for b in books if isinstance(b, dict) and str(b.get("key", "")).lower() == "goldbet"),
            None,
        )
    if isinstance(books, dict):
        bm = books.get("goldbet") or books.get("GoldBet") or books
        return bm if isinstance(bm, dict) else None
    return None

first = fetch_page(0)
page_results = [first]
expected_total = int(first.get("count") or 0) if first.get("ok") else 0
needed_pages = max(1, math.ceil(expected_total / PAGE_SIZE)) if expected_total else 1
capped = needed_pages > MAX_PAGES
pages_to_fetch = min(needed_pages, MAX_PAGES)

if first.get("ok"):
    for page_index in range(1, pages_to_fetch):
        time.sleep(BETWEEN_PAGES_SECONDS)
        page_results.append(fetch_page(page_index * PAGE_SIZE))

complete = (
    bool(first.get("ok"))
    and not capped
    and len(page_results) == needed_pages
    and all(page.get("ok") for page in page_results)
)

raw_rows = []
for page in page_results:
    if page.get("ok"):
        raw_rows.extend(page.get("rows") or [])

window_start = now - timedelta(hours=2)
window_end = now + timedelta(hours=HORIZON_HOURS)
rows = []
seen = set()

for record in raw_rows:
    if not isinstance(record, dict) or not market_relevant(record.get("market")):
        continue
    start = parse_dt(record.get("commence_time"))
    if not start or start < window_start or start > window_end:
        continue
    bookmaker = goldbet_bookmaker(record)
    if not isinstance(bookmaker, dict):
        continue
    outcomes = bookmaker.get("outcomes") or {}
    if not isinstance(outcomes, dict):
        continue
    for selection, raw_price in outcomes.items():
        try:
            price = float(raw_price)
        except Exception:
            continue
        item = {
            "source_class": "GOLDBET_DIRECT_STANDARD",
            "bookmaker": "goldbet",
            "event_id": record.get("event_id"),
            "event": record.get("event") or f"{record.get('home_team', '')} - {record.get('away_team', '')}".strip(" -"),
            "league": record.get("league"),
            "commence_time": start.isoformat(),
            "market": record.get("market"),
            "line": record.get("line"),
            "scope": record.get("scope"),
            "period": record.get("period"),
            "selection": str(selection),
            "price": price,
            "source_last_update": bookmaker.get("last_update"),
        }
        dedupe = (
            str(item["event_id"]),
            str(item["market"]),
            str(item["line"]),
            str(item["scope"]),
            str(item["period"]),
            str(item["selection"]),
        )
        if dedupe in seen:
            continue
        seen.add(dedupe)
        rows.append(item)

rows.sort(key=lambda x: (
    x.get("commence_time") or "",
    str(x.get("event") or ""),
    str(x.get("market") or ""),
    str(x.get("selection") or ""),
))

last_good_generated_at = None
if OUT.exists():
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
        last_good_generated_at = old.get("generated_at")
    except Exception:
        pass

acquisition_fresh = bool(complete and rows)
status = "OK" if acquisition_fresh else ("PARTIAL" if raw_rows else "ERROR")
errors = [
    {"offset": page.get("offset"), "error": page.get("error"), "attempts": page.get("attempts")}
    for page in page_results if not page.get("ok")
]
if capped:
    errors.append({
        "error": "PAGE_CAP_EXCEEDED",
        "needed_pages": needed_pages,
        "max_pages": MAX_PAGES,
    })
if complete and not rows:
    status = "EMPTY"
    errors.append({"error": "NO_RELEVANT_UPCOMING_GOLDBET_ROWS"})

health = {
    "generated_at": now_iso,
    "source": BASE,
    "source_class": "GOLDBET_DIRECT_STANDARD",
    "status": status,
    "acquisition_fresh": acquisition_fresh,
    "expected_total_rows": expected_total,
    "needed_pages": needed_pages,
    "fetched_pages": len([p for p in page_results if p.get("ok")]),
    "page_size": PAGE_SIZE,
    "raw_rows_received": len(raw_rows),
    "operational_rows": len(rows),
    "horizon_hours": HORIZON_HOURS,
    "last_good_generated_at_before_run": last_good_generated_at,
    "errors": errors,
    "page_attempts": [
        {"offset": p.get("offset"), "ok": p.get("ok"), "attempts": p.get("attempts")}
        for p in page_results
    ],
    "contract": (
        "Fresh current GoldBet standard prices are usable only when acquisition_fresh=true. "
        "A failed/partial run must never make preserved historical prices appear current."
    ),
}
HEALTH.write_text(json.dumps(health, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if acquisition_fresh:
    snapshot = {
        "generated_at": now_iso,
        "source": BASE,
        "source_class": "GOLDBET_DIRECT_STANDARD",
        "acquisition_fresh": True,
        "horizon_hours": HORIZON_HOURS,
        "row_count": len(rows),
        "rows": rows,
    }
    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(json.dumps({
    "status": status,
    "acquisition_fresh": acquisition_fresh,
    "expected_total_rows": expected_total,
    "fetched_pages": health["fetched_pages"],
    "needed_pages": needed_pages,
    "operational_rows": len(rows),
    "errors": errors,
}, ensure_ascii=False))
