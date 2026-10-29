import json
import tempfile
import unittest
from pathlib import Path

from examwatch.session_storage import delete_session
from examwatch.session_storage import save_event_review
from unittest.mock import patch


class SessionDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reports = self.root / 'outputs/session_reports'
        self.images = self.root / 'outputs/screenshots'
        self.reports.mkdir(parents=True)
        self.images.mkdir(parents=True)

    def report(self, name, image):
        path = self.reports / f'session_report_{name}.json'
        path.write_text(json.dumps({'events': [{'screenshot': str(image)}]}), encoding='utf-8')
        return path

    def test_deletes_selected_report_pair_and_image_only(self):
        image = self.images / 'one.jpg'
        image.write_bytes(b'evidence')
        other = self.images / 'other.jpg'
        other.write_bytes(b'keep')
        report = self.report('one', image)
        report.with_suffix('.txt').write_text('summary')
        delete_session(self.root, report)
        self.assertFalse(report.exists())
        self.assertFalse(report.with_suffix('.txt').exists())
        self.assertFalse(image.exists())
        self.assertTrue(other.exists())

    def test_shared_image_is_preserved(self):
        image = self.images / 'shared.jpg'
        image.write_bytes(b'evidence')
        first = self.report('one', image)
        second = self.report('two', image)
        delete_session(self.root, first)
        self.assertTrue(image.exists())
        self.assertTrue(second.exists())

    def test_deletion_removes_clip_and_default_derived_reports(self):
        clips = self.root / 'outputs/clips'
        clips.mkdir()
        clip = clips / 'event_test.avi'
        clip.write_bytes(b'clip')
        report = self.report('one', None)
        report.write_text(json.dumps({'events': [{'clip': str(clip)}]}), encoding='utf-8')
        pdf = self.root / 'outputs/pdf/session_report_one.pdf'
        pdf.parent.mkdir()
        pdf.write_bytes(b'pdf')
        result = self.root / 'outputs/evaluations/session_report_one_evaluation.json'
        result.parent.mkdir()
        result.write_text('{}')
        delete_session(self.root, report)
        self.assertFalse(clip.exists())
        self.assertFalse(pdf.exists())
        self.assertFalse(result.exists())

    def test_outside_reference_is_rejected_before_deletion(self):
        outside = self.root / 'important.jpg'
        outside.write_bytes(b'keep')
        report = self.report('one', outside)
        with self.assertRaises(ValueError):
            delete_session(self.root, report)
        self.assertTrue(outside.exists())
        self.assertTrue(report.exists())

    def test_outside_report_is_rejected(self):
        with self.assertRaises(ValueError):
            delete_session(self.root, self.root / 'session_report_other.json')

    def test_review_persists_arabic_notes_and_preserves_detection_data(self):
        report = self.report('one', None)
        review = save_event_review(self.root, report, 0, 'False alarm', '  حركة طبيعية  ')
        saved = json.loads(report.read_text(encoding='utf-8'))
        self.assertEqual(saved['events'][0]['review']['notes'], 'حركة طبيعية')
        self.assertEqual(saved['events'][0]['review']['status'], 'False alarm')
        self.assertIn('updated_at', review)
        self.assertEqual(saved['events'][0]['screenshot'], 'None')

    def test_failed_atomic_write_preserves_original_report(self):
        report = self.report('one', None)
        original = report.read_bytes()
        with patch('examwatch.session_storage.os.replace', side_effect=OSError('locked')):
            with self.assertRaises(OSError):
                save_event_review(self.root, report, 0, 'Reviewed', 'test')
        self.assertEqual(report.read_bytes(), original)
        self.assertEqual(list(self.reports.glob('.review-*.tmp')), [])

    def test_invalid_review_or_event_does_not_change_report(self):
        report = self.report('one', None)
        original = report.read_bytes()
        for index, status in ((0, 'bad status'), (4, 'Reviewed'), (-1, 'Reviewed')):
            with self.assertRaises(ValueError):
                save_event_review(self.root, report, index, status, '')
        self.assertEqual(report.read_bytes(), original)
