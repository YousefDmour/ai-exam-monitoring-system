import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from examwatch.evaluation import annotation_template, evaluate_report


class EvaluationTests(unittest.TestCase):
    def report(self, events):
        return {'session_id': 'test', 'duration_seconds': 20, 'events': events}

    def event(self, start, end, reason='CELL PHONE'):
        return {'start_seconds': start, 'end_seconds': end, 'reasons': [reason]}

    def test_duplicate_predictions_are_false_alerts_and_misses_are_counted(self):
        report = self.report([self.event(2, 5), self.event(2, 5)])
        truth = dict(annotation_template(report), complete=True,
                     events=[self.event(2, 5), self.event(10, 12, 'BOOK')])
        result = evaluate_report(report, truth)
        self.assertEqual((result['tp'], result['fp'], result['fn']), (1, 1, 1))
        self.assertEqual(result['precision'], .5)
        self.assertEqual(result['recall'], .5)
        self.assertEqual(result['f1'], .5)

    def test_verified_negative_has_no_invented_accuracy(self):
        report = self.report([])
        truth = dict(annotation_template(report), complete=True)
        result = evaluate_report(report, truth)
        self.assertIsNone(result['precision'])
        self.assertIsNone(result['recall'])
        self.assertEqual(result['false_alerts_per_minute'], 0)

    def test_requires_matching_complete_ground_truth(self):
        report = self.report([])
        truth = annotation_template(report)
        with self.assertRaises(ValueError):
            evaluate_report(report, truth)
        truth.update(complete=True, session_id='wrong')
        with self.assertRaises(ValueError):
            evaluate_report(report, truth)

    def test_invalid_intervals_and_reasons_are_rejected(self):
        report = self.report([])
        for event in (self.event(-1, 3), self.event(4, 3), self.event(1, 22),
                      self.event(1, 3, 'UNKNOWN'), self.event(float('nan'), 3)):
            truth = dict(annotation_template(report), complete=True, events=[event])
            with self.assertRaises(ValueError):
                evaluate_report(report, truth)


@unittest.skipUnless(importlib.util.find_spec('cv2') and importlib.util.find_spec('numpy'),
                     'OpenCV and NumPy are needed for real frame tests')
class EvidenceAndQualityTests(unittest.TestCase):
    def setUp(self):
        import cv2
        import numpy as np
        self.cv, self.np = cv2, np
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_real_clip_contains_pre_and_post_event_frames(self):
        from examwatch.evidence_clips import ClipRecorder
        recorder = ClipRecorder(Path(self.temp.name), 'test', self.cv)
        event = {}
        for index in range(121):
            frame = self.np.full((90, 160, 3), index, dtype=self.np.uint8)
            recorder.add_frame(frame, index / 10)
            if index == 60:
                recorder.trigger(event, 6, 1)
        recorder.close()
        self.assertEqual(event['clip_status'], 'saved')
        self.assertFalse(event['clip_truncated'])
        self.assertAlmostEqual(event['clip_start_seconds'], 1)
        self.assertAlmostEqual(event['clip_end_seconds'], 11)
        cap = self.cv.VideoCapture(event['clip'])
        try:
            self.assertTrue(cap.isOpened())
            self.assertEqual(int(cap.get(self.cv.CAP_PROP_FRAME_COUNT)), 100)
            self.assertEqual(cap.get(self.cv.CAP_PROP_FPS), 10)
            ok, first = cap.read()
            self.assertTrue(ok)
            self.assertAlmostEqual(float(first.mean()), 10, delta=3)
        finally:
            cap.release()

    def test_shutdown_finalizes_partial_clip(self):
        from examwatch.evidence_clips import ClipRecorder
        recorder = ClipRecorder(Path(self.temp.name), 'partial', self.cv)
        event = {}
        frame = self.np.zeros((90, 160, 3), dtype=self.np.uint8)
        recorder.add_frame(frame, 0)
        recorder.trigger(event, 0, 1)
        recorder.add_frame(frame, 1)
        recorder.close()
        self.assertEqual(event['clip_status'], 'saved')
        self.assertTrue(event['clip_truncated'])
        self.assertLessEqual(len(recorder.buffer), 52)

    def test_configured_clip_durations_are_encoded_as_total_seconds(self):
        from examwatch.evidence_clips import ClipRecorder
        from examwatch.exam_rules import clip_window
        for duration in (5, 15):
            pre, post = clip_window(duration)
            recorder = ClipRecorder(Path(self.temp.name), str(duration), self.cv, pre=pre, post=post)
            event = {}
            frame = self.np.zeros((90, 160, 3), dtype=self.np.uint8)
            trigger = int(pre * 10)
            for index in range(duration * 10 + 1):
                recorder.add_frame(frame, index / 10)
                if index == trigger:
                    recorder.trigger(event, pre, 1)
            recorder.close()
            cap = self.cv.VideoCapture(event['clip'])
            try:
                self.assertEqual(cap.get(self.cv.CAP_PROP_FRAME_COUNT) / cap.get(self.cv.CAP_PROP_FPS), duration)
            finally:
                cap.release()

    def test_dark_and_blurry_frames_block_calibration(self):
        from examwatch.camera_quality import assess_quality
        frame = self.np.zeros((90, 160, 3), dtype=self.np.uint8)
        quality = assess_quality(frame, [], self.cv)
        self.assertIn('Increase lighting', quality['warnings'])
        self.assertFalse(quality['calibration_ready'])


@unittest.skipUnless(importlib.util.find_spec('reportlab') and importlib.util.find_spec('arabic_reshaper'),
                     'PDF dependencies required')
class PDFTests(unittest.TestCase):
    def test_pdf_handles_arabic_long_notes_and_missing_evidence(self):
        from examwatch.pdf_report import export_pdf
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'session.json'
            report.write_text(json.dumps({
                'session_id': 'test', 'session_name': 'امتحان الذكاء الاصطناعي',
                'duration_seconds': 25, 'events': [{'start_seconds': 1, 'end_seconds': 4,
                    'reasons': ['CELL PHONE'], 'screenshot': 'outputs/screenshots/missing.jpg',
                    'review': {'status': 'False alarm', 'notes': 'ملاحظة للمراجعة <test> & ' * 100}}],
            }), encoding='utf-8')
            target = export_pdf(root, report, root / 'report.pdf')
            self.assertTrue(target.read_bytes().startswith(b'%PDF'))
            self.assertGreater(target.stat().st_size, 10000)
