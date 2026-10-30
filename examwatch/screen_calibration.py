"""Explicit camera phases and a personal, heuristic screen-look envelope."""
from dataclasses import dataclass, field
from statistics import median
import threading

from examwatch.monitoring_logic import face_measurements

TARGETS = (('Center', .5, .5), ('Left', .08, .5), ('Right', .92, .5),
           ('Top', .5, .10), ('Bottom', .5, .90))


@dataclass
class CameraControls:
    calibrate: threading.Event = field(default_factory=threading.Event)
    begin_exam: threading.Event = field(default_factory=threading.Event)
    shown_target: int = -1


def screen_measurements(face):
    base = face_measurements(face)
    if base is None:
        return None
    vertical = []
    for a, b, iris in ((33, 133, 468), (362, 263, 473)):
        width = abs(face[b].x - face[a].x)
        if width < 1e-6:
            return None
        vertical.append((face[iris].y - (face[a].y + face[b].y) / 2) / width)
    return tuple(base) + (sum(vertical) / 2,)


def fit_screen_envelope(groups):
    if len(groups) != len(TARGETS) or any(len(group) < 15 for group in groups):
        raise ValueError('Complete all five targets with a clear, stable face.')
    centers = [tuple(median(column) for column in zip(*group)) for group in groups]
    spans = [max(column) - min(column) for column in zip(*centers)]
    if max(spans[0], spans[2]) < .04 or max(spans[1], spans[3]) < .035:
        raise ValueError('Screen positions were too similar. Improve lighting, keep eyes visible, and follow each target before retrying.')
    bounds = []
    for index, column in enumerate(zip(*centers)):
        noise = median(abs(sample[index] - centers[g][index])
                       for g, group in enumerate(groups) for sample in group)
        margin = max((.07, .07, .055, .055)[index], noise * 4, spans[index] * .20)
        bounds.append((min(column) - margin, max(column) + margin))
    return {'center': centers[0], 'bounds': bounds, 'target_centers': centers,
            'method': 'Five target median envelopes with noise margin; not physical gaze coordinates.'}


def outside_screen(values, envelope):
    return any(value < low or value > high for value, (low, high) in zip(values, envelope['bounds']))
