"""Reason-level interval evaluation against independently labeled ground truth."""
import math
from examwatch.exam_rules import SUPPORTED_OBJECTS

REASONS = SUPPORTED_OBJECTS + ('HEAD TURN', 'HEAD PITCH', 'EYE GAZE', 'FACE ABSENT', 'MULTIPLE FACES')


def annotation_template(report):
    return {'session_id': report['session_id'], 'complete': False,
            'duration_seconds': report['duration_seconds'],
            'instructions': 'Label ALL target events in the entire processed timeline; set complete=true only when done. Times in seconds. reasons must use allowed_reasons. Empty events means a verified negative recording.',
            'allowed_reasons': list(REASONS), 'events': []}


def evaluate_report(report, truth, threshold=.3):
    duration = float(report['duration_seconds'])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('A session with processed video is required.')
    if truth.get('session_id') != report.get('session_id') or truth.get('complete') is not True:
        raise ValueError('Ground truth must match this session and have complete=true.')
    truth_duration = float(truth.get('duration_seconds', -1))
    if not math.isfinite(truth_duration) or abs(truth_duration - duration) > .05:
        raise ValueError('Ground-truth duration must match the processed session duration.')
    if not 0 < threshold <= 1:
        raise ValueError('IoU threshold must be between 0 and 1.')

    def intervals(events):
        output = {reason: [] for reason in REASONS}
        for event in events:
            start, end = float(event['start_seconds']), float(event['end_seconds'])
            if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end <= duration + .05):
                raise ValueError('Event intervals must fall within the processed timeline.')
            reasons = event.get('reasons', [])
            if not isinstance(reasons, list) or not reasons or any(r not in REASONS for r in reasons):
                raise ValueError('Each event requires valid reasons from allowed_reasons.')
            for reason in set(reasons):
                output[reason].append((start, end))
        return output

    predicted, actual = intervals(report.get('events', [])), intervals(truth['events'])
    details = {}
    total = dict(tp=0, fp=0, fn=0)
    for reason in REASONS:
        edges = []
        for a, b in predicted[reason]:
            matches = []
            for index, (c, d) in enumerate(actual[reason]):
                union = max(b, d) - min(a, c)
                iou = max(0, min(b, d) - max(a, c)) / union if union else float(a == c)
                if iou >= threshold:
                    matches.append((iou, index))
            edges.append([i for _, i in sorted(matches, reverse=True)])
        assigned = {}

        def match(prediction, visited):
            for target in edges[prediction]:
                if target in visited:
                    continue
                visited.add(target)
                if target not in assigned or match(assigned[target], visited):
                    assigned[target] = prediction
                    return True
            return False

        tp = sum(match(index, set()) for index in range(len(edges)))
        counts = {'tp': tp, 'fp': len(predicted[reason]) - tp, 'fn': len(actual[reason]) - tp}
        details[reason] = counts
        for key in total:
            total[key] += counts[key]
    tp, fp, fn = total['tp'], total['fp'], total['fn']
    return {'session_id': report['session_id'], 'iou_threshold': threshold, **total,
            'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / (tp + fn) if tp + fn else None,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            'false_alerts_per_minute': fp / (duration / 60), 'per_reason': details,
            'method': 'One-to-one maximum-cardinality matching per reason using interval IoU. Multi-reason episodes use their shared episode interval. No true-negative accuracy is inferred.'}
