"""Unit tests for publish (revealed.json). No network calls."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import publish  # noqa: E402
import send_beer  # noqa: E402

BEERS = [f"Distinct Brew Number {i:02d}" for i in range(1, 25)]


class PublishTests(unittest.TestCase):
    def setUp(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        f.write("\n".join(BEERS) + "\n")
        f.close()
        self.list_path = f.name
        self.addCleanup(os.unlink, self.list_path)
        self.out = tempfile.mkdtemp()
        self.addCleanup(lambda: [os.unlink(os.path.join(self.out, n)) for n in os.listdir(self.out)])
        patcher = mock.patch.dict(os.environ, {"BEERS_URL": self.list_path, "SEED": ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def publish(self, d):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = publish.main(["--out", self.out, "--date", d])
        self.assertEqual(code, 0, err.getvalue())
        text = Path(self.out, "revealed.json").read_text(encoding="utf-8")
        return text, json.loads(text)

    def test_reveal_counts(self):
        cases = {
            # One day ahead: the Nov 30 run reveals Dec 1, the Dec 23 run reveals Dec 24.
            "2026-11-29": 0, "2026-11-30": 1, "2026-12-01": 2, "2026-12-10": 11,
            "2026-12-23": 24, "2026-12-24": 24, "2026-12-30": 24,
            "2026-12-31": 0, "2027-01-15": 0,
        }
        for d, n in cases.items():
            with self.subTest(date=d):
                _, data = self.publish(d)
                self.assertEqual([x["day"] for x in data["days"]], list(range(1, n + 1)))
                self.assertEqual(data["year"], (date.fromisoformat(d) + timedelta(days=1)).year)
                self.assertIn("updated", data)

    def test_revealed_beers_match_send_beer(self):
        for d in ("2026-12-01", "2026-12-10", "2026-12-24"):
            _, data = self.publish(d)
            for entry in data["days"]:
                with self.subTest(date=d, day=entry["day"]):
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out), \
                            mock.patch.dict(os.environ, {"NTFY_TOPIC": "x"}):
                        code = send_beer.main(["--date", (date(2026, 12, entry["day"]) - timedelta(days=1)).isoformat(), "--dry-run"])
                    self.assertEqual(code, 0)
                    self.assertIn(f"Tomorrow's beer (Dec {entry['day']}): {entry['beer']}", out.getvalue())

    def test_no_peek_mid_month(self):
        text, data = self.publish("2026-12-10")
        revealed = {x["beer"] for x in data["days"]}
        hidden = [b for b in BEERS if b not in revealed]
        self.assertEqual(len(hidden), 13)  # Dec 10 run reveals days 1 to 11
        for beer in hidden:
            self.assertNotIn(beer, text)
        self.assertEqual(set(data.keys()), {"year", "updated", "days"})

    def test_wrong_count_fails_even_in_november(self):
        Path(self.list_path).write_text("\n".join(BEERS[:23]), encoding="utf-8")
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = publish.main(["--out", self.out, "--date", "2026-11-30"])
        self.assertEqual(code, 1)
        self.assertIn("found 23", err.getvalue())


if __name__ == "__main__":
    unittest.main()
