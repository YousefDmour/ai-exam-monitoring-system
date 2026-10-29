# Evaluating ExamWatch

The evaluation tab compares saved event intervals with independent, complete
annotations for the same processed timeline. It does not infer cheating, student
intent, or true-negative accuracy from review decisions.

1. Analyze a consented recording and finish the session.
2. Open **Accuracy evaluation**, refresh sessions, and select that session.
3. Click **Export annotation template**.
4. Watch the entire original recording and label every target event using seconds
   from the start of the processed video. Do not copy the model's predictions.
5. Set `complete` to `true` only when the whole processed timeline is labeled.
6. Click **Import labels & evaluate** and select the completed JSON file.

For example, keep the exported `session_id` and `duration_seconds` unchanged, and
replace `events` with intervals such as:

```json
{
  "session_id": "USE_THE_EXPORTED_SESSION_ID",
  "duration_seconds": 60.0,
  "complete": true,
  "events": [
    {"start_seconds": 10.0, "end_seconds": 15.0, "reasons": ["CELL PHONE"]},
    {"start_seconds": 30.0, "end_seconds": 34.0, "reasons": ["FACE ABSENT"]}
  ]
}
```

Use the exact reason names listed in the template's `allowed_reasons`. Annotate
target behaviors consistently with the experiment's allowed objects and minimum
durations. If a clip contains no target events after independent review, a complete
annotation with an empty `events` list is a valid negative example.

Predictions and annotations match once per reason when temporal intersection over
union (IoU) is at least 0.30. Matching maximizes the number of matched intervals.
Extra predictions are false alerts; unmatched annotations are missed events.
Reports currently group overlapping reasons into a shared episode interval, so
reason metrics are an approximation of reason-specific temporal boundaries.

- Precision = matched / (matched + false alerts).
- Recall = matched / (matched + missed events).
- F1 = 2 * matched / (2 * matched + false alerts + missed events).
- N/A means there is no valid denominator.
- False alerts/minute is a reason-level rate over processed media duration.
- Processing FPS includes local detection/evidence work; it is not camera FPS.

Results are saved in `outputs/evaluations/`. Use multiple recordings, varied
lighting, glasses, normal movements, and both positive and negative examples. Keep
threshold-tuning recordings separate from the final evaluation recordings. No
project-wide accuracy claim is justified by one clip or the synthetic test suite.
