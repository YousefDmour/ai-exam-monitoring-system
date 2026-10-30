import json
import tempfile
import unittest
from pathlib import Path

from examwatch.home_page import session_overview
from examwatch.session_library import filter_sessions, duration_label


class LibraryDataTests(unittest.TestCase):
    def test_duration_and_unicode_name_filter(self):
        rows = [{'name': 'امتحان البرمجة', 'status': 'Needs review'},
                {'name': 'AI Exam', 'status': 'Reviewed'}, {'name': 'Empty', 'status': 'No events'}]
        self.assertEqual(len(filter_sessions(rows, 'البرمجة')), 1)
        self.assertEqual(filter_sessions(rows, '  ai EXAM  ')[0]['status'], 'Reviewed')
        self.assertEqual(filter_sessions(rows, 'AI', 'Needs review'), [])
        self.assertEqual(len(filter_sessions(rows, '', 'No events')), 1)
        self.assertEqual(duration_label(65), '01:05')
        self.assertEqual(duration_label(3661), '1:01:01')

    def test_old_reports_and_unreadable_files_are_handled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'session_report_1.json').write_text(json.dumps({'events': []}))
            (root / 'bad.json').write_text('{')
            (root / 'invalid-duration.json').write_text(json.dumps({'duration_seconds': -1, 'events': []}))
            rows, unreadable = session_overview(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['status'], 'No events')
            self.assertEqual(rows[0]['duration_seconds'], 0)
            self.assertEqual(unreadable, 2)
