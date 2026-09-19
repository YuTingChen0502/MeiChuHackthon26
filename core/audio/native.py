"""Optional PortAudio adapter. Callback work is limited to copying and enqueueing PCM.

The native backend is deliberately lazy: file streaming does not need sounddevice.
Discovery proves input capability, not physical microphone identity or disabled AGC.
"""
from __future__ import annotations

import hashlib
import math
import queue
import struct
import time
from dataclasses import dataclass
from threading import Event

from .types import AudioChunk


@dataclass(frozen=True)
class NativeDevice:
    device_id: str
    index: int
    name: str
    host_api: str
    max_channels: int
    default_sample_rate_hz: int
    is_default: bool | None = None


class SoundDeviceBackend:
    def __init__(self, module=None):
        if module is None:
            import sounddevice as module
        self.module = module

    def discover(self):
        hosts = self.module.query_hostapis()
        devices = []
        inventory = list(self.module.query_devices())
        # PortAudio descriptors expose no cross-host physical endpoint identity.
        # Keep host-specific entries; equal display names do not prove one device.
        default_index = None
        try:
            selected = self.module.default.device[0]
            if (type(selected) is int and 0 <= selected < len(inventory)
                    and inventory[selected]["max_input_channels"] > 0):
                default_index = selected
        except Exception:
            # Missing optional default metadata must not disable discovery.
            pass
        identities = [(hosts[item["hostapi"]]["name"], item["name"]) for item in inventory if item["max_input_channels"] > 0]
        for index, item in enumerate(inventory):
            if item['max_input_channels'] < 1:
                continue
            name = item['name']
            # Do not advertise known system loopback sources as microphones.
            if any(term in name.lower() for term in ('loopback', 'stereo mix', 'stereo input', 'what u hear', 'monitor of', 'speaker', '喇叭', '立體聲混音')):
                continue
            host = hosts[item['hostapi']]['name']
            # Withhold ambiguous devices; indices are not stable identities.
            if identities.count((host, name)) != 1:
                continue
            digest = hashlib.sha256(f'{host}\0{name}'.encode()).hexdigest()[:20]
            devices.append(NativeDevice(f'portaudio:{digest}', index, name, host,
                                       item['max_input_channels'], int(item['default_samplerate']),
                                       None if default_index is None else index == default_index))
        return devices

    def negotiate(self, *, device_id, sample_rate_hz):
        device = next((item for item in self.discover() if item.device_id == device_id), None)
        if device is None:
            raise RuntimeError("native_device_unavailable")
        for rate in dict.fromkeys((sample_rate_hz, device.default_sample_rate_hz)):
            for channels in dict.fromkeys((1, min(2, device.max_channels))):
                try:
                    self.module.check_input_settings(device=device.index, channels=channels, dtype="float32", samplerate=rate)
                    return {"sample_rate_hz":rate, "channels":channels}
                except Exception:
                    continue
        raise RuntimeError("native_capture_format_unavailable")

    def open(self, *, device_id, sample_rate_hz, block_size, callback, channels=1):
        # Resolve again so a cached index cannot silently select a different device.
        device = next((item for item in self.discover() if item.device_id == device_id), None)
        if device is None:
            raise RuntimeError('native_device_unavailable')
        self.module.check_input_settings(device=device.index, channels=channels,
                                         dtype='float32', samplerate=sample_rate_hz)
        return self.module.RawInputStream(device=device.index, channels=channels, dtype='float32',
                                           samplerate=sample_rate_hz, blocksize=block_size,
                                           callback=callback, clip_off=True, dither_off=True)


class NativeMicAudioInput:
    """One mono stream, with bounded callback packets and explicit discontinuities.

    Sample positions include packets dropped by queue backpressure. Hardware overflow
    or ADC clock jumps skip one position (unknown missing duration) and reanchor time;
    that marker is never synthesized as silence or sent across an analysis window.
    """
    def __init__(self, *, backend, device_id, clock_id, sample_rate_hz,
                 block_size=1024, queue_capacity=8, clock=time.monotonic, timeout_s=2.0, clock_tolerance_s=0.05, channels=1):
        if min(sample_rate_hz, block_size, queue_capacity, channels) <= 0 or min(timeout_s, clock_tolerance_s) <= 0:
            raise ValueError('positive capture settings required')
        self.backend, self.device_id, self.clock_id = backend, device_id, clock_id
        self.sample_rate_hz, self.block_size = sample_rate_hz, block_size
        self.channels = channels
        self.clock, self.timeout_s = clock, timeout_s
        self.clock_tolerance_s = clock_tolerance_s
        self.max_adc_residual_s = 0.0
        self._queue = queue.Queue(maxsize=queue_capacity)
        self._stop = Event()
        self._stream = None
        self._next_sample = 0
        self._origin = None
        self._adc_origin = None
        self.dropped_packets = 0
        self.discontinuities = 0
        self.max_queue_depth = 0
        self.error = None

    def _callback(self, data, frames, timing, status):
        if self._stop.is_set():
            return
        try:
            now = self.clock()
            if frames <= 0 or frames > self.block_size or len(data) != frames * 4 * self.channels:
                raise ValueError('invalid_native_packet')
            adc = float(timing.inputBufferAdcTime)
            current = float(timing.currentTime)
            if not all(math.isfinite(value) for value in (adc, current, now)) or adc <= 0:
                raise ValueError('native_adc_clock_unavailable')
            measured_start = now + adc - current
            expected_adc = None if self._adc_origin is None else self._adc_origin + self._next_sample / self.sample_rate_hz
            residual = 0.0 if expected_adc is None else abs(adc - expected_adc)
            self.max_adc_residual_s = max(self.max_adc_residual_s, residual)
            # WASAPI/PortAudio callback ADC timestamps can have millisecond jitter.
            # Sample counts own the timeline; status flags always break continuity,
            # while gross ADC drift/restart exceeds the declared 50 ms clock budget.
            gap = bool(status) or residual > self.clock_tolerance_s
            if gap:
                self._next_sample += 1
                self._origin = self._adc_origin = None
                self.discontinuities += 1
            if self._origin is None:
                self._origin = measured_start - self._next_sample / self.sample_rate_hz
                self._adc_origin = adc - self._next_sample / self.sample_rate_hz
            start = self._next_sample
            self._next_sample += frames
            packet = (start, self._origin + self._next_sample / self.sample_rate_hz, bytes(data))
            try:
                self._queue.put_nowait(packet)
                self.max_queue_depth = max(self.max_queue_depth, self._queue.qsize())
            except queue.Full:
                self.dropped_packets += 1
        except Exception as exc:
            self.error = str(exc)
            self._stop.set()

    def start(self):
        if self._stream is not None or self._stop.is_set():
            raise RuntimeError('capture_instance_cannot_restart')
        options = {"channels": self.channels} if self.channels != 1 else {}
        stream = self.backend.open(device_id=self.device_id, sample_rate_hz=self.sample_rate_hz,
                                   block_size=self.block_size, callback=self._callback, **options)
        self._stream = stream
        try:
            stream.start()
        except Exception:
            stream.close()
            self._stream = None
            raise

    def chunks(self):
        last_packet = self.clock()
        while not self._stop.is_set():
            try:
                start, end, raw = self._queue.get(timeout=0.05)
            except queue.Empty:
                if self.clock() - last_packet > self.timeout_s:
                    raise RuntimeError('capture_dropout_timeout')
                continue
            last_packet = self.clock()
            samples = struct.unpack(f'={len(raw) // 4}f', raw)
            clipping = sum(abs(x) >= 32767/32768 for x in samples)/len(samples)
            if self.channels > 1:
                samples = tuple(sum(samples[i:i+self.channels])/self.channels for i in range(0,len(samples),self.channels))
            yield AudioChunk('live_microphone', self.device_id, self.clock_id,
                             self.sample_rate_hz, start, end, samples, clipping)
        if self.error:
            raise RuntimeError(self.error)

    def close(self):
        self._stop.set()
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.abort()
            finally:
                stream.close()
