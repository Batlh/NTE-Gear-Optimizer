"""Distance-only gesture intent. Elapsed time never turns a tap into a swipe."""

from dataclasses import dataclass
from math import hypot, isfinite
from time import perf_counter


@dataclass
class TouchIntent:
    x: float
    y: float
    slop: float
    started: float | None = None
    max_distance: float = 0.0
    distance: float = 0.0
    kind: str = 'TAP'

    def __post_init__(self):
        if not isfinite(self.slop) or self.slop <= 0:
            raise ValueError('Touch slop must be finite and positive')
        if self.started is None:
            self.started = perf_counter()

    def move(self, x, y):
        self.distance = hypot(x - self.x, y - self.y)
        self.max_distance = max(self.max_distance, self.distance)
        if self.max_distance > self.slop:
            self.kind = 'SWIPE'
        return self.kind

    def finish(self, x, y, now=None):
        self.move(x, y)
        return {
            'classification': self.kind,
            'distance_px': round(self.distance, 3),
            'max_distance_px': round(self.max_distance, 3),
            'touch_slop_px': self.slop,
            'duration_ms': round(
                ((perf_counter() if now is None else now) - self.started) * 1000, 3
            ),
            'duration_used_for_classification': False,
        }
