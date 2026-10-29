import json
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from examwatch import monitoring_runner
from examwatch.video_timing import VideoTimeline


class VideoTimingTests(unittest.TestCase):
    def test_timestamps_and_fps_fallback(self):
        clock = VideoTimeline(25)
        self.assertEqual(clock.advance(0), 0)
        self.assertAlmostEqual(clock.advance(0), .04)
        self.assertAlmostEqual(clock.advance(float('nan')), .08)
        self.assertAlmostEqual(clock.advance(120), .12)
        self.assertAlmostEqual(clock.duration, .16)

    def test_invalid_frame_rates_are_rejected(self):
        for fps in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                VideoTimeline(fps)

    def test_video_worker_uses_media_time_and_saves_at_read_end(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'models').mkdir()
            (root / 'models/face_landmarker.task').touch()
            video = root / 'exam.mp4'
            video.touch()
            frame = Mock()
            cap = Mock()
            cap.isOpened.return_value = True
            cap.read.side_effect = [(True, frame)] * 3 + [(False, None)]
            positions = iter((0, 1000, 2000))
            cap.get.side_effect = lambda key: 1 if key == 1 else next(positions)
            cv = types.ModuleType('cv2')
            cv.VideoCapture = Mock(return_value=cap)
            cv.CAP_PROP_FPS, cv.CAP_PROP_POS_MSEC = 1, 2
            cv.COLOR_BGR2RGB = 3
            cv.cvtColor = Mock(return_value=frame)
            cv.flip = Mock()
            cv.imwrite = Mock(return_value=True)
            mp = types.ModuleType('mediapipe')
            tasks = types.ModuleType('mediapipe.tasks')
            python = types.ModuleType('mediapipe.tasks.python')
            vision = types.ModuleType('mediapipe.tasks.python.vision')
            mp.Image = Mock()
            mp.ImageFormat = types.SimpleNamespace(SRGB=1)
            python.BaseOptions = Mock()
            vision.FaceLandmarkerOptions = Mock()
            vision.RunningMode = types.SimpleNamespace(VIDEO=1)
            detector = Mock()
            detector.detect_for_video.return_value = types.SimpleNamespace(face_landmarks=[])
            vision.FaceLandmarker = types.SimpleNamespace(create_from_options=Mock(return_value=detector))
            tasks.python = python
            python.vision = vision
            yolo = types.ModuleType('ultralytics')
            yolo.YOLO = Mock(return_value=Mock(return_value=[]))
            modules = {'cv2': cv, 'mediapipe': mp, 'mediapipe.tasks': tasks,
                       'mediapipe.tasks.python': python, 'mediapipe.tasks.python.vision': vision,
                       'ultralytics': yolo}
            settings = dict(camera=0, source_type='Video file', video_path=str(video),
                            minimum_duration=1, absence_duration=1, confidence=.4,
                            save_clips=False,
                            allowed_objects=['CLOCK'], session_name='Recorded exam')
            with patch.dict('sys.modules', modules), patch.object(monitoring_runner, 'ROOT', root), patch.object(
                    monitoring_runner, 'assess_quality', return_value={'warnings': [], 'calibration_ready': False}):
                monitoring_runner.run_monitoring(settings, Mock(), threading.Event(), threading.Event())
            reports = list((root / 'outputs/session_reports').glob('*.json'))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text())
            self.assertEqual(report['duration_seconds'], 3)
            self.assertEqual(report['source_name'], 'exam.mp4')
            self.assertEqual(report['end_reason'], 'video_read_end')
            self.assertEqual(report['confirmed_reason_counts']['FACE ABSENT'], 1)
            self.assertEqual(report['events'][0]['start_seconds'], 0)
            self.assertEqual(report['events'][0]['confirmed_seconds'], 1)
            cv.flip.assert_not_called()
            cap.release.assert_called_once()
            detector.close.assert_called_once()
