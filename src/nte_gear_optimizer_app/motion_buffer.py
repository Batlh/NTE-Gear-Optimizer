"""Fixed CI motion slots; allocate report copies only at idle snapshot time."""


class MotionBuffer:
    def __init__(self, capacity=16):
        if type(capacity) is not int or capacity < 1:
            raise ValueError('Motion capacity must be a positive integer')
        self.capacity = capacity
        self.rows = [
            dict(event=None, sx=None, sy=None, x=None, y=None, device='')
            for _ in range(capacity)
        ]
        self.position = self.count = 0

    def record(self, kind, touch):
        row = self.rows[self.position]
        row['event'] = kind
        row['sx'] = getattr(touch, 'sx', None)
        row['sy'] = getattr(touch, 'sy', None)
        row['x'] = getattr(touch, 'x', None)
        row['y'] = getattr(touch, 'y', None)
        device = getattr(touch, 'device', '')
        row['device'] = device if isinstance(device, str) else type(device).__name__
        self.position = (self.position + 1) % self.capacity
        self.count = min(self.count + 1, self.capacity)

    def snapshot(self):
        start = (self.position - self.count) % self.capacity
        return [
            self.rows[(start + i) % self.capacity].copy() for i in range(self.count)
        ]
