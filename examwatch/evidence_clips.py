"""Bounded JPEG pre-buffer and short, silent event videos."""
from bisect import bisect_right
from collections import deque
from pathlib import Path


class ClipRecorder:
    def __init__(self, directory, session_id, cv2, pre=5.0, post=5.0, fps=10):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.session_id, self.cv = session_id, cv2
        self.pre, self.post, self.fps = pre, post, fps
        self.buffer = deque(maxlen=int(pre * fps) + 2)
        self.pending = []
        self.last_sample = None

    def add_frame(self, frame, timestamp):
        if self.last_sample is not None and timestamp - self.last_sample < 1 / self.fps - 1e-6:
            return
        height, width = frame.shape[:2]
        scale = min(1.0, 640 / width)
        small = self.cv.resize(frame, (max(2, int(width * scale)), max(2, int(height * scale))))
        ok, jpeg = self.cv.imencode('.jpg', small, [self.cv.IMWRITE_JPEG_QUALITY, 75])
        if not ok:
            return
        self.last_sample = timestamp
        sample = (timestamp, jpeg)
        self.buffer.append(sample)
        while self.buffer and timestamp - self.buffer[0][0] > self.pre:
            self.buffer.popleft()
        for item in list(self.pending):
            item['samples'].append(sample)
            if timestamp >= item['until']:
                self.finish(item)

    def trigger(self, event, timestamp, number):
        event['clip_status'] = 'recording'
        self.pending.append({'event': event, 'samples': list(self.buffer),
                             'until': timestamp + self.post, 'number': number})

    def finish(self, item):
        event, samples = item['event'], item['samples']
        writer = None
        try:
            if not samples:
                raise RuntimeError('No frames available for clip')
            first = self.cv.imdecode(samples[0][1], self.cv.IMREAD_COLOR)
            if first is None:
                raise RuntimeError('Cannot decode clip frames')
            path = self.directory / f"event_{self.session_id}_{item['number']:04d}.avi"
            size = (first.shape[1], first.shape[0])
            writer = self.cv.VideoWriter(str(path), self.cv.VideoWriter_fourcc(*'MJPG'), self.fps, size)
            if not writer.isOpened():
                raise RuntimeError('MJPG video codec unavailable')
            times = [sample[0] for sample in samples]
            end = min(times[-1], item['until'])
            count = max(1, int(round((end - times[0]) * self.fps)))
            previous_index, image = -1, first
            for index in range(count):
                sample_index = max(0, bisect_right(times, times[0] + index / self.fps) - 1)
                if sample_index != previous_index:
                    image = self.cv.imdecode(samples[sample_index][1], self.cv.IMREAD_COLOR)
                    previous_index = sample_index
                if image is None:
                    raise RuntimeError('Cannot decode clip frame')
                writer.write(self.cv.resize(image, size))
            event.update(clip=str(path), clip_status='saved', clip_start_seconds=times[0],
                         clip_end_seconds=end, clip_truncated=end < item['until'])
        except Exception as error:
            event.update(clip=None, clip_status='failed', clip_error=str(error))
        finally:
            if writer is not None:
                writer.release()
            self.pending.remove(item)

    def close(self):
        for item in list(self.pending):
            self.finish(item)
