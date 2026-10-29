import unittest
from types import SimpleNamespace

from examwatch.monitoring_logic import (
    EventTracker, calibration_baseline, classify_measurements, face_measurements,
)


class EventTrackerTests(unittest.TestCase):
    def test_sustained_signal_counts_once_even_with_slow_frames(self):
        tracker = EventTracker()
        self.assertFalse(tracker.update(True, 0.0))
        self.assertTrue(tracker.update(True, 1.0))
        self.assertFalse(tracker.update(True, 3.0))
        self.assertTrue(tracker.confirmed)
        self.assertEqual(tracker.duration(3.0), 3.0)

    def test_brief_signal_is_not_confirmed(self):
        tracker = EventTracker()
        tracker.update(True, 0.0)
        tracker.update(False, 0.8)
        self.assertFalse(tracker.update(True, 1.1))
        self.assertFalse(tracker.confirmed)
        self.assertEqual(tracker.started_at, 1.1)

    def test_short_dropout_preserves_confirmed_episode(self):
        tracker = EventTracker()
        tracker.update(True, 0.0)
        tracker.update(True, 1.0)
        tracker.update(False, 1.2)
        self.assertTrue(tracker.confirmed)
        self.assertFalse(tracker.update(True, 1.4))
        self.assertEqual(tracker.started_at, 0.0)

    def test_recovery_closes_episode_and_next_signal_must_qualify(self):
        tracker = EventTracker()
        tracker.update(True, 0.0)
        tracker.update(True, 1.0)
        tracker.update(False, 1.2)
        tracker.update(False, 1.6)
        self.assertFalse(tracker.confirmed)
        self.assertFalse(tracker.update(True, 2.0))
        self.assertTrue(tracker.update(True, 3.0))

    def test_reappearance_after_recovery_starts_new_candidate(self):
        tracker = EventTracker()
        tracker.update(True, 0.0)
        tracker.update(True, 1.0)
        tracker.update(False, 1.2)
        self.assertFalse(tracker.update(True, 1.7))
        self.assertFalse(tracker.confirmed)
        self.assertEqual(tracker.started_at, 1.7)

    def test_face_absence_uses_three_seconds(self):
        tracker = EventTracker(3.0, 0.5)
        tracker.update(True, 0.0)
        self.assertFalse(tracker.update(True, 2.9))
        self.assertTrue(tracker.update(True, 3.0))


class CalibrationTests(unittest.TestCase):
    def test_neutral_pose_uses_personal_baseline(self):
        baseline = calibration_baseline([(0.2, 0.6, 0.7)] * 3)
        self.assertEqual(classify_measurements((0.2, 0.6, 0.7), baseline),
                         ("FORWARD", "LEVEL", "CENTER"))
        self.assertEqual(classify_measurements((0.4, 0.8, 0.9), baseline),
                         ("RIGHT", "DOWN", "RIGHT"))

    def test_empty_calibration_is_explicitly_rejected(self):
        with self.assertRaises(ValueError):
            calibration_baseline([])

    def test_measurements_are_translation_and_scale_independent(self):
        def face(scale, offset):
            points = [SimpleNamespace(x=0.0, y=0.0) for _ in range(478)]
            for index, x, y in ((33, .2, .3), (133, .3, .3),
                                (362, .6, .3), (263, .7, .3),
                                (468, .25, .3), (473, .65, .3),
                                (1, .45, .5)):
                points[index] = SimpleNamespace(x=x * scale + offset,
                                                y=y * scale + offset)
            return points
        for actual, expected in zip(face_measurements(face(.5, .1)),
                                    face_measurements(face(1, 0))):
            self.assertAlmostEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
