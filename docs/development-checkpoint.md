# Development checkpoint - 2026-10-30

## Implemented

- Consistent English/dark navigation across Overview, New session, camera
  monitoring, Session library, Session review, Accuracy evaluation, and Settings.
- Supervisor-configurable supported forbidden objects and 5-15 second total clips.
- Raw live preview without analysis, followed by explicit five-target gaze
  calibration and a separate Start exam action.
- Personalized screen-look envelope gating head/gaze alerts during live exams.
- Recorded-video analysis, evidence clips, inline playback, review decisions,
  Arabic/English notes, and PDF export.
- Search and status filtering, safe session deletion, independent label evaluation,
  and atomically saved application defaults.
- Python-version-aware ReportLab requirements for older working environments.

## Verified

The automated suite covers timing, camera phase isolation, simulated face/gaze
inputs, media timestamps, real synthetic clip encoding/playback, PDF generation,
settings persistence, review safety, file/path boundaries, and window layout.
UI pages were inspected visually. Tests do not open a real camera.

Passing tests does not establish real-world gaze/detection accuracy. PDF export
was tested in the development environment; the compatibility repair should also
be checked in the user's working Python environment.

## Next practical validation

1. Run the app using the same Python interpreter where its vision dependencies
   are installed. Verify PDF export after installing the updated requirements.
2. Test preview -> calibration -> ready -> exam -> review -> PDF on the actual
   camera. Verify preview/calibration produce no report or alerts.
3. Check normal reading across the screen and sustained off-screen looks under
   representative lighting/glasses/camera positions. Keep camera/window placement
   unchanged after calibration and record false alarms as well as missed events.
4. Evaluate independent, consented recordings using the methodology in
   [evaluation-guide.md](evaluation-guide.md). Keep threshold-tuning recordings
   separate from the final evaluation set.

## Repository hygiene

Run with `python app.py`; run checks with
`python -m unittest discover -s tests -v`. Keep model binaries in `models/` and all
session/evidence/export/preferences files in `outputs/`. Both local models and
generated/private data are ignored by Git. The notebook remains experimental;
clear its outputs before sharing. Temporary preview scripts are not application
entry points and should not be committed.
