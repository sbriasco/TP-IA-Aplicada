"""Five second diagnostic windows; bounded and reset across discontinuities."""

from collections import deque


class LivePerformance:
    def __init__(self):
        self.points = deque(maxlen=2048)
        self.analyzed = 0

    def reset(self):
        self.points.clear()
        self.analyzed = 0

    def observe(self, sequence, captured_seconds, published_seconds):
        self.analyzed += 1
        self.points.append((sequence, captured_seconds, published_seconds, self.analyzed))
        while len(self.points) > 1 and published_seconds - self.points[0][2] > 5:
            self.points.popleft()
        first = self.points[0]
        capture_time = captured_seconds - first[1]
        analysis_time = published_seconds - first[2]
        return (
            (sequence - first[0]) / capture_time if capture_time > 0 else None,
            (self.analyzed - first[3]) / analysis_time if analysis_time > 0 else None,
        )
