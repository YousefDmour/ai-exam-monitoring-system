"""Delete only the selected local session's reports and unshared evidence."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REVIEW_STATUSES = ("Unreviewed", "Needs follow-up", "False alarm", "Reviewed")


def save_event_review(root, report_path, event_index, status, notes):
    """Update one event atomically, preserving detection data and other reviews."""
    reports = (Path(root).resolve() / "outputs/session_reports").resolve()
    report_path = Path(report_path).resolve()
    if report_path.parent != reports or report_path.suffix != ".json":
        raise ValueError("Review report is outside the session reports folder.")
    if status not in REVIEW_STATUSES:
        raise ValueError("Invalid review status.")
    data = json.loads(report_path.read_text(encoding="utf-8"))
    events = data.get("events", [])
    if not 0 <= event_index < len(events):
        raise ValueError("The selected event no longer exists. Refresh the report.")
    review = {"status": status, "notes": notes.strip(),
              "updated_at": datetime.now(timezone.utc).isoformat()}
    events[event_index]["review"] = review
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=reports,
                                         prefix=".review-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(str(temporary), str(report_path))
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return review


def delete_session(root, report_path):
    root = Path(root).resolve()
    reports = (root / "outputs/session_reports").resolve()
    screenshots = (root / "outputs/screenshots").resolve()
    clips = (root / "outputs/clips").resolve()
    report_path = Path(report_path).resolve()
    if (report_path.parent != reports or report_path.suffix != ".json"
            or not report_path.name.startswith("session_report_")):
        raise ValueError("The selected report is outside the session reports folder.")
    data = json.loads(report_path.read_text(encoding="utf-8"))

    def evidence_paths(data):
        paths = set()
        for event in data.get("events", []):
            for key, folder, extensions in (('screenshot', screenshots, ('.jpg', '.jpeg', '.png')),
                                             ('clip', clips, ('.avi', '.mp4'))):
                name = event.get(key)
                if not name:
                    continue
                path = Path(name)
                path = (path if path.is_absolute() else root / path).resolve()
                if path.parent != folder or path.suffix.lower() not in extensions:
                    raise ValueError(f"A {key} reference is outside its evidence folder.")
                paths.add(path)
        return paths

    candidates = evidence_paths(data)
    # Preserve images referenced by other sessions. If another report cannot be
    # read, keep all images rather than risk deleting shared evidence.
    for other in reports.glob("*.json"):
        if other.resolve() == report_path:
            continue
        try:
            candidates -= evidence_paths(json.loads(other.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, AttributeError):
            candidates.clear()
            break
    paired_text = report_path.with_suffix(".txt")
    if paired_text.resolve().parent != reports:
        raise ValueError("The paired text report is outside the reports folder.")
    for folder, filename in (('pdf', report_path.stem + '.pdf'),
                             ('evaluations', report_path.stem + '_evaluation.json')):
        directory = (root / 'outputs' / folder).resolve()
        paired = (directory / filename).resolve()
        if paired.parent != directory:
            raise ValueError('A derived report is outside its output folder.')
        candidates.add(paired)
    for path in sorted(candidates):
        path.unlink(missing_ok=True)
    paired_text.unlink(missing_ok=True)
    report_path.unlink()
