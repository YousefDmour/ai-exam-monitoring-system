import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from examwatch.preferences import DEFAULT_PREFERENCES, load_preferences, save_preferences, validate_preferences


class PreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_defaults_are_independent_and_missing_file_is_not_created(self):
        first, warning = load_preferences(self.root)
        first['forbidden_objects'].clear()
        second, _ = load_preferences(self.root)
        self.assertEqual(second, DEFAULT_PREFERENCES)
        self.assertEqual(warning, '')
        self.assertFalse((self.root / 'outputs').exists())

    def test_round_trip_preserves_typed_valid_settings(self):
        values = dict(deepcopy(DEFAULT_PREFERENCES), fullscreen=False, camera='2',
                      confidence='0.6', clip_duration_seconds='15', forbidden_objects=['LAPTOP'])
        saved = save_preferences(self.root, values)
        loaded, warning = load_preferences(self.root)
        self.assertEqual(loaded, saved)
        self.assertEqual(loaded['camera'], 2)
        self.assertEqual(loaded['clip_duration_seconds'], 15)
        self.assertFalse(loaded['fullscreen'])
        self.assertEqual(warning, '')

    def test_invalid_settings_do_not_overwrite_saved_values(self):
        original = save_preferences(self.root, DEFAULT_PREFERENCES)
        for changes in ({'camera': '1.5'}, {'confidence': 'nan'}, {'minimum_duration': -1},
                        {'clip_duration_seconds': 16}, {'fullscreen': 'false'},
                        {'forbidden_objects': ['CUSTOM UNKNOWN OBJECT']}):
            with self.assertRaises((ValueError, TypeError)):
                save_preferences(self.root, dict(original, **changes))
        self.assertEqual(load_preferences(self.root)[0], original)

    def test_corrupt_file_falls_back_without_rewriting(self):
        directory = self.root / 'outputs'
        directory.mkdir()
        path = directory / 'preferences.json'
        path.write_text('invalid settings')
        values, warning = load_preferences(self.root)
        self.assertEqual(values, DEFAULT_PREFERENCES)
        self.assertTrue(warning)
        self.assertEqual(path.read_text(), 'invalid settings')

    def test_failed_replace_preserves_existing_file(self):
        save_preferences(self.root, DEFAULT_PREFERENCES)
        path = self.root / 'outputs/preferences.json'
        original = path.read_bytes()
        with patch('examwatch.preferences.os.replace', side_effect=OSError('locked')):
            with self.assertRaises(OSError):
                save_preferences(self.root, dict(DEFAULT_PREFERENCES, camera=1))
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(path.parent.glob('.preferences-*.tmp')), [])
