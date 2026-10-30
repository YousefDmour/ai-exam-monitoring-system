"""Desktop monitoring worker using the notebook detection pipeline."""
from datetime import datetime
from pathlib import Path
import json
import time
from examwatch.video_timing import VideoTimeline
from examwatch.evidence_clips import ClipRecorder
from examwatch.camera_quality import assess_quality
from examwatch.exam_rules import SUPPORTED_OBJECTS, validate_forbidden, model_object_classes, clip_window
from examwatch.screen_calibration import screen_measurements, outside_screen
from examwatch.monitoring_logic import (
    EventTracker, face_measurements, calibration_baseline, classify_measurements,
)


ROOT = Path(__file__).resolve().parents[1]

def run_monitoring(settings, emit, stop_event, recalibrate_event, controls=None):
    if controls is not None and settings.get('source_type', 'Camera') == 'Camera':
        from examwatch.camera_preparation import prepare_camera
        prepared = prepare_camera(ROOT, settings, emit, stop_event, controls)
        if prepared is None:
            emit({'message': 'Camera closed. No exam session was started.', 'phase': 'closed'})
            return
        try:
            return _run_analysis(settings, emit, stop_event, recalibrate_event, prepared)
        finally:
            prepared['cap'].release()
            prepared['landmarker'].close()
    return _run_analysis(settings, emit, stop_event, recalibrate_event)


def _run_analysis(settings, emit, stop_event, recalibrate_event, prepared=None):
    # Imports stay inside the worker so the UI opens without vision packages.
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    from ultralytics import YOLO

    CAMERA_INDEX = settings["camera"]
    is_video = settings.get("source_type", "Camera") == "Video file"
    video_path = Path(settings.get("video_path", ""))
    if is_video and not video_path.is_file():
        raise ValueError("Select an existing video file before starting.")
    MAX_FACES = 5
    CALIBRATION_FRAMES = 150
    MIN_EVENT_DURATION = settings["minimum_duration"]
    RECOVERY_PERIOD = 0.5
    FACE_ABSENCE_SECONDS = settings["absence_duration"]
    HIGH_ALERT_SECONDS = 3.0
    HEAD_THRESHOLD = 0.15
    PITCH_THRESHOLD = 0.15
    GAZE_THRESHOLD = 0.10
    OBJECT_CONFIDENCE = settings["confidence"]
    forbidden = validate_forbidden(settings.get('forbidden_objects',
        [name for name in ('CELL PHONE', 'BOOK', 'CLOCK') if name not in settings.get('allowed_objects', [])]))
    OBJECT_CLASSES = {}
    ALLOWED_OBJECTS = set(SUPPORTED_OBJECTS) - set(forbidden)
    clip_pre, clip_post = clip_window(settings.get('clip_duration_seconds', 10))
    MODEL_DIR = ROOT / "models"
    SCREENSHOT_DIR = ROOT / "outputs/screenshots"
    REPORT_DIR = ROOT / "outputs/session_reports"
    if not (MODEL_DIR / "face_landmarker.task").is_file():
        raise FileNotFoundError("Missing models/face_landmarker.task. See README setup instructions.")

    MODEL_DIR.mkdir(exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    session_name = settings.get("session_name", "").strip() or f"Session {session_id}"
    session_start = time.monotonic()
    calibration_samples = []
    screen_envelope = prepared['screen_envelope'] if prepared else None
    baseline = tuple(screen_envelope['center'][:3]) if screen_envelope else None
    last_timestamp_ms = prepared['last_timestamp_ms'] if prepared else -1
    trackers = {
        reason: EventTracker(
            FACE_ABSENCE_SECONDS if reason == "FACE ABSENT" else MIN_EVENT_DURATION,
            RECOVERY_PERIOD,
        )
        for reason in sorted(set(forbidden) | {'CELL PHONE', 'BOOK', 'CLOCK', 'HEAD TURN', 'HEAD PITCH',
                                              'EYE GAZE', 'FACE ABSENT', 'MULTIPLE FACES'})
    }
    counters = dict.fromkeys(trackers, 0)
    events = []
    current_event = None
    cap = prepared['cap'] if prepared else None
    landmarker = prepared['landmarker'] if prepared else None
    timeline = None
    elapsed = 0.0
    end_reason = "stopped"
    clips = None
    processed_frames = 0
    quality_warning_frames = 0
    loop_started = None

    try:
        emit({"message": "Loading detection models..."})
        model = YOLO(str(MODEL_DIR / "yolov8n.pt"))
        OBJECT_CLASSES = model_object_classes(model.names, forbidden)
        options = mp_vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_DIR / "face_landmarker.task")),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_faces=MAX_FACES,
            min_face_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        if prepared is None:
            landmarker = mp_vision.FaceLandmarker.create_from_options(options)
            cap = cv2.VideoCapture(str(video_path) if is_video else CAMERA_INDEX)
        if not cap.isOpened():
            raise RuntimeError("Unable to open the video file." if is_video else
                               "Unable to open the camera. Check camera access and CAMERA_INDEX.")
        if is_video:
            timeline = VideoTimeline(cap.get(cv2.CAP_PROP_FPS))
        if settings.get('save_clips', True):
            clips = ClipRecorder(ROOT / 'outputs/clips', session_id, cv2, pre=clip_pre, post=clip_post)
        loop_started = time.monotonic()
        if prepared:
            session_start = loop_started

        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                if is_video and timeline.last is not None:
                    end_reason = "video_read_end"
                    break
                raise RuntimeError("The video has no readable frames." if is_video else
                                   "Unable to read from the camera. Available results were saved.")
            elapsed = (timeline.advance(cap.get(cv2.CAP_PROP_POS_MSEC)) if is_video
                       else time.monotonic() - session_start)
            now = session_start + elapsed
            if not is_video:
                frame = cv2.flip(frame, 1)
            processed_frames += 1
            if clips is not None:
                clips.add_frame(frame, elapsed)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp_ms = max(last_timestamp_ms + 1, int(elapsed * 1000))
            if prepared:
                timestamp_ms = max(last_timestamp_ms + 1, int((time.monotonic() - prepared['timestamp_origin']) * 1000))
            last_timestamp_ms = timestamp_ms
            result = landmarker.detect_for_video(mp_image, timestamp_ms)
            face_count = len(result.face_landmarks)
            quality = assess_quality(frame, result.face_landmarks, cv2)
            quality_warning_frames += bool(quality['warnings'])
            head_status = pitch_status = gaze_status = "NO FACE"
            signals = dict.fromkeys(trackers, False)
            signals["FACE ABSENT"] = face_count == 0
            signals["MULTIPLE FACES"] = face_count > 1

            if face_count == 1:
                values = face_measurements(result.face_landmarks[0])
                head_status = pitch_status = gaze_status = "UNAVAILABLE"
                if values is not None:
                    if baseline is None and quality['calibration_ready']:
                        calibration_samples.append(values)
                        if len(calibration_samples) >= CALIBRATION_FRAMES:
                            baseline = calibration_baseline(calibration_samples)
                    if baseline is not None:
                        head_status, pitch_status, gaze_status = classify_measurements(
                            values, baseline, HEAD_THRESHOLD, PITCH_THRESHOLD, GAZE_THRESHOLD,
                        )
                        signals["HEAD TURN"] = head_status != "FORWARD"
                        signals["HEAD PITCH"] = pitch_status != "LEVEL"
                        signals["EYE GAZE"] = gaze_status != "CENTER"
                        if screen_envelope is not None:
                            screen_values = screen_measurements(result.face_landmarks[0])
                            away = screen_values is not None and outside_screen(screen_values, screen_envelope)
                            signals['HEAD TURN'] = away and head_status != 'FORWARD'
                            signals['HEAD PITCH'] = away and pitch_status != 'LEVEL'
                            signals['EYE GAZE'] = away
                            gaze_status = 'OUTSIDE SCREEN' if away else 'ON SCREEN' if screen_values else 'UNAVAILABLE'
                    else:
                        head_status = pitch_status = gaze_status = "CALIBRATING"
            elif face_count > 1:
                head_status = pitch_status = gaze_status = "MULTIPLE FACES"

            detected_objects = set()
            results = (model(frame, classes=list(OBJECT_CLASSES), conf=OBJECT_CONFIDENCE, verbose=False)
                       if OBJECT_CLASSES else [])
            for detection_result in results:
                for box in detection_result.boxes:
                    name = OBJECT_CLASSES.get(int(box.cls[0]))
                    if name is None:
                        continue
                    detected_objects.add(name)
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    confidence = float(box.conf[0])
                    allowed = name in ALLOWED_OBJECTS
                    box_color = (0, 180, 0) if allowed else (0, 165, 255)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                    label = f"{name} {confidence:.2f}" + (" (ALLOWED)" if allowed else "")
                    cv2.putText(frame, label, (x1, max(y1 - 10, 20)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
            for name in OBJECT_CLASSES.values():
                signals[name] = name in detected_objects and name not in ALLOWED_OBJECTS

            for reason, tracker in trackers.items():
                if tracker.update(signals[reason], now):
                    counters[reason] += 1
            active_reasons = {reason for reason, tracker in trackers.items() if tracker.confirmed}

            if active_reasons:
                if current_event is None:
                    image_path = SCREENSHOT_DIR / f"event_{session_id}_{len(events) + 1:04d}.jpg"
                    saved = cv2.imwrite(str(image_path), frame)
                    if not saved:
                        print(f"Warning: unable to save screenshot: {image_path}")
                    current_event = {
                        "start_seconds": min(trackers[r].started_at for r in active_reasons) - session_start,
                        "confirmed_seconds": elapsed,
                        "reasons": sorted(active_reasons),
                        "screenshot": str(image_path) if saved else None,
                    }
                    events.append(current_event)
                    if clips is not None:
                        clips.trigger(current_event, elapsed, len(events))
                current_event["reasons"] = sorted(set(current_event["reasons"]) | active_reasons)
                current_event["last_signal_seconds"] = max(
                    trackers[r].last_signal_at for r in active_reasons
                ) - session_start
            elif current_event is not None:
                current_event["end_seconds"] = current_event["last_signal_seconds"]
                current_event["closed_seconds"] = elapsed
                current_event = None

            high_alert = any(
                tracker.confirmed and signals[reason] and tracker.duration(now) > HIGH_ALERT_SECONDS
                for reason, tracker in trackers.items()
            )
            pending = any(signals.values())
            status = ("HIGH ALERT" if high_alert else "FLAGGED FOR REVIEW" if active_reasons
                      else "OBSERVING" if pending else "NORMAL")
            color = (0, 0, 255) if active_reasons else (0, 165, 255) if pending else (0, 200, 0)
            emit({
                "phase": "exam" if prepared else "video_analysis" if is_video else "exam",
                "frame": frame, "status": status, "faces": face_count,
                "head": head_status, "pitch": pitch_status, "gaze": gaze_status,
                "elapsed": elapsed, "events": len(events),
                "calibration": 1.0 if screen_envelope else len(calibration_samples) / CALIBRATION_FRAMES,
                "reasons": sorted(active_reasons),
                "quality": quality,
                "processing_fps": processed_frames / max(.001, time.monotonic() - loop_started),
            })
            if recalibrate_event.is_set() and screen_envelope is None:
                recalibrate_event.clear()
                calibration_samples.clear()
                baseline = None
                for reason in ("HEAD TURN", "HEAD PITCH", "EYE GAZE"):
                    trackers[reason].reset()

    except Exception:
        end_reason = "error"
        raise
    finally:
        processing_duration = time.monotonic() - session_start
        session_duration = timeline.duration if timeline is not None else (0.0 if is_video else processing_duration)
        if cap is not None and prepared is None:
            cap.release()
        if landmarker is not None and prepared is None:
            landmarker.close()
        if clips is not None:
            clips.close()
        if current_event is not None:
            current_event["end_seconds"] = current_event["last_signal_seconds"]
            current_event["closed_seconds"] = session_duration
            current_event["closed_by_session_end"] = True
        report_data = {
            "session_name": session_name,
            "session_id": session_id,
            "source_type": "video" if is_video else "camera",
            "source_name": video_path.name if is_video else f"Camera {CAMERA_INDEX}",
            "end_reason": end_reason,
            "processing_duration_seconds": processing_duration,
            "processed_frames": processed_frames,
            "processing_fps": processed_frames / max(.001, time.monotonic() - loop_started) if loop_started else 0,
            "quality_warning_frames": quality_warning_frames,
            "clip_settings": {"enabled": settings.get('save_clips', True), "pre_seconds": clip_pre,
                              "post_seconds": clip_post, "total_seconds": clip_pre + clip_post,
                              "fps": 10, "max_width": 640},
            "duration_seconds": session_duration,
            "calibration_complete": baseline is not None,
            "baseline": baseline,
            "screen_calibration": screen_envelope,
            "timing_origin": "exam_start" if prepared else "media_start" if is_video else "analysis_start",
            "allowed_objects": sorted(ALLOWED_OBJECTS),
            "forbidden_objects": forbidden,
            "thresholds": {
                "minimum_event_seconds": MIN_EVENT_DURATION,
                "recovery_seconds": RECOVERY_PERIOD,
                "face_absence_seconds": FACE_ABSENCE_SECONDS,
                "high_alert_seconds": HIGH_ALERT_SECONDS,
                "head": HEAD_THRESHOLD, "pitch": PITCH_THRESHOLD,
                "gaze": GAZE_THRESHOLD, "object_confidence": OBJECT_CONFIDENCE,
            },
            "confirmed_episodes": len(events),
            "confirmed_reason_counts": counters,
            "events": events,
        }
        json_path = REPORT_DIR / f"session_report_{session_id}.json"
        json_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        report = "\n".join([
            "FINAL SESSION REPORT", "====================",
            f"Session name: {session_name}",
            f"Source: {video_path.name if is_video else 'Camera ' + str(CAMERA_INDEX)}",
            f"Confirmed review episodes: {len(events)}",
            *[f"{reason}: {count}" for reason, count in counters.items()],
            f"Calibration complete: {baseline is not None}",
            f"Total session duration: {session_duration:.2f} seconds",
            "Counts represent confirmed episodes; overlapping reasons may share an episode.",
            "Flags require human review and do not establish cheating.",
        ])
        report_path = REPORT_DIR / f"session_report_{session_id}.txt"
        report_path.write_text(report, encoding="utf-8")
        emit({"report_path": str(json_path), "message": "Session saved."})
