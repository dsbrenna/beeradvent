Tier 1: Prototype / experiment (fun project)

# Beer Advent

A beer advent calendar. 24 beers are shuffled once for the year, and one is
revealed for each day from Dec 1 to Dec 24. Each beer is revealed one day ahead,
at about 5:00 pm Central the evening before (Dec 1's beer on Nov 30, Dec 24's on
Dec 23).

- **Web app:** https://dsbrenna.github.io/beeradvent/ (open on a phone, then Add to
  Home Screen for an app icon).
- **Push alert:** the same daily job sends a push through [ntfy](https://ntfy.sh)
  to anyone subscribed to the private topic.

## How it works

One scheduled GitHub Action (`.github/workflows/daily.yml`, 23:00 UTC daily):

1. `src/send_beer.py` reads the list, picks tomorrow's beer, and posts it to ntfy.
2. `src/publish.py` writes `revealed.json` containing only the days up to
   tomorrow, and the job deploys `site/` plus that file to GitHub Pages.

The full list is NOT in this repo. It lives at a private URL stored in the
`BEERS_URL` repository secret, so nobody can peek ahead from the public code or
site. The daily job runs with `BEER_ORDER=listed`, so the list is used in the
order given: line 1 is Dec 1, line 24 is Dec 24. Without that setting the list
is shuffled with a seed based on the year.

## Editing the beer list

Edit the list at the location behind `BEERS_URL`. It must be exactly 24 beers,
one per line (plain text) or the first column (CSV). Blank lines and lines
starting with `#` are ignored. Any other count makes the daily run fail instead
of guessing.

## Repository secrets

| Secret       | What it is                                              |
|--------------|---------------------------------------------------------|
| `BEERS_URL`  | Private URL of the 24-line list                         |
| `NTFY_TOPIC` | Long unguessable ntfy topic name the alerts are sent to |

## Run locally

No install needed, Python 3.11+ and the standard library only.

```
python3 -m unittest discover -s tests -v
BEERS_URL=beers.example.txt NTFY_TOPIC=dummy python3 src/send_beer.py --date 2026-12-05 --dry-run
BEERS_URL=beers.example.txt python3 src/publish.py --out /tmp/preview --date 2026-12-05
```

To preview the site, copy `site/*` next to the generated `revealed.json` and run
`python3 -m http.server` in that folder.

## Manual runs (Actions tab, "Run workflow")

- `test_message`: sends a test push now.
- `dry_run`: prints what would be sent, sends nothing, publishes nothing.
- `date`: pretends it is that date. This publicly reveals beers up to that date
  until the next run, so avoid it once the real list is in.

## Good to know

- GitHub can start scheduled runs several minutes late.
- GitHub turns off scheduled workflows after 60 days without repo activity.
- The site goes back to empty with the Dec 31 run (the reveal rule is December
  only, and it looks one day ahead).
- The year is fixed as 2026 in `site/index.html`.

## Files

- `src/send_beer.py`: list loading, shuffle, ntfy send
- `src/publish.py`: writes `revealed.json` for the site
- `site/`: the static web app and icons
- `scripts/make_icons.py`: regenerates the icons
- `tests/`: unit tests
- `docs/TODO.md`: punch list
