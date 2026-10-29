"""Camera-independent measurements and timed alert tracking."""

from dataclasses import dataclass
from statistics import median
from typing import Optional


@dataclass
class EventTracker:
    minimum_duration: float = 1.0
    recovery_period: float = 0.5
    started_at: Optional[float] = None
    last_signal_at: Optional[float] = None
    confirmed: bool = False
    recovering: bool = False

    def update(self, signal: bool, now: float) -> bool:
        """Return True exactly once when an episode becomes confirmed.

        A gap before confirmation resets the candidate. Once confirmed, short
        gaps are tolerated until recovery_period has elapsed since the signal.
        """
        if self.last_signal_at is not None:
            expired = (now - self.last_signal_at >= self.recovery_period)
            if self.confirmed and expired and (self.recovering or not signal):
                self.reset()
        if signal:
            self.recovering = False
            if self.started_at is None:
                self.started_at = now
            self.last_signal_at = now
            if not self.confirmed and now - self.started_at >= self.minimum_duration:
                self.confirmed = True
                return True
        elif not self.confirmed:
            self.reset()
        else:
            self.recovering = True
        return False

    def reset(self):
        self.started_at = None
        self.last_signal_at = None
        self.confirmed = False
        self.recovering = False

    def duration(self, now: float) -> float:
        return 0.0 if self.started_at is None else now - self.started_at


def face_measurements(face):
    """Return normalized position proxies, not physical yaw/pitch angles."""
    left, right, nose = face[33], face[263], face[1]
    width = abs(right.x - left.x)
    if width < 1e-6:
        return None
    head_x = (nose.x - (left.x + right.x) / 2) / width
    head_y = (nose.y - (left.y + right.y) / 2) / width
    gaze = []
    for a, b, iris in ((33, 133, 468), (362, 263, 473)):
        low, high = sorted((face[a].x, face[b].x))
        if high - low < 1e-6:
            return None
        gaze.append((face[iris].x - low) / (high - low))
    return head_x, head_y, sum(gaze) / len(gaze)


def calibration_baseline(samples):
    if not samples:
        raise ValueError("Calibration requires valid face samples")
    return tuple(median(values) for values in zip(*samples))


def classify_measurements(values, baseline, head_threshold=0.15,
                          pitch_threshold=0.15, gaze_threshold=0.10):
    dx, dy, dg = (value - normal for value, normal in zip(values, baseline))
    # Directions describe the mirrored preview, not anatomical left/right.
    head = "RIGHT" if dx > head_threshold else "LEFT" if dx < -head_threshold else "FORWARD"
    pitch = "DOWN" if dy > pitch_threshold else "UP" if dy < -pitch_threshold else "LEVEL"
    gaze = "RIGHT" if dg > gaze_threshold else "LEFT" if dg < -gaze_threshold else "CENTER"
    return head, pitch, gaze
