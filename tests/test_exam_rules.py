import unittest

from examwatch.exam_rules import clip_window, model_object_classes, validate_forbidden


class ExamRuleTests(unittest.TestCase):
    def test_added_objects_resolve_from_actual_model_names(self):
        names = {63: 'laptop', 67: 'cell phone', 73: 'book'}
        self.assertEqual(model_object_classes(names, ['LAPTOP', 'BOOK']), {63: 'LAPTOP', 73: 'BOOK'})
        self.assertEqual(model_object_classes(names, []), {})

    def test_unavailable_or_custom_objects_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_forbidden(['SMARTWATCH'])
        with self.assertRaises(ValueError):
            model_object_classes({73: 'book'}, ['LAPTOP'])

    def test_clip_duration_means_total_length(self):
        for duration in (5, 10, 15):
            pre, post = clip_window(duration)
            self.assertEqual(pre + post, duration)
            self.assertEqual(pre, post)
        for invalid in (4, 16, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                clip_window(invalid)
