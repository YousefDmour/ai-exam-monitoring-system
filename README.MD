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
- Saved application defaults for fullscreen, camera selection, alert timing,
  object confidence, forbidden objects, and clip recording.

## Project structure

```text
ai-exam-monitoring-system/
|-- app.py                         # Desktop application entry point
|-- examwatch/                     # Application package
|   |-- dashboard.py               # Navigation and application coordination
|   |-- home_page.py               # Overview and recent sessions
|   |-- new_session_page.py        # Source, rules, and clip setup
|   |-- monitoring_page.py         # Camera preview/calibration/exam UI
|   |-- session_library.py         # Search, filters, and session actions
|   |-- session_review.py          # Evidence, decisions, and reviewer notes
|   |-- evidence_viewer.py         # Inline screenshot/video playback
|   |-- evaluation_panel.py        # Independent evaluation UI
|   |-- settings_page.py           # Default display/session settings
|   |-- camera_preparation.py      # Preview-only and guided calibration phases
|   |-- screen_calibration.py      # Five-point screen-look envelope
|   |-- monitoring_runner.py       # Background camera/video analysis
|   |-- monitoring_logic.py        # Event timing and normalized measurements
|   |-- camera_quality.py          # Lighting, focus, and positioning guidance
|   |-- exam_rules.py              # Supported objects and clip validation
|   |-- evidence_clips.py          # Bounded pre-buffer and clip recording
|   |-- video_timing.py            # Media timestamps and FPS fallback
|   |-- session_storage.py         # Review persistence and session deletion
|   |-- preferences.py             # Atomic local settings storage
|   |-- pdf_report.py              # PDF export with Arabic support
|   `-- evaluation.py              # Interval matching and metrics
|-- tests/                         # Logic, UI, evidence, and report tests
|-- docs/                          # Evaluation guide and draft flowchart
|-- models/                        # Local model binaries (ignored by Git)
|-- outputs/                       # Local sessions/evidence/exports (ignored)
|-- exam_monitoring_system.ipynb    # Experimental notebook
|-- requirements.txt               # Application dependencies
`-- requirements-dev.txt           # Application dependencies plus Jupyter
```

See [the development checkpoint](docs/development-checkpoint.md) for the current
verification scope and the next practical validation steps.

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

If PDF export reports that ReportLab requires Python 3.10+, the application is
running in an older interpreter with an incompatible ReportLab build. The
requirements select ReportLab 4.2.5 for Python below 3.10. In the same environment
used to launch the app, repair that installation with:

```powershell
python -c "import sys; print(sys.version); print(sys.executable)"
python -m pip install --force-reinstall "reportlab==4.2.5" "arabic-reshaper>=3.0,<4" python-bidi
```

Restart the app afterward. Do not edit ReportLab's internal version checks.

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

The app opens on an English, dark **Overview**. It shows real saved
session counts, sessions awaiting review, and recent sessions. **New session** opens
the dedicated session preparation page without starting a camera. Select a recent
session and click **Open selected** to review it. **Overview** in the workspace
sidebar returns to the home page. Session setup, monitoring, the library, event
review, evaluation, and settings share the same dark workspace navigation.

### Settings

Open **Settings** from any sidebar to save the startup fullscreen preference,
default camera, alert confirmation/face-absence durations, object confidence,
clip saving/total duration, and default forbidden-object categories. Click **Save
settings** to persist them locally in `outputs/preferences.json` (ignored by Git).
**Restore defaults** only loads values into the form; save to keep that change.

Session defaults are applied the next time you open **New session** and can still
be overridden for that session. Existing reports and active sessions are not
changed. Saving while a session is active also defers the fullscreen change until
the next session setup. When idle, the saved fullscreen choice applies immediately;
Esc/F11 change the current window without changing its saved startup preference.
Invalid settings are rejected before writing. Unreadable settings fall back to
defaults with a message on the Settings page, preserving the original file until
you explicitly save again.

### Live monitoring

**New session** provides the session name, input source, supervisor-defined
forbidden-object list, clip settings, and collapsed advanced settings. Add or remove
supported categories using **Add** and **Remove selected**. Defaults forbid phones
and books. The available categories include clocks, laptops, remotes, mice,
keyboards, backpacks, handbags, bottles, cups, and scissors. These are YOLO model
categories, not arbitrary custom objects: the loaded model is checked for support.
An empty forbidden list disables object alerts while face/gaze monitoring remains
active. The exact rule list is saved with each session.

Set **Clip duration** from 5 to 15 seconds total (default 10): half before alert
confirmation and half after it. For example, 15 seconds means 7.5 before and 7.5
after, subject to available frames at session boundaries. Turning clip saving off
disables the duration field. Start transitions to the monitoring screen only after
settings pass validation.

### Camera preview and screen-look calibration

The camera workspace uses the same dark sidebar and colors as Overview and New
session. It shows a three-step phase guide, exam-time/face/event cards, a bounded
camera preview, and fixed bottom controls. The phase badge distinguishes preview,
calibration, ready, and active monitoring. Exit app stays in the left sidebar.

For a live camera, **Open camera** starts a raw preview only. It does not load the
face/object models, count alerts, record clips, or create a report. Position
yourself before proceeding. **Calibrate gaze** then loads only the face model and
guides you through five targets: center, left, right, top, and bottom of the app
window. Each target includes settling time followed by at least two seconds and
15 valid samples. Poor lighting, face loss, or hiding the monitoring page pauses
sampling. Follow the dot with your eyes while keeping a comfortable head position.

Once calibration is complete, the camera stays in a ready preview until you click
**Start exam**. Only then are object detection, alert counters, evidence recording,
and the exam timer activated. Closing a preview/calibration without starting the
exam creates no session report. The settings used and learned screen-look bounds
are stored with the exam report.

The personalized envelope tolerates head/eye variation observed while following
the window targets. A sustained excursion beyond it triggers gaze review flags;
head/pitch flags are also gated by that envelope. It is a heuristic, not accurate
screen-coordinate eye tracking or proof that someone is looking off-screen.
Use a maximized/fullscreen exam window and do not move the window or camera after
calibration. A changed window geometry requires recalibration before starting.
Recalibration during an active live exam requires ending that exam first.
Recorded-video analysis keeps its automatic baseline workflow because an existing
recording cannot follow live targets.

Choose **Camera** and a camera index (usually 0), or **Video file** and **Choose
video...**. Enter an optional session name, configure durations/confidence, and
define forbidden objects. Click **Start session** and look forward for calibration
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

The dark **Session review** workspace opens from **Open review** in the library.
An event timeline sits on the left; evidence, the decision selector, and notes sit
on the right. It initially selects the first event when one exists. Use Previous
and Next to step through events, or select a row directly. Review progress counts
Reviewed/False alarm decisions as resolved; Needs follow-up remains pending.

Screenshots resize within a bounded viewport. **Play clip** plays evidence inside
the same page, with Play/Pause and Restart controls; **Screenshot** returns to the
still image without changing notes. Playback stops and releases its decoder when
switching events or leaving the page. Missing images/clips display an unavailable
message, and sessions without events keep the editor disabled.

Click **Save review** to persist the decision and Arabic/English notes. Unsaved
changes show a reminder and require confirmation before being discarded by event
switching, navigation, or application exit. Save edits before exporting a PDF.

**Session library** uses the same dark sidebar layout as Overview and the camera
workspace. Search session names (Arabic/English), filter by **All sessions**,
**Needs review**, **Reviewed**, or **No events**, and select a row. Each row shows
the session name, date, duration, event count, and review state. Search and status
filters work together, and refresh keeps the selected report when it still matches.
Unreadable reports are skipped with a visible count.

Use **Open review** (or double-click/Enter) to open event review, **Export PDF** for
the selected report, or **Delete session** with confirmation. Actions identify the
report file rather than its display name, so sessions with identical names remain
distinct. The **Library** button in event review returns to the filtered list.
Sessions with unreviewed or needs-follow-up events stay in Needs review; sessions
whose events are all Reviewed/False alarm are Reviewed. Sessions with no events
have their own No events state.

Select a session in **Session reports**, then select an event. Set **Unreviewed**,
**Needs follow-up**, **False alarm**, or **Reviewed**, add notes, and click **Save
review** before switching events or sessions. Decisions persist in JSON reports
with UTC update timestamps; detector reasons/counts are preserved.

When enabled, event clips use the configured total duration of 5-15 seconds,
split evenly before and after confirmation. They are silent MJPG AVI at 10 FPS, with maximum width 640 pixels. A
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

The evaluation page uses the shared dark sidebar and responsive metric cards.
Precision/Recall/F1 show **N/A** until a valid independent evaluation exists. Choose
a saved session, export a label template, and import completed labels to run the
evaluation. Saved results reload when the same session is selected again. The
reason table scrolls, and the main actions remain available on smaller windows.

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
