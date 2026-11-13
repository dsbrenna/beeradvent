# Beer Advent: project notes

- **Tier:** 1 (prototype, fun project). Tests exist anyway because the reveal rule is the one thing that must not break.
- **Stack:** Python 3.11+ standard library only; static HTML/CSS/JS site with no build step; GitHub Actions cron; GitHub Pages; ntfy for push.
- **This repo is PUBLIC.** Never commit the real beer list, the ntfy topic, or any personal details. Commits use the GitHub no-reply address.

## Decisions

- **One public repo, list kept outside it.** The owner's GitHub plan cannot serve Pages from a private repo, and a cross-repo deploy key was not wanted. So code and site are public, and the list lives at a private URL in the `BEERS_URL` secret.
- **One day ahead.** `LEAD_DAYS = 1` in `send_beer.py`: the 5pm run on date X reveals and announces the beer for X+1, so people can buy it the day before. Both scripts and the page's door times follow this one rule.
- **Publish only reached days.** `publish.py` regenerates `revealed.json` in full each run from the list, seed, and date, so a missed day self-heals and unrevealed beers never reach the public site. A test asserts no hidden name appears in the output.
- **Shuffle keyed on line position, seeded by year.** Editing a beer's text keeps its day. Changing the number or order of lines reshuffles.
- **Pages deployed by Actions artifact** (`upload-pages-artifact` + `deploy-pages`), so no generated files are committed and no extra credentials exist.
- **No service worker.** Cached data would show stale doors; Add to Home Screen works without one.
- **Site renders only from `revealed.json`.** The page never decides on its own that a door is open.

## Gotchas

- Workflow logs are public. Do not add steps that print the list or the schedule (`--show-schedule` must never run in CI).
- A manual run with a `date` input publicly reveals beers up to that date.
- Actions cron can run late; the page says the door is due and re-checks every minute.
