import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from examwatch.camera_preparation import prepare_camera
from examwatch.screen_calibration import CameraControls, fit_screen_envelope, outside_screen


CENTERS = ((0, .2, .5, 0), (-.12, .2, .32, 0), (.12, .2, .68, 0),
           (0, .06, .5, -.14), (0, .34, .5, .14))


class ScreenEnvelopeTests(unittest.TestCase):
    def test_reading_across_calibrated_screen_is_normal(self):
        envelope = fit_screen_envelope([[center] * 20 for center in CENTERS])
        for point in CENTERS + ((.08, .25, .59, .03), (.18, .2, .5, 0)):
            self.assertFalse(outside_screen(point, envelope))
        self.assertTrue(outside_screen((0, .2, 1.0, 0), envelope))
        self.assertTrue(outside_screen((0, .7, .5, .4), envelope))

    def test_identical_targets_cannot_establish_screen_range(self):
        with self.assertRaises(ValueError):
            fit_screen_envelope([[CENTERS[0]] * 20 for _ in range(5)])
        with self.assertRaises(ValueError):
            fit_screen_envelope([[point] for point in CENTERS])


class CameraPhaseTests(unittest.TestCase):
    def fake_cv(self):
        cv = types.ModuleType('cv2')
        cap = Mock()
        cap.isOpened.return_value = True
        frame = Mock()
        cap.read.return_value = True, frame
        cv.VideoCapture = Mock(return_value=cap)
        cv.flip = Mock(return_value=frame)
        cv.cvtColor = Mock(return_value=frame)
        cv.COLOR_BGR2RGB = 1
        return cv, cap

    def test_preview_never_loads_models_or_records_reports(self):
        cv, cap = self.fake_cv()
        stop, controls = threading.Event(), CameraControls()
        controls.begin_exam.set()  # A premature start request must be ignored.
        messages = []

        def emit(message):
            messages.append(message)
            stop.set()

        with tempfile.TemporaryDirectory() as directory, patch.dict('sys.modules', {
                'cv2': cv, 'mediapipe': None, 'ultralytics': None}):
            result = prepare_camera(Path(directory), {'camera': 0}, emit, stop, controls)
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertIsNone(result)
        self.assertEqual(messages[0]['phase'], 'preview')
        self.assertEqual(messages[0]['events'], 0)
        self.assertEqual(messages[0]['elapsed'], 0)
        self.assertFalse(controls.begin_exam.is_set())
        cap.release.assert_called_once()

    def test_five_targets_then_ready_waits_for_explicit_exam_start(self):
        cv, cap = self.fake_cv()
        controls = CameraControls()
        controls.calibrate.set()
        stop = Mock()
        stop.is_set.return_value = False
        stop.wait.return_value = False
        mp = types.ModuleType('mediapipe')
        tasks = types.ModuleType('mediapipe.tasks')
        python = types.ModuleType('mediapipe.tasks.python')
        vision = types.ModuleType('mediapipe.tasks.python.vision')
        mp.Image = Mock()
        mp.ImageFormat = types.SimpleNamespace(SRGB=1)
        python.BaseOptions = Mock()
        python.vision = vision
        tasks.python = python
        vision.FaceLandmarkerOptions = Mock()
        vision.RunningMode = types.SimpleNamespace(VIDEO=1)
        detector = Mock()
        detector.detect_for_video.return_value = types.SimpleNamespace(face_landmarks=[[Mock()]])
        vision.FaceLandmarker = types.SimpleNamespace(create_from_options=Mock(return_value=detector))
        modules = {'cv2': cv, 'mediapipe': mp, 'mediapipe.tasks': tasks,
                   'mediapipe.tasks.python': python, 'mediapipe.tasks.python.vision': vision,
                   'ultralytics': None}
        clock = [0]
        seen = set()
        ready = []

        def now():
            clock[0] += .1
            if clock[0] > 200:
                raise AssertionError('Calibration did not finish')
            return clock[0]

        def emit(message):
            if message.get('phase') == 'calibrating':
                controls.shown_target = message['target_index']
                seen.add(message['target_index'])
            if message.get('phase') == 'ready':
                ready.append(message)
                if len(ready) >= 3:
                    controls.begin_exam.set()

        def measure(_face):
            return CENTERS[max(0, controls.shown_target)]

        with tempfile.TemporaryDirectory() as directory, patch.dict('sys.modules', modules), patch(
                'examwatch.camera_preparation.time.monotonic', side_effect=now), patch(
                'examwatch.camera_preparation.assess_quality', return_value={'warnings': [], 'calibration_ready': True}), patch(
                'examwatch.camera_preparation.screen_measurements', side_effect=measure):
            root = Path(directory)
            (root / 'models').mkdir()
            (root / 'models/face_landmarker.task').touch()
            prepared = prepare_camera(root, {'camera': 0}, emit, stop, controls)
            self.assertFalse((root / 'outputs').exists())
        self.assertEqual(seen, set(range(5)))
        self.assertEqual(len(ready), 3)
        self.assertTrue(all(message['events'] == 0 for message in ready))
        self.assertIsNotNone(prepared['screen_envelope'])
        cap.release.assert_not_called()  # Ownership transfers to the exam worker.
        detector.close.assert_not_called()

    def test_exam_pipeline_suppresses_on_screen_head_turn_and_flags_far_gaze(self):
        import json
        from examwatch import monitoring_runner
        envelope = fit_screen_envelope([[point] * 20 for point in CENTERS])
        for point, expected in (((.18, .2, .5, 0), 0), ((0, .2, 1.0, 0), 1)):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'models').mkdir()
                (root / 'models/face_landmarker.task').touch()
                cv, cap = self.fake_cv()
                cv.imwrite = Mock(return_value=True)
                mp = types.ModuleType('mediapipe')
                tasks = types.ModuleType('mediapipe.tasks')
                python = types.ModuleType('mediapipe.tasks.python')
                vision = types.ModuleType('mediapipe.tasks.python.vision')
                mp.Image, python.BaseOptions, vision.FaceLandmarkerOptions = Mock(), Mock(), Mock()
                mp.ImageFormat = types.SimpleNamespace(SRGB=1)
                vision.RunningMode = types.SimpleNamespace(VIDEO=1)
                tasks.python, python.vision = python, vision
                yolo = types.ModuleType('ultralytics')
                model = Mock()
                model.names = {}
                yolo.YOLO = Mock(return_value=model)
                detector = Mock()
                detector.detect_for_video.return_value = types.SimpleNamespace(face_landmarks=[[Mock()]])
                stop = threading.Event()
                frames = []

                def emit(message):
                    if 'frame' in message:
                        frames.append(message)
                        if len(frames) == 8:
                            stop.set()

                clock = [0]

                def now():
                    clock[0] += .2
                    return clock[0]

                modules = {'cv2': cv, 'mediapipe': mp, 'mediapipe.tasks': tasks,
                           'mediapipe.tasks.python': python, 'mediapipe.tasks.python.vision': vision,
                           'ultralytics': yolo}
                prepared = dict(cap=cap, landmarker=detector, screen_envelope=envelope,
                                timestamp_origin=0, last_timestamp_ms=0)
                settings = dict(camera=0, source_type='Camera', minimum_duration=1,
                                absence_duration=3, confidence=.4, forbidden_objects=[], save_clips=False)
                with patch.dict('sys.modules', modules), patch.object(monitoring_runner, 'ROOT', root), patch(
                        'examwatch.monitoring_runner.time.monotonic', side_effect=now), patch(
                        'examwatch.monitoring_runner.face_measurements', return_value=point[:3]), patch(
                        'examwatch.monitoring_runner.screen_measurements', return_value=point), patch(
                        'examwatch.monitoring_runner.assess_quality', return_value={'warnings': [], 'calibration_ready': True}):
                    monitoring_runner._run_analysis(settings, emit, stop, threading.Event(), prepared)
                report = json.loads(next((root / 'outputs/session_reports').glob('*.json')).read_text())
                self.assertEqual(report['confirmed_reason_counts']['EYE GAZE'], expected)
                self.assertEqual(report['confirmed_reason_counts']['HEAD TURN'], 0)
                self.assertEqual(frames[-1]['gaze'], 'ON SCREEN' if expected == 0 else 'OUTSIDE SCREEN')
