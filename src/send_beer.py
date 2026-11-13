#!/usr/bin/env python3
"""Beer advent calendar notifier.

Usage:
    BEERS_URL=beers.example.txt NTFY_TOPIC=mytopic python3 src/send_beer.py [--dry-run]
        [--date YYYY-MM-DD] [--show-schedule] [--test-message]

Env: NTFY_TOPIC, BEERS_URL (required); NTFY_SERVER, SEED (optional).
"""

import argparse
import csv
import io
import os
import random
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

DAYS = 24
# Each beer is revealed this many days before the day it is for, so the 5pm run
# on Nov 30 announces the Dec 1 beer and the run on Dec 23 announces Dec 24.
LEAD_DAYS = 1
DEFAULT_SERVER = "https://ntfy.sh"
TIMEZONE = "America/Chicago"
TIMEOUT = 20
HEADER_WORDS = {"beer", "beers", "name"}
TEST_BODY = "Beer Advent test: notifications are working"


class BeerError(Exception):
    """A user-facing error that should end the run with a non-zero exit."""


def read_source(source):
    """Return the text at an http(s) URL, file:// URL, or local path."""
    parsed = urllib.parse.urlparse(source)
    try:
        if parsed.scheme in ("http", "https"):
            with urllib.request.urlopen(source, timeout=TIMEOUT) as resp:
                return resp.read().decode("utf-8-sig")
        if parsed.scheme == "file":
            path = urllib.request.url2pathname(parsed.path)
        else:
            path = source
        with open(path, encoding="utf-8-sig") as f:
            return f.read()
    except urllib.error.HTTPError as e:
        raise BeerError(f"Could not fetch beer list: HTTP {e.code} from {source}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise BeerError(f"Could not read beer list from {source}: {e}") from e


def parse_beers(text):
    """Parse plain text (one per line) or CSV (first column) into a clean list."""
    beers = []
    for row in csv.reader(io.StringIO(text)):
        if not row:
            continue
        cell = row[0].strip()
        if not cell or cell.startswith("#"):
            continue
        if not beers and cell.lower() in HEADER_WORDS:
            continue
        beers.append(cell)
    return beers


def load_beers(source):
    beers = parse_beers(read_source(source))
    if len(beers) != DAYS:
        raise BeerError(f"Expected exactly {DAYS} beers, found {len(beers)} in {source}")
    return beers


def permutation(seed):
    """Permutation of row indices 0..23. Day N gets row perm[N-1]."""
    perm = list(range(DAYS))
    random.Random(seed).shuffle(perm)
    return perm


def beer_for_day(beers, day, seed):
    return beers[permutation(seed)[day - 1]]


def resolve_seed(target):
    raw = os.environ.get("SEED", "").strip()
    if not raw:
        return target.year
    # Numeric seeds become ints so SEED=2026 matches the default for 2026.
    return int(raw) if raw.lstrip("-").isdigit() else raw


def advent_day(target):
    """Return 1..24 if target is Dec 1 to Dec 24, else None."""
    if target.month == 12 and 1 <= target.day <= DAYS:
        return target.day
    return None


def reveal_date(run_date):
    """The calendar date whose beer is revealed by the run on run_date."""
    return run_date + timedelta(days=LEAD_DAYS)


def today_chicago():
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def build_request(server, topic, title, body):
    url = f"{server.rstrip('/')}/{urllib.parse.quote(topic, safe='')}"
    headers = {"Title": title, "Tags": "beer"}
    return urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")


def send(req):
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        raise BeerError(f"ntfy rejected the push: HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise BeerError(f"Could not reach ntfy: {e}") from e
    if not 200 <= status < 300:
        raise BeerError(f"ntfy returned unexpected status {status}")
    return status


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise BeerError(f"Missing required environment variable {name}")
    return value


def deliver(title, body, dry_run):
    server = os.environ.get("NTFY_SERVER", "").strip() or DEFAULT_SERVER
    topic = require_env("NTFY_TOPIC")
    if dry_run:
        print(f"[dry-run] Would POST to {server.rstrip('/')}/<NTFY_TOPIC>")
        print(f"[dry-run] Title: {title}")
        print(f"[dry-run] Body: {body}")
        return
    send(build_request(server, topic, title, body))
    print(f"Sent: {title}: {body}")


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date {value!r}, expected YYYY-MM-DD")


def run(argv=None):
    parser = argparse.ArgumentParser(description="Beer advent calendar notifier")
    parser.add_argument("--dry-run", action="store_true", help="print, do not POST")
    parser.add_argument("--date", type=parse_date, help="target date YYYY-MM-DD (default: today in Chicago)")
    parser.add_argument("--show-schedule", action="store_true", help="print all 24 days (spoilers)")
    parser.add_argument("--test-message", action="store_true", help="send a test push regardless of date")
    args = parser.parse_args(argv)

    if args.test_message:
        deliver("Beer Advent test", TEST_BODY, args.dry_run)
        return 0

    run_date = args.date or today_chicago()
    target = reveal_date(run_date)
    seed = resolve_seed(target)

    if args.show_schedule:
        beers = load_beers(require_env("BEERS_URL"))
        perm = permutation(seed)
        print(f"Schedule (seed {seed}):")
        for n in range(1, DAYS + 1):
            print(f"Dec {n:2d}: {beers[perm[n - 1]]}")
        return 0

    day = advent_day(target)
    if day is None:
        print(f"{run_date.isoformat()}: nothing to send (next day {target.isoformat()} is outside Dec 1 to 24)")
        return 0

    beers = load_beers(require_env("BEERS_URL"))
    beer = beer_for_day(beers, day, seed)
    deliver(f"Beer Advent Day {day}", f"Tomorrow's beer (Dec {day}): {beer}", args.dry_run)
    return 0


def main(argv=None):
    try:
        return run(argv)
    except BeerError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
