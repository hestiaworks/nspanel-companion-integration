"""Tests for reducing a span of history to a row of bars."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest

PATH = Path(__file__).parents[1] / "custom_components/nspanel_companion/history.py"
SPEC = spec_from_file_location("nspanel_history", PATH)
history = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(history)


class BucketTest(unittest.TestCase):
    now = 1_000_000.0

    def test_each_span_is_reduced_to_the_bars_its_page_draws(self):
        # The prose says 24 to 48 rectangles, and the short spans keep that
        # dense row. A week is drawn as seven wide bars labelled by weekday
        # instead — you can point at a day, which is the whole use of it.
        self.assertEqual(7, history.RANGE_BUCKETS["7d"])
        for span in ("6h", "24h", "30d"):
            self.assertTrue(24 <= history.RANGE_BUCKETS[span] <= 48)
        for span, count in history.RANGE_BUCKETS.items():
            self.assertEqual(count, len(history.bucket([], span, self.now)))

    def test_samples_land_in_the_bucket_their_time_falls_in(self):
        start, _, width = history.bucket_bounds("6h", self.now)
        samples = [(start + width * 0.5, 10.0), (start + width * 1.5, 20.0)]
        buckets = history.bucket(samples, "6h", self.now)
        self.assertEqual(10.0, buckets[0]["mean"])
        self.assertEqual(20.0, buckets[1]["mean"])
        self.assertIsNone(buckets[2])

    def test_a_bucket_keeps_the_extremes_it_covers(self):
        start, _, width = history.bucket_bounds("24h", self.now)
        inside = [(start + width * 0.1, 5.0), (start + width * 0.2, 9.0), (start + width * 0.3, 7.0)]
        first = history.bucket(inside, "24h", self.now)[0]
        self.assertEqual(5.0, first["min"])
        self.assertEqual(9.0, first["max"])
        self.assertEqual(7.0, first["mean"])

    def test_an_empty_bucket_is_absent_rather_than_zero(self):
        # A gap in the recording is not a reading of nought, and a bar drawn
        # at the floor claims one.
        self.assertTrue(all(b is None for b in history.bucket([], "7d", self.now)))

    def test_samples_outside_the_window_are_ignored(self):
        start, end, _ = history.bucket_bounds("6h", self.now)
        buckets = history.bucket([(start - 60, 1.0), (end + 60, 2.0)], "6h", self.now)
        self.assertTrue(all(b is None for b in buckets))

    def test_the_last_sample_is_not_pushed_past_the_end(self):
        # An exact hit on the upper bound would index one past the array.
        _, end, _ = history.bucket_bounds("6h", self.now)
        buckets = history.bucket([(end, 3.0)], "6h", self.now)
        self.assertEqual(3.0, buckets[-1]["mean"])

    def test_the_summary_spans_every_bucket_drawn(self):
        start, _, width = history.bucket_bounds("24h", self.now)
        samples = [(start + width * 0.5, 18.6), (start + width * 5.5, 23.1)]
        summary = history.summarise(history.bucket(samples, "24h", self.now))
        self.assertEqual(18.6, summary["min"])
        self.assertEqual(23.1, summary["max"])

    def test_nothing_recorded_has_no_summary(self):
        self.assertIsNone(history.summarise(history.bucket([], "30d", self.now)))



class BucketBoundsTest(unittest.TestCase):
    """The window a series covers, which only the server knows.

    The panel used to label its axis "-6h, -4h, -2h, now" because the series
    it was sent carried no times at all. It cannot infer them either: the
    server decides what "now" was when it bucketed, and by the time a panel
    draws the row that moment has passed.
    """

    def test_the_window_is_stated_in_milliseconds(self):
        start, end, width = history.bucket_bounds("24h", 1_000_000.0)
        self.assertEqual(1_000_000.0 - 24 * 3600, start)
        self.assertEqual(1_000_000.0, end)
        # 48 buckets across a day is half an hour each.
        self.assertEqual(1800.0, width)

    def test_every_span_divides_evenly_into_its_buckets(self):
        # A width that did not divide evenly would put the last bucket's end
        # somewhere other than now, and the axis would say so.
        for span in history.RANGE_SECONDS:
            with self.subTest(span=span):
                start, end, width = history.bucket_bounds(span, 0.0)
                self.assertAlmostEqual(end - start, width * history.RANGE_BUCKETS[span])

if __name__ == "__main__":
    unittest.main()
