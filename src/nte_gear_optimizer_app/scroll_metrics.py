"""Scroll presentation observations. No input, layout or scheduling decisions."""

import math
import statistics
import time
from collections import deque


def frame_statistics(timestamps, refresh_hz):
    intervals = [1000 * (b - a) for a, b in zip(timestamps, timestamps[1:]) if b > a]
    if not intervals:
        return {
            'status': 'UNVERIFIED_INSUFFICIENT_FRAMES',
            'drawn_frames': len(timestamps),
        }
    ordered = sorted(intervals)
    median = statistics.median(intervals)
    result = {
        'status': 'MEASURED_GL_FLIP_PROXY',
        'drawn_frames': len(timestamps),
        'drawn_duration_ms': round(1000 * (timestamps[-1] - timestamps[0]), 3),
        'fps': round(1000 * len(intervals) / sum(intervals), 3),
        'frame_interval_median_ms': round(median, 3),
        'frame_interval_p95_ms': round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3),
        'refresh_hz': refresh_hz,
        'missed_frames_percent': None,
        'scope': 'GL flips following observed content movement, not physical display presentation.',
    }
    if refresh_hz is not None and math.isfinite(refresh_hz) and refresh_hz > 1:
        budget = 1000 / refresh_hz
        slots = sum(max(1, math.floor(value / budget + 0.5)) for value in intervals)
        result['expected_refresh_slots'] = slots
        result['missed_refresh_slots'] = slots - len(intervals)
        result['missed_frames_percent'] = round(
            100 * (slots - len(intervals)) / slots, 3
        )
    return result


class ScrollMetrics:
    def __init__(self, emit, refresh_hz=None, clock=time.perf_counter):
        self.emit, self.refresh_hz, self.clock = emit, refresh_hz, clock
        self.current = None
        self.recent = deque(maxlen=100)

    def begin(self, identifier, x, y):
        self.finish()
        self.current = {
            'touch_id': str(identifier),
            'start': self.clock(),
            'origin': (x, y),
            'last_touch': (x, y),
            'released': False,
            'first_drag': None,
            'first_visible': None,
            'last_change': None,
            'pending': False,
            'frames': deque(maxlen=7200),
            'distance': 0.0,
            'label': None,
            'last_position': None,
        }

    def move(self, identifier, x, y):
        g = self.current
        if g is None or g['touch_id'] != str(identifier):
            return
        if (x, y) != g['origin'] and g['first_drag'] is None:
            g['first_drag'] = self.clock()
        g['last_touch'] = (x, y)

    def end(self, identifier):
        if self.current is not None and self.current['touch_id'] == str(identifier):
            self.current['released'] = True
            self.current['release_time'] = self.clock()

    def changed(self, label, position):
        g = self.current
        if g is None or g['first_drag'] is None:
            return
        if g['label'] is not None and g['label'] != label:
            return
        g['label'] = label
        if g['last_position'] is not None:
            g['distance'] += abs(position - g['last_position'])
        g['last_position'] = position
        g['last_change'] = self.clock()
        g['pending'] = True

    def frame(self, *args):
        g = self.current
        if g is None or not g['pending']:
            return
        now = self.clock()
        g['pending'] = False
        g['frames'].append(now)
        if g['first_visible'] is None:
            g['first_visible'] = now

    def settle(self, dt=0):
        g = self.current
        if g is not None and g['released']:
            last = g['last_change'] or g['release_time']
            if self.clock() - last >= 0.15:
                self.finish()

    def finish(self):
        g, self.current = self.current, None
        if g is None or g['first_drag'] is None or not g['frames']:
            return
        row = frame_statistics(list(g['frames']), self.refresh_hz)
        row.update(
            touch_id=g['touch_id'],
            scroll=g['label'],
            distance_px=round(g['distance'], 3),
            gesture_duration_ms=round(1000 * (self.clock() - g['start']), 3),
            first_drag_to_visible_movement_ms=round(
                1000 * (g['first_visible'] - g['first_drag']), 3
            ),
        )
        self.recent.append(row)
        try:
            self.emit('scroll_gesture_metrics', **row)
        except Exception:
            pass

    def summary(self):
        measured = [r for r in self.recent if 'fps' in r]
        return {
            'gestures': list(self.recent),
            'measured_gesture_count': len(measured),
            'median_gesture_fps': statistics.median([r['fps'] for r in measured])
            if measured
            else None,
            'reference_refresh_hz': self.refresh_hz,
            'scope': 'At most100retainedgestures; no replacement for Samsung physical-device test.',
        }
