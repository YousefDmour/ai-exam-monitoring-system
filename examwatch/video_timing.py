"""Video timeline independent of inference speed."""
import math


class VideoTimeline:
    def __init__(self, fps):
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("Video frame rate is unavailable. Convert the video to a standard MP4 and retry.")
        self.interval = 1.0 / fps
        self.last = None

    def advance(self, position_ms):
        fallback = 0.0 if self.last is None else self.last + self.interval
        position = position_ms / 1000
        if not math.isfinite(position) or position < 0:
            position = fallback
        if self.last is not None and position <= self.last:
            position = fallback
        self.last = position
        return position

    @property
    def duration(self):
        return 0.0 if self.last is None else self.last + self.interval
