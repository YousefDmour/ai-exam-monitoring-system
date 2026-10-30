"""Preview -> guided calibration -> ready. No alerts or evidence before exam."""
import time
from pathlib import Path

from examwatch.camera_quality import assess_quality
from examwatch.screen_calibration import TARGETS, fit_screen_envelope, screen_measurements


def prepare_camera(root, settings, emit, stop, controls):
    import cv2
    cap = cv2.VideoCapture(settings['camera'])
    landmarker = None
    handed_off = False
    phase = 'preview'
    groups = [[] for _ in TARGETS]
    target = 0
    target_started = None
    good_since = None
    calibrated = None
    notice = ''
    origin = time.monotonic()
    last_timestamp = -1
    try:
        if not cap.isOpened():
            raise RuntimeError('Unable to open the camera. Check camera access and camera index.')
        while not stop.is_set():
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError('Unable to read the camera.')
            frame = cv2.flip(frame, 1)
            quality = {'warnings': []}
            instruction = notice or 'Preview only. Position yourself, then choose Calibrate gaze. No monitoring or recording is active.'
            if controls.calibrate.is_set():
                controls.calibrate.clear()
                controls.begin_exam.clear()
                controls.shown_target = -1
                calibrated = None
                notice = ''
                groups, target, target_started, good_since = [[] for _ in TARGETS], 0, None, None
                if landmarker is None:
                    emit({'message': 'Loading face calibration model...', 'phase': 'loading_calibration'})
                    import mediapipe as mp
                    from mediapipe.tasks import python as mp_python
                    from mediapipe.tasks.python import vision
                    model_path = Path(root) / 'models/face_landmarker.task'
                    if not model_path.is_file():
                        raise FileNotFoundError('Missing models/face_landmarker.task.')
                    landmarker = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
                        base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
                        running_mode=vision.RunningMode.VIDEO, num_faces=5,
                        min_face_detection_confidence=.5, min_tracking_confidence=.5))
                phase = 'calibrating'
            if phase == 'calibrating':
                now = time.monotonic()
                timestamp = max(last_timestamp + 1, int((now - origin) * 1000))
                last_timestamp = timestamp
                image = mp.Image(image_format=mp.ImageFormat.SRGB,
                                 data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                faces = landmarker.detect_for_video(image, timestamp).face_landmarks
                quality = assess_quality(frame, faces, cv2)
                values = screen_measurements(faces[0]) if len(faces) == 1 else None
                instruction = f'Look at the {TARGETS[target][0].lower()} target. Keep your head comfortable and follow the dot with your eyes.'
                if controls.shown_target != target:
                    target_started, good_since = None, None
                    groups[target].clear()
                if controls.shown_target == target and target_started is None:
                    target_started = now
                if target_started is not None and now - target_started >= 1 and values is not None and quality['calibration_ready']:
                    if good_since is None:
                        good_since = now
                    groups[target].append(values)
                    if now - good_since >= 2 and len(groups[target]) >= 15:
                        if target == len(TARGETS) - 1:
                            try:
                                calibrated = fit_screen_envelope(groups)
                                phase = 'ready'
                            except ValueError as error:
                                phase = 'preview'
                                notice = str(error) + ' Choose Calibrate gaze to retry.'
                                instruction = notice
                        else:
                            target += 1
                            target_started, good_since = None, None
                elif good_since is not None:
                    # Do not join disjoint looks into one stable calibration sample.
                    groups[target].clear()
                    good_since = None
            if phase == 'ready':
                instruction = 'Calibration complete. Keep the camera and window in place. Choose Start exam when ready. No monitoring is active yet.'
                if controls.begin_exam.is_set():
                    controls.begin_exam.clear()
                    handed_off = True
                    return {'cap': cap, 'landmarker': landmarker, 'screen_envelope': calibrated,
                            'last_timestamp_ms': last_timestamp, 'timestamp_origin': origin}
            else:
                controls.begin_exam.clear()
            progress = 1.0 if phase == 'ready' else (target + min(
                1, (time.monotonic() - good_since) / 2 if good_since is not None else 0,
                len(groups[target]) / 15)) / len(TARGETS) if phase == 'calibrating' else 0
            emit({'frame': frame, 'phase': phase, 'status': phase.upper().replace('_', ' '),
                  'faces': '—', 'head': '—', 'pitch': '—', 'gaze': '—', 'elapsed': 0,
                  'events': 0, 'calibration': progress, 'reasons': [], 'quality': quality,
                  'instruction': instruction, 'target_index': target if phase == 'calibrating' else -1,
                  'target': TARGETS[target][1:] if phase == 'calibrating' else (.5, .5) if phase == 'preview' else None})
            stop.wait(.025)
    finally:
        if not handed_off:
            cap.release()
            if landmarker is not None:
                landmarker.close()
    return None
