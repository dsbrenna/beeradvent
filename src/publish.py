#!/usr/bin/env python3
"""Write revealed.json for the public Beer Advent site.

Usage:
    BEERS_URL=beers.txt python3 src/publish.py --out DIR [--date YYYY-MM-DD]

Writes DIR/revealed.json with only the days already reached (Dec 1 up to the
target date, America/Chicago). Nothing about unrevealed days is ever written.
Env: BEERS_URL (required); SEED (optional, same meaning as send_beer).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from send_beer import (
    DAYS,
    BeerError,
    beer_for_day,
    load_beers,
    parse_date,
    require_env,
    resolve_seed,
    today_chicago,
)

FILENAME = "revealed.json"


def revealed_count(target):
    """Number of days revealed on target: 0 outside December, else min(day, 24)."""
    if target.month != 12:
        return 0
    return min(target.day, DAYS)


def build_payload(beers, target, seed, now=None):
    count = revealed_count(target)
    days = [{"day": n, "beer": beer_for_day(beers, n, seed)} for n in range(1, count + 1)]
    updated = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    return {"year": target.year, "updated": updated, "days": days}


def write_revealed(out_dir, payload):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, FILENAME)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return path


def run(argv=None):
    parser = argparse.ArgumentParser(description="Write revealed.json for the public site")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--date", type=parse_date, help="target date YYYY-MM-DD (default: today in Chicago)")
    args = parser.parse_args(argv)

    target = args.date or today_chicago()
    count = revealed_count(target)
    # Validate the list (exactly 24) even when nothing is revealed, so a broken
    # list fails loudly in November instead of on Dec 1.
    beers = load_beers(require_env("BEERS_URL"))
    payload = build_payload(beers, target, resolve_seed(target))
    path = write_revealed(args.out, payload)
    print(f"{target.isoformat()}: wrote {path} with {count} revealed day(s)")
    return 0


def main(argv=None):
    try:
        return run(argv)
    except BeerError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
