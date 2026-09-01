# Fraud Detection Project

This project is a real-time cheat detection system for exam or video-monitoring scenarios. It combines MediaPipe face landmark tracking with Ultralytics YOLO object detection to detect suspicious head movement, gaze direction, and forbidden objects such as phones, books, and clocks.

## Features

- Face landmark detection using MediaPipe
- Head pose estimation
- Eye gaze estimation
- Object detection with YOLOv8
- Suspicious event counting and session reporting
- Screenshot capture for suspicious moments
- Live webcam feedback overlay

## Project structure

- `p.ipynb` — main notebook containing the detection pipeline
- `face_landmarker.task` — MediaPipe face landmark model asset downloaded at runtime
- `yolov8n.pt` — YOLO model file downloaded automatically by Ultralytics if needed
- `session_reports/` — generated reports for each run
- `screenshots/` — saved screenshots of suspicious frames
- `requirements.txt` — Python package requirements

## Requirements

Python 3.10+ is recommended.

## Setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

   On Windows PowerShell:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Open the notebook and run all cells:

   ```bash
   jupyter notebook p.ipynb
   ```

## Notes

- The file `face_landmarker.task` is large and is not usually committed to GitHub.
- The YOLO weights file `yolov8n.pt` is also large and should be generated or downloaded locally.
- The project may require camera access to run correctly.

## Output

The application will:

- show live video with detection overlays,
- save suspicious screenshots to `screenshots/`,
- write a summary report to `session_reports/` when the session ends.

## License

This project is provided for educational and research purposes.
