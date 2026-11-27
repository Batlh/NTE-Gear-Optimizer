"""Observational timings; no scheduling, calculation or focus decisions."""

from functools import wraps
import time


class PerformanceTrace:
    def __init__(self, emit, clock=time.perf_counter):
        self.emit = emit
        self.clock = clock
        self.active = {}
        self.counter = 0
        self.frames = []
        self.touches = {}
        self.feedback_touches = {}
        self.action_touches = {}

    def start(self, operation, **context):
        self.counter += 1
        token = self.counter
        self.active[token] = (operation, self.clock(), context)
        return token

    def record(self, operation, started, *, endpoint='function_return', **context):
        duration = max(0, (self.clock() - started) * 1000)
        try:
            self.emit(
                'performance',
                operation=operation,
                duration_ms=round(duration, 3),
                over_100_ms=duration > 100,
                endpoint=endpoint,
                **context,
            )
        except Exception:
            pass

    def finish(self, token, *, failed=False, frame=False):
        if token is None or token not in self.active:
            return
        operation, started, context = self.active.pop(token)
        self.record(operation, started, failed=failed, **context)
        if frame and not failed:
            self.frames.append((operation + '_first_frame', started, context))
            self.frames = self.frames[-32:]

    def touch_begin(self, identifier):
        self.touches[str(identifier)] = self.clock()
        self.feedback_touches[str(identifier)] = self.touches[str(identifier)]
        self.action_touches[str(identifier)] = self.touches[str(identifier)]
        for values in (self.feedback_touches, self.action_touches):
            while len(values) > 32:
                values.pop(next(iter(values)))
        if len(self.touches) > 32:
            self.touches.pop(next(iter(self.touches)))

    def queue_touch_phase(self, values, operation, reaction, identifier):
        started = values.pop(str(identifier), None)
        if started is None or self.clock() - started > 5:
            return
        self.frames.append(
            (
                operation,
                started,
                {
                    'touch_id': str(identifier),
                    'reaction': reaction,
                    'scope': 'App event delivery to GL flip proxy; not physical display latency.',
                },
            )
        )
        self.frames = self.frames[-32:]

    def feedback(self, reaction, identifier):
        self.queue_touch_phase(
            self.feedback_touches, 'touch_to_feedback_frame', reaction, identifier
        )

    def action_response(self, identifier):
        self.queue_touch_phase(
            self.action_touches,
            'touch_to_action_frame',
            'action_callback_returned',
            identifier,
        )

    def response(self, reaction, identifier=None):
        if not self.touches:
            return
        inferred = identifier is None
        identifier = (
            str(identifier) if identifier is not None else next(reversed(self.touches))
        )
        started = self.touches.pop(identifier, None)
        if started is None or self.clock() - started > 5:
            return
        self.frames.append(
            (
                'touch_to_response_frame',
                started,
                {
                    'touch_id': identifier,
                    'touch_link': 'latest_pending_touch_inferred'
                    if inferred
                    else 'explicit_touch_id',
                    'reaction': reaction,
                    'startpoint': 'Window.on_motion begin',
                    'scope': 'first GL surface flip after observed UI response; not physical display latency',
                },
            )
        )
        self.frames = self.frames[-32:]

    def frame(self, *args):
        # Window.on_flip is a buffer-flip proxy, not proof of physical
        # presentation or Android's external chooser being drawn.
        pending, self.frames = self.frames, []
        for operation, started, context in pending:
            self.record(operation, started, endpoint='Window.on_flip_proxy', **context)

    def in_progress(self):
        return [
            {
                'operation': operation,
                'elapsed_ms': round((self.clock() - started) * 1000, 3),
                'complete': False,
                **context,
            }
            for operation, started, context in self.active.values()
        ]


def timed(operation, *, frame=False):
    def decorate(function):
        @wraps(function)
        def measured(self, *args, **kwargs):
            performance = getattr(self, 'performance', None)
            if performance is None:
                performance = getattr(getattr(self, 'debug', None), 'performance', None)
            token = None
            try:
                context = {}
                vm = getattr(self, 'vm', self)
                if hasattr(vm, 'step'):
                    context['step'] = vm.step + 1
                if args and operation.startswith('selector'):
                    context['selector'] = str(args[0])
                if args and operation == 'export':
                    context['mode'] = str(args[0])
                if performance is not None:
                    token = performance.start(operation, **context)
            except Exception:
                pass
            failed = True
            try:
                result = function(self, *args, **kwargs)
                failed = False
                return result
            finally:
                if performance is not None:
                    try:
                        performance.finish(token, failed=failed, frame=frame)
                    except Exception:
                        pass

        return measured

    return decorate
