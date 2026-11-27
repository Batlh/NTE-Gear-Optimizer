"""Bounded single-writer journal adapter: no filesystem work on the UI thread."""

from concurrent.futures import Future
from copy import deepcopy
from datetime import datetime, timezone
import queue
import threading
import time

from .debug_journal import DebugJournal, private_traceback


class BackgroundJournal:
    def __init__(self, directory, *, capacity=1024, store_factory=DebugJournal):
        self.directory = directory
        self.start = time.monotonic()
        self.jobs = queue.Queue(maxsize=capacity)
        self.store_factory = store_factory
        self.store = None
        self.closed = False
        self.enabled = True
        self.dropped = 0
        self.worker_error = None
        self.ready = threading.Event()
        self.thread = threading.Thread(
            target=self._run, name='NTE-debug-writer', daemon=True
        )
        self.thread.start()

    @property
    def seq(self):
        return self._request('_seq')

    @property
    def failed(self):
        return bool(
            self.worker_error
            or self.dropped
            or (self.store is not None and self.store.failed)
        )

    def _run(self):
        try:
            self.store = self.store_factory(
                self.directory, buffered=True, sync_interval=3.0
            )
        except Exception as error:
            self.worker_error = private_traceback(error)
        finally:
            self.ready.set()
        last_flush = time.monotonic()
        while True:
            try:
                job = self.jobs.get(timeout=0.1)
            except queue.Empty:
                job = None
            if job is not None:
                operation, args, kwargs, future = job
                try:
                    if operation == '_close':
                        if self.store is not None:
                            self.store.flush_inputs(force=True)
                            self.store.flush_disk(force_sync=True)
                        if future is not None:
                            future.set_result(self.store is not None)
                        return
                    if self.store is None:
                        raise RuntimeError(
                            self.worker_error or 'Journal worker unavailable'
                        )
                    if operation == '_seq':
                        value = self.store.seq
                    elif operation == '_barrier':
                        self.store.flush_disk(force_sync=True)
                        value = True
                    else:
                        if operation == 'report':
                            self.store.flush_inputs(force=True)
                            self.store.flush_disk(force_sync=True)
                        value = getattr(self.store, operation)(*args, **kwargs)
                    if future is not None:
                        future.set_result(value)
                except Exception as error:
                    self.worker_error = private_traceback(error)
                    if future is not None:
                        future.set_exception(error)
                finally:
                    self.jobs.task_done()
            now = time.monotonic()
            if now - last_flush >= 0.25 and self.store is not None:
                self.store.flush_disk()
                last_flush = now

    def _enqueue(self, store_method, *args, **kwargs):
        if self.closed:
            return False
        if not self.enabled and store_method in ('emit', 'input', 'flush_inputs'):
            return True
        try:
            self.jobs.put_nowait((store_method, deepcopy(args), deepcopy(kwargs), None))
            return True
        except queue.Full:
            self.dropped += 1
            return False
        except Exception as error:
            self.worker_error = private_traceback(error)
            return False

    def _request(self, operation, *args, **kwargs):
        if self.closed:
            raise RuntimeError('Journal is closed')
        future = Future()
        self.jobs.put((operation, args, kwargs, future), timeout=5)
        return future.result(timeout=10)

    def emit(self, event, **data):
        stamp = {
            'ms': round((time.monotonic() - self.start) * 1000),
            'utc': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
        }
        return self._enqueue('emit', event, **data, **stamp)

    def input(self, *args, **kwargs):
        return self._enqueue('input', *args, **kwargs)

    def flush_inputs(self, *args, **kwargs):
        return self._enqueue('flush_inputs', *args, **kwargs)

    def exception(self, error, *, caught):
        return self.emit(
            'exception',
            caught=caught,
            exception_type=type(error).__name__,
            stacktrace=private_traceback(error),
        )

    def events(self):
        return self._request('events')

    def report(self, device, state, **kwargs):
        state = deepcopy(state)
        state['journal_health'] = {
            'queue_dropped': self.dropped,
            'worker_error': self.worker_error,
        }
        return self._request('report', deepcopy(device), state, **kwargs)

    def clear(self, *, confirmed=False):
        if not confirmed:
            return False
        return self._request('clear', confirmed=True)

    def barrier(self):
        return self._request('_barrier')

    def close(self):
        if self.closed:
            return
        try:
            self._request('_close')
        finally:
            self.closed = True
            self.thread.join(timeout=1)

    filename = staticmethod(DebugJournal.filename)
