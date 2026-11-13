"""Unit tests for send_beer. No real network calls: urlopen is always mocked."""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import send_beer  # noqa: E402

BEERS = [f"Beer {i:02d}" for i in range(1, 25)]


def write_temp(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


class ParseTests(unittest.TestCase):
    def test_plain_text_with_blanks_and_comments(self):
        text = "# my list\n\n  Pliny the Elder  \n# skip\nHeady Topper\n\n"
        self.assertEqual(send_beer.parse_beers(text), ["Pliny the Elder", "Heady Topper"])

    def test_csv_with_header_uses_first_column(self):
        text = "Beer,Brewery,ABV\nZombie Dust,3 Floyds,6.2\n\n\"Two Hearted, Ale\",Bells,7\n#x,y\n"
        self.assertEqual(send_beer.parse_beers(text), ["Zombie Dust", "Two Hearted, Ale"])

    def test_header_variants_skipped(self):
        for header in ("beer", "BEERS", "Name"):
            self.assertEqual(send_beer.parse_beers(f"{header}\nA\nB\n"), ["A", "B"])

    def test_header_word_only_skipped_as_first_row(self):
        self.assertEqual(send_beer.parse_beers("A\nName\n"), ["A", "Name"])

    def test_load_local_path_and_file_url(self):
        path = write_temp("beers\n" + "\n".join(BEERS) + "\n")
        self.addCleanup(os.unlink, path)
        self.assertEqual(send_beer.load_beers(path), BEERS)
        self.assertEqual(send_beer.load_beers(Path(path).as_uri()), BEERS)

    def test_wrong_count_fails_with_count(self):
        path = write_temp("\n".join(BEERS[:23]))
        self.addCleanup(os.unlink, path)
        with self.assertRaises(send_beer.BeerError) as ctx:
            send_beer.load_beers(path)
        self.assertIn("found 23", str(ctx.exception))

    def test_missing_file_is_beer_error(self):
        with self.assertRaises(send_beer.BeerError):
            send_beer.load_beers("/nonexistent/beers.txt")


class ShuffleTests(unittest.TestCase):
    def test_listed_order_skips_shuffle(self):
        with mock.patch.dict(os.environ, {"BEER_ORDER": "listed"}):
            self.assertEqual(send_beer.permutation(2026), list(range(24)))
            self.assertEqual(send_beer.beer_for_day(BEERS, 1, 2026), BEERS[0])
            self.assertEqual(send_beer.beer_for_day(BEERS, 24, 2026), BEERS[23])

    def test_is_true_permutation(self):
        perm = send_beer.permutation(2026)
        self.assertEqual(sorted(perm), list(range(24)))

    def test_stable_for_same_seed(self):
        self.assertEqual(send_beer.permutation(2026), send_beer.permutation(2026))
        self.assertNotEqual(send_beer.permutation(2026), send_beer.permutation(2027))

    def test_editing_one_beer_text_moves_nothing_else(self):
        edited = list(BEERS)
        edited[7] = "Something Completely Different"
        changed_days = [
            d for d in range(1, 25)
            if send_beer.beer_for_day(BEERS, d, 2026) != send_beer.beer_for_day(edited, d, 2026)
        ]
        self.assertEqual(len(changed_days), 1)
        self.assertEqual(send_beer.beer_for_day(edited, changed_days[0], 2026),
                         "Something Completely Different")

    def test_numeric_seed_env_matches_default(self):
        with mock.patch.dict(os.environ, {"SEED": "2026"}):
            self.assertEqual(send_beer.resolve_seed(date(2026, 12, 1)), 2026)
        with mock.patch.dict(os.environ, {"SEED": ""}):
            self.assertEqual(send_beer.resolve_seed(date(2030, 12, 1)), 2030)


class RunTests(unittest.TestCase):
    def setUp(self):
        self.path = write_temp("\n".join(BEERS) + "\n")
        self.addCleanup(os.unlink, self.path)
        env = {"BEERS_URL": self.path, "NTFY_TOPIC": "test-topic", "NTFY_SERVER": "", "SEED": ""}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = send_beer.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    @mock.patch("send_beer.urllib.request.urlopen")
    def test_out_of_range_dates_noop(self, urlopen):
        for d in ("2026-11-29", "2026-12-24", "2026-12-25", "2026-12-31", "2027-01-01", "2026-07-04"):
            code, out, _ = self.run_main("--date", d)
            self.assertEqual(code, 0)
            self.assertIn("nothing to send", out)
        urlopen.assert_not_called()

    @mock.patch("send_beer.urllib.request.urlopen")
    def test_dry_run_prints_right_beer_no_network(self, urlopen):
        # The Dec 5 run announces the Dec 6 beer, one day ahead.
        expected = send_beer.beer_for_day(BEERS, 6, 2026)
        code, out, _ = self.run_main("--date", "2026-12-05", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn(f"Tomorrow's beer (Dec 6): {expected}", out)
        self.assertIn("Beer Advent Day 6", out)
        urlopen.assert_not_called()

    @mock.patch("send_beer.urllib.request.urlopen")
    def test_send_builds_right_request(self, urlopen):
        urlopen.return_value.__enter__.return_value.status = 200
        expected = send_beer.beer_for_day(BEERS, 1, 2026)
        code, _, _ = self.run_main("--date", "2026-11-30")
        self.assertEqual(code, 0)
        urlopen.assert_called_once()
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, "https://ntfy.sh/test-topic")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.data, f"Tomorrow's beer (Dec 1): {expected}".encode("utf-8"))
        self.assertEqual(req.get_header("Title"), "Beer Advent Day 1")
        self.assertEqual(req.get_header("Tags"), "beer")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], send_beer.TIMEOUT)

    @mock.patch("send_beer.urllib.request.urlopen")
    def test_unicode_beer_goes_in_body(self, urlopen):
        urlopen.return_value.__enter__.return_value.status = 200
        beers = list(BEERS)
        perm = send_beer.permutation(2026)
        beers[perm[0]] = "Weihenstephaner Hefeweißbier \U0001F37A"
        Path(self.path).write_text("\n".join(beers), encoding="utf-8")
        code, _, _ = self.run_main("--date", "2026-11-30")
        self.assertEqual(code, 0)
        req = urlopen.call_args.args[0]
        self.assertEqual(req.data.decode("utf-8"),
                         "Tomorrow's beer (Dec 1): Weihenstephaner Hefeweißbier \U0001F37A")
        req.get_header("Title").encode("latin-1")

    @mock.patch("send_beer.urllib.request.urlopen")
    def test_wrong_count_exits_nonzero_and_does_not_send(self, urlopen):
        Path(self.path).write_text("\n".join(BEERS[:20]), encoding="utf-8")
        code, _, err = self.run_main("--date", "2026-12-03")
        self.assertEqual(code, 1)
        self.assertIn("found 20", err)
        urlopen.assert_not_called()

    @mock.patch("send_beer.urllib.request.urlopen")
    def test_network_error_exits_nonzero(self, urlopen):
        urlopen.side_effect = send_beer.urllib.error.URLError("no route")
        code, _, err = self.run_main("--date", "2026-12-03")
        self.assertEqual(code, 1)
        self.assertIn("Could not reach ntfy", err)

    @mock.patch("send_beer.urllib.request.urlopen")
    def test_test_message_honors_dry_run(self, urlopen):
        code, out, _ = self.run_main("--test-message", "--dry-run", "--date", "2026-07-04")
        self.assertEqual(code, 0)
        self.assertIn(send_beer.TEST_BODY, out)
        urlopen.assert_not_called()

    @mock.patch("send_beer.urllib.request.urlopen")
    def test_show_schedule_lists_all_24(self, urlopen):
        code, out, _ = self.run_main("--show-schedule", "--date", "2026-12-01")
        self.assertEqual(code, 0)
        lines = [l for l in out.splitlines() if l.startswith("Dec ")]
        self.assertEqual(len(lines), 24)
        self.assertEqual(sorted(l.split(": ", 1)[1] for l in lines), sorted(BEERS))
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
