# ExamWatch - AI Exam Monitoring System

A local desktop application for a university computer-vision project. ExamWatch
combines MediaPipe facial landmarks and YOLO object detection to flag events for
human review. It supports live cameras and recorded exam videos.

## Features

- Fullscreen desktop dashboard with camera/video selection and configurable alerts.
- Personalized head-position and gaze calibration with camera-quality guidance.
- Phone/book detection, allowed-object settings, multiple faces, and face absence.
- Confirmation and recovery timing to reduce brief false alarms.
- Named sessions, screenshots, silent event clips, and JSON/text reports.
- Event review statuses and Arabic/English notes saved with the session.
- PDF export with screenshots, review notes, and Arabic text support.
- Ground-truth interval evaluation: precision, recall, F1, false alerts, and misses.

## Project structure

```text
ai-exam-monitoring-system/
|-- app.py                         # Desktop application entry point
|-- examwatch/                     # Detection, UI helpers, storage, and evaluation
|   |-- dashboard.py               # Desktop layout and controls
|   |-- monitoring_logic.py        # Camera-independent tracking and calibration
|   |-- monitoring_runner.py       # Background camera/video analysis
|   |-- camera_quality.py          # Lighting, focus, and face-position guidance
|   |-- evidence_clips.py          # Bounded pre-buffer and clip recording
|   |-- clip_player.py             # Local evidence video player
|   |-- session_storage.py         # Review persistence and session deletion
|   |-- pdf_report.py              # PDF export with Arabic support
|   |-- evaluation.py              # Interval matching and metrics
|   |-- evaluation_panel.py        # Evaluation dashboard
|   `-- video_timing.py            # Media timestamps and frame-rate fallback
|-- tests/                         # Logic, UI, evidence, and report tests
|-- docs/                          # Evaluation guide and draft flowchart
|-- models/                        # Local model binaries (ignored by Git)
|-- outputs/                       # Local sessions/evidence/exports (ignored)
|-- exam_monitoring_system.ipynb    # Experimental notebook
|-- requirements.txt               # Application dependencies
`-- requirements-dev.txt           # Application dependencies plus Jupyter
```

## Setup

Use Python 3.10 or 3.11 for the pinned vision dependencies. Run commands from the
project root. The standard Windows Python distribution includes Tkinter.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For an existing working environment, activate that environment and install the
updated requirements there. Run the app and install its packages with the same
Python interpreter.

Download the MediaPipe model before the first run:

```powershell
New-Item -ItemType Directory -Path models -Force | Out-Null
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" -OutFile "models/face_landmarker.task"
```

Place `yolov8n.pt` in `models/`. Ultralytics downloads it on first use if missing.
Initial model downloads require internet; local models can be reused offline.

```powershell
python app.py
```

## Using the desktop app

### Live monitoring

Choose **Camera** and a camera index (usually 0), or **Video file** and **Choose
video...**. Enter an optional session name, configure durations/confidence, and
select allowed objects. Click **Start session** and look forward for calibration
(150 valid single-face samples). Calibration pauses when quality checks fail;
object and face-count monitoring remain active.

Use **Recalibrate** if needed and **End & save** to finish. **Exit app** ends an
active session and waits for cleanup. **Esc** leaves fullscreen; **F11** toggles it.
Settings are locked during a session.

Most signals require 1 second to confirm by default; face absence requires 3
seconds. Confirmed reasons recover after 0.5 seconds without a signal. High alert
indicates a currently present confirmed signal in an episode older than 3 seconds.
These thresholds require validation on representative recordings.

Recorded-video timestamps use media time, independent of inference speed. Original
video orientation is preserved; camera previews are mirrored. Video analysis saves
at the end of decoding, or saves partial results when stopped. A corrupt file may
stop decoding early. Unsupported frame-rate metadata is rejected. Calibration
requires a suitable forward-facing segment at the beginning of the clip.

### Evidence and session review

Select a session in **Session reports**, then select an event. Set **Unreviewed**,
**Needs follow-up**, **False alarm**, or **Reviewed**, add notes, and click **Save
review** before switching events or sessions. Decisions persist in JSON reports
with UTC update timestamps; detector reasons/counts are preserved.

When enabled, event clips contain up to 5 seconds before confirmation and 5 seconds
after it. They are silent MJPG AVI at 10 FPS, with maximum width 640 pixels. A
bounded JPEG buffer samples processed frames; low inference FPS can result in
repeated frames. Context is shorter near session boundaries. **Play clip** opens
local playback with pause and restart controls. Older reports without clips remain
readable.

**Export PDF** exports saved data, screenshots, and reviewer notes. Save edits
first. PDFs are snapshots: export again after changing notes or evaluations. Arabic
requires Arial (Windows) or DejaVu Sans (Linux), plus the included shaping libraries.

**Delete session** asks for confirmation and removes its reports, unshared
screenshots/clips, and default PDF/evaluation exports. Custom exports saved outside
the default location are retained.

### Accuracy evaluation

Open **Accuracy evaluation**, select a saved session, export the annotation
template, independently label the entire processed timeline, set `complete=true`,
and import it. The dashboard shows precision, recall, F1, false alerts, missed
events, reason-level false alerts/minute, and processing FPS. Saved evaluations
are included in subsequent PDF exports.

Matching uses one-to-one intervals per reason at temporal IoU >= 0.30. Overlapping
reasons currently share their episode interval. No scores or overall accuracy are
invented without independent labels. See [the evaluation guide](docs/evaluation-guide.md)
for the annotation format and metric definitions.

## Local outputs

```text
outputs/
|-- screenshots/       # One image per confirmed episode
|-- clips/             # Silent event videos
|-- session_reports/   # JSON timelines/settings/reviews and text summaries
|-- pdf/               # Default PDF exports
`-- evaluations/       # Ground-truth evaluation results
```

Overlapping reasons can share one episode and screenshot, while each reason has its
own count. Reason counts can exceed the episode count. End times mark the last
signal; closure times include recovery or shutdown. Generated output directories
are created as needed and are never committed by default.

## Experimental notebook

The notebook retains its experimental pipeline and original controls; new desktop
features live in `app.py` and `examwatch/`. Keep the notebook working directory at
the project root. Restart its kernel after code changes, run cells in order, and
close its camera session before starting the desktop app.

```powershell
python -m pip install -r requirements-dev.txt
python -m ipykernel install --user --name ai-exam-monitoring --display-name "AI Exam Monitoring"
python -m notebook exam_monitoring_system.ipynb
```

Select the registered kernel. In the notebook preview, **C** recalibrates and **Q**
ends the session. The flowchart in `docs/` is a conceptual draft and does not yet
represent every desktop feature.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests never open the camera. Timing/evaluation/storage tests use synthetic data;
video/PDF tests need the corresponding dependencies. Desktop smoke tests require
Tk and skip when no display is available. Passing tests does not establish
real-world detection accuracy; evaluate consented recordings separately.

## GitHub contents and limitations

Source code, tests, notebook source, documentation, and dependency lists belong in
Git. Models, local environments, editor settings, caches, and session outputs are
ignored. Clear notebook outputs before sharing, since they may contain local data.

Head/gaze and quality estimates are heuristics, not physical rotation measurements
or proof of cheating. Lighting, camera position, glasses, and occlusion can affect
results. Flags require human review. Obtain participants' permission before
recording. This project is intended for university education and research.
