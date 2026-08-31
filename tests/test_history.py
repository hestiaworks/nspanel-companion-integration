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

    def test_every_span_lands_in_the_range_the_spec_draws(self):
        # 24 to 48 flat rectangles, whatever the span.
        for span, count in history.RANGE_BUCKETS.items():
            self.assertTrue(24 <= count <= 48, f"{span} asks for {count}")
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


if __name__ == "__main__":
    unittest.main()
