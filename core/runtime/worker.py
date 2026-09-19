"""Bounded acquisition/framing and analysis workers, independent of perception backend."""
from __future__ import annotations

import queue
import time
import uuid
from collections import deque
from threading import Event, Thread

from core.runtime.quality import pcm_clipped_fraction, quality_state


class AudioWorker:
    def __init__(self, *, audio_input, pipeline, session_id, on_window, on_end,
                 clock=time.monotonic, queue_capacity=2, max_age_s=2.0, pace_file=False, clock_tolerance_s=0.05):
        if queue_capacity < 1 or min(max_age_s, clock_tolerance_s) <= 0:
            raise ValueError('positive worker limits required')
        self.audio_input, self.pipeline = audio_input, pipeline
        self.session_id, self.on_window, self.on_end = session_id, on_window, on_end
        self.clock, self.max_age_s, self.pace_file = clock, max_age_s, pace_file
        self.clock_tolerance_s = clock_tolerance_s
        self._queue = queue.Queue(maxsize=queue_capacity)
        self._stop, self._finished = Event(), Event()
        self._producer = self._consumer = None
        self.error = None
        self.dropped_windows = self.stale_windows = self.processed_windows = 0
        self.max_queue_depth = self.discontinuities = 0
        self.processing_ms = deque(maxlen=2048)
        self.publication_age_s = deque(maxlen=2048)

    def start(self):
        if self._producer is not None:
            raise RuntimeError('worker_instance_cannot_restart')
        start = getattr(self.audio_input, 'start', None)
        if start:
            start()
        self._producer = Thread(target=self._acquire, name=f'audio-acquire:{self.session_id}', daemon=True)
        self._consumer = Thread(target=self._analyze, name=f'audio-analyze:{self.session_id}', daemon=True)
        self._consumer.start()
        self._producer.start()

    @staticmethod
    def _contiguous(previous, current):
        return (all(getattr(previous, key) == getattr(current, key) for key in
                    ('input_kind', 'input_asset_or_device_id', 'clock_id', 'sample_rate_hz'))
                and current.sample_start == previous.sample_end
                and abs(current.capture_end_monotonic_s - previous.capture_end_monotonic_s
                        - len(current.samples) / current.sample_rate_hz) <= 1 / current.sample_rate_hz)

    def _acquire(self):
        try:
            source = iter(self.audio_input.chunks())
            pending = next(source, None)
            while pending is not None and not self._stop.is_set():
                run_id = f'run:{uuid.uuid4().hex}'
                first, pending = pending, None
                def segment():
                    nonlocal pending
                    previous = first
                    yield first
                    for current in source:
                        if self._stop.is_set():
                            return
                        if not self._contiguous(previous, current):
                            pending = current
                            self.discontinuities += 1
                            return
                        yield current
                        previous = current
                for window in self.pipeline.windows_from_chunks(segment(), session_id=self.session_id,
                                                                 analysis_run_id=run_id):
                    if self._stop.is_set():
                        break
                    if self.pace_file and self._stop.wait(max(0, window.capture_end_monotonic_s - self.clock())):
                        break
                    # Oldest queued work is discarded; the consumer detects a skipped
                    # hop/run and explicitly gates the next publication as dropout.
                    try:
                        self._queue.put_nowait(window)
                    except queue.Full:
                        try:
                            self._queue.get_nowait()
                            self.dropped_windows += 1
                        except queue.Empty:
                            pass
                        self._queue.put_nowait(window)
                    self.max_queue_depth = max(self.max_queue_depth, self._queue.qsize())
        except Exception as exc:
            self.error = str(exc)
        finally:
            self._finished.set()
            self._close_input()

    def _analyze(self):
        previous = None
        gap = False
        dropped_seen = 0
        discontinuities_seen = 0
        input_faults_seen = 0
        try:
            while not self._stop.is_set():
                try:
                    window = self._queue.get(timeout=0.05)
                except queue.Empty:
                    if self._finished.is_set():
                        break
                    continue
                if self.error:
                    break
                age = self.clock() - window.capture_end_monotonic_s
                if age > self.max_age_s or age < -self.clock_tolerance_s:
                    self.stale_windows += 1
                    gap = True
                    continue
                input_faults = getattr(self.audio_input, "discontinuities", 0) + getattr(self.audio_input, "dropped_packets", 0)
                gap |= self.discontinuities != discontinuities_seen or input_faults != input_faults_seen
                discontinuities_seen, input_faults_seen = self.discontinuities, input_faults
                gap |= self.dropped_windows != dropped_seen
                dropped_seen = self.dropped_windows
                if previous is not None:
                    gap |= (window.analysis_run_id != previous.analysis_run_id or
                            window.sample_start != previous.sample_start + self.pipeline.hop_size_samples)
                quality = quality_state(
                    clipped_fraction=max(window.input_clipped_fraction, pcm_clipped_fraction(window.samples)),
                    dropout=gap,
                    comparability='weak' if not any(window.samples) else 'comparable')
                begin = self.clock()
                self.on_window(window, quality, self.max_age_s)
                end = self.clock()
                self.processing_ms.append(max(0, (end - begin) * 1000))
                self.publication_age_s.append(max(0, end - window.capture_end_monotonic_s))
                self.processed_windows += 1
                previous, gap = window, False
        except Exception as exc:
            self.error = str(exc)
            self._stop.set()
        finally:
            self._close_input()
            if not self._stop.is_set() or self.error:
                self.on_end(self.error or 'audio_eof')

    def _close_input(self):
        close = getattr(self.audio_input, 'close', None)
        if close:
            try:
                close()
            except Exception as exc:
                # A driver teardown error must not skip joins or the terminal
                # session notification. Preserve the original capture failure.
                self.error = self.error or f'capture_close_failed:{exc}'

    def stop(self, timeout_s=5.0):
        self._stop.set()
        self._close_input()
        deadline = time.monotonic() + timeout_s
        for thread in (self._producer, self._consumer):
            if thread is not None:
                thread.join(max(0, deadline - time.monotonic()))
        if any(thread and thread.is_alive() for thread in (self._producer, self._consumer)):
            raise RuntimeError('audio_worker_shutdown_timeout')

    def metrics(self):
        def percentile(values, fraction):
            ordered = sorted(values)
            return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))] if ordered else None
        return dict(processed_windows=self.processed_windows, dropped_windows=self.dropped_windows,
                    stale_windows=self.stale_windows, discontinuities=self.discontinuities,
                    queue_depth=self._queue.qsize(), max_queue_depth=self.max_queue_depth,
                    processing_p50_ms=percentile(self.processing_ms, .5),
                    processing_p95_ms=percentile(self.processing_ms, .95),
                    publication_age_p95_s=percentile(self.publication_age_s, .95), error=self.error)
