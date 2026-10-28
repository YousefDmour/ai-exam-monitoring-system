# AI Exam Monitoring System

A university computer-vision project that flags exam video events for human review.
It combines MediaPipe facial landmarks with YOLO object detection and produces
screenshots, event timelines, and session summaries.

## Features

- Personalized calibration for head position, vertical movement, and eye gaze.
- Multiple-face and prolonged face-absence alerts.
- Phone and book detection, with configurable allowed objects (clocks by default).
- Duration thresholds and recovery timing to reduce brief false alarms.
- One screenshot per confirmed episode, plus text and JSON reports.
- Live preview with calibration progress and keyboard controls.

## Project structure

```text
ai-exam-monitoring-system/
|-- exam_monitoring_system.ipynb   # Main application; run from project root
|-- monitoring_logic.py           # Timing and normalized measurement helpers
|-- requirements.txt             # Application dependencies
|-- requirements-dev.txt         # Application + Jupyter Notebook
|-- tests/
|   |-- __init__.py
|   `-- test_monitoring_logic.py
|-- docs/
|   `-- cheat-detection-flowchart.png
|-- models/
|   |-- README.md
|   |-- face_landmarker.task      # Local, ignored by Git
|   `-- yolov8n.pt                # Local, ignored by Git
`-- outputs/                     # Created at runtime, ignored by Git
    |-- screenshots/
    `-- session_reports/
```

The flowchart in `docs/` is a conceptual draft; the notebook is the source of truth
for current event timing and control flow.

## Setup (Windows PowerShell)

Python 3.10+ is recommended. Open a terminal in the project root.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Download the MediaPipe face model into `models/`:

```powershell
New-Item -ItemType Directory -Path models -Force | Out-Null
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" -OutFile "models/face_landmarker.task"
```

YOLO weights are downloaded by Ultralytics on first use if missing. An internet
connection is needed for initial downloads. Existing local model files can be
placed in `models/` for offline use afterward.

Register the environment as a notebook kernel and open the notebook:

```powershell
python -m ipykernel install --user --name ai-exam-monitoring --display-name "AI Exam Monitoring"
python -m notebook exam_monitoring_system.ipynb
```

Select **AI Exam Monitoring** as the kernel, then run all cells in order. If you
already have a configured Jupyter or VS Code environment, select that environment
and open the notebook directly. Keep the notebook working directory at the project
root so local imports and asset paths resolve correctly.

## Running a session

1. Allow camera access and look forward during calibration. Calibration uses 150
   valid single-face samples and pauses when no face or multiple faces are visible.
2. Object detection and face-count alerts remain active during calibration.
3. Press **C** in the preview to recalibrate, or **Q** to finish and save reports.

Configure the camera, thresholds, allowed objects, and face limit in the first cell.
By default, most signals require 1 second to confirm; face absence requires 3
seconds. Confirmed reasons close after 0.5 seconds without a signal. High alert is
shown when a confirmed, currently present signal has an episode older than 3 seconds.

## Reports and counts

Reports are saved to `outputs/session_reports/`; screenshots are saved to
`outputs/screenshots/`. Text reports summarize counts. JSON reports include timing,
reasons, screenshot paths, calibration details, and configured thresholds.

Overlapping reasons can share one episode and screenshot. Each reason has its own
confirmed count, so reason counts may exceed the total episode count. End times
mark the last detected signal; closure times include recovery or session shutdown.

## Tests

These checks run without a camera or the vision dependencies:

```powershell
python -m unittest discover -s tests -v
```

They cover sustained events, short detections, recovery, face-absence timing, and
calibrated measurements. Camera behavior and detection accuracy require separate
manual evaluation on representative recordings.

## GitHub contents

Commit source code, tests, documentation, and dependency files. `.gitignore`
excludes virtual environments, model binaries, generated captures/reports, Python
caches, and local environment files. Saved notebook outputs are cleared for sharing.

## Limitations

Head and gaze outputs are calibrated position heuristics, not physical rotation
angles. Left/right refers to the mirrored preview. Lighting, camera position,
occlusion, and glasses can affect results. Flags require human review and do not
establish cheating. Capture recordings only with participants' permission.

This project is intended for university education and research.
