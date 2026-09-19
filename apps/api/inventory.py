"""Read-only local inventory. Queries devices but never opens a microphone."""
import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
from dataclasses import asdict


def inventory():
    result = {"platform":platform.platform(), "machine":platform.machine(), "python":platform.python_version(),
              "processor":platform.processor(), "logical_cpus":os.cpu_count(),
              "scope":"local inventory only; no inference provider or PN54 capability claim"}
    result["packages"] = {}
    for name in ("sounddevice", "onnxruntime", "onnxruntime-directml", "torch"):
        try:
            result["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][name] = None
    try:
        from core.audio.native import SoundDeviceBackend
        result["microphones"] = [asdict(item) for item in SoundDeviceBackend().discover()]
    except Exception as exc:
        result["microphones"] = []
        result["microphone_discovery_error"] = str(exc)
    if os.name == "nt":
        command = "Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,TotalPhysicalMemory | ConvertTo-Json -Compress"
        try:
            result["system"] = json.loads(subprocess.check_output(["powershell", "-NoProfile", "-Command", command], timeout=15, text=True))
        except Exception as exc:
            result["system_error"] = str(exc)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(inventory(), indent=2))
