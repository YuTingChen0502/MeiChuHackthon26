"""Native continuity probe; retains timing/quality/RSS metadata, never audio samples."""
import argparse
import json
import platform
import subprocess
import threading
import time
from pathlib import Path

from core.audio import SharedAudioPipeline
from core.audio.native import NativeMicAudioInput, SoundDeviceBackend
from core.runtime.worker import AudioWorker
from tests.runtime.sustained_probe import memory_bytes


def run(device_id, seconds, output):
    backend = SoundDeviceBackend()
    source = NativeMicAudioInput(backend=backend, device_id=device_id,
                                clock_id='native-continuity', sample_rate_hz=48000)
    frames = []
    done = threading.Event()
    started = time.monotonic()
    def observe(window, quality, max_age):
        frames.append(dict(run=window.analysis_run_id, sample_start=window.sample_start,
            sample_end=window.sample_end, capture_end=window.capture_end_monotonic_s,
            dropout=quality['dropout'], clipped_fraction=quality['clipped_fraction'],
            rss_bytes=memory_bytes()))
    worker = AudioWorker(audio_input=source,
        pipeline=SharedAudioPipeline(window_size_samples=192000, hop_size_samples=48000),
        session_id='native-continuity', on_window=observe, on_end=lambda reason: done.set())
    worker.start()
    try:
        done.wait(seconds)
    finally:
        worker.stop()
    manifest = dict(git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        git_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()),
        python=platform.python_version(), platform=platform.platform(), sounddevice=backend.module.__version__,
        duration_s=time.monotonic()-started, labels=None, perception='none; native continuity only',
        recording='No PCM saved', source_id=source.device_id, sample_rate_hz=48000,
        window_samples=192000, hop_samples=48000, block_samples=1024,
        clock_tolerance_s=source.clock_tolerance_s, max_adc_residual_s=source.max_adc_residual_s,
        callback_drops=source.dropped_packets, callback_discontinuities=source.discontinuities,
        callback_max_queue=source.max_queue_depth, worker_metrics=worker.metrics(), frames=frames)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in manifest.items() if key != 'frames'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--device-id', required=True)
    parser.add_argument('--seconds', type=float, default=120)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.device_id, args.seconds, args.output)
