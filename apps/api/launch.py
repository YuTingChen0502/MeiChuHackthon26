"""Explicit local host launcher; adapter imports are host CLI choices, never manifest code."""
import argparse
import importlib
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("bundle", "fake", "candidate-p1"), default="bundle")
    parser.add_argument("--bundle")
    parser.add_argument("--host-review")
    parser.add_argument("--storage", required=True)
    parser.add_argument("--adapter", action="append", default=[], metavar="ID=MODULE:FACTORY")
    parser.add_argument("--rate", type=int)
    parser.add_argument("--window", type=int)
    parser.add_argument("--hop", type=int)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    bundle_loader = None
    if args.mode == "candidate-p1":
        if args.host_review or args.adapter:
            parser.error("candidate-p1 cannot use production acceptance or registry adapters")
        geometry = (44100, 176400, 44100)
        if any(value is not None and value != expected for value, expected in
               zip((args.rate, args.window, args.hop), geometry)):
            parser.error("candidate-p1 requires its frozen 44100 Hz / 4-second / 1-second profile")
        from analyzers.separation.p1_candidate import make_p1_candidate_loader
        bundle_loader = make_p1_candidate_loader(
            cache_dir=Path(args.storage) / "context-cache", candidate_mode=True, device="cpu")
    else:
        geometry = (48000, 192000, 48000)
    args.rate, args.window, args.hop = tuple(
        expected if value is None else value for value, expected in
        zip((args.rate, args.window, args.hop), geometry))
    registry = {}
    for value in args.adapter:
        identity, location = value.split("=", 1)
        module, name = location.split(":", 1)
        if identity in registry:
            parser.error("duplicate adapter ID")
        registry[identity] = getattr(importlib.import_module(module), name)
    os.environ.update(PA_ANALYZER_MODE="bundle" if args.mode == "candidate-p1" else args.mode, PA_RUNTIME_STORAGE_DIR=args.storage,
        PA_ANALYSIS_RATE_HZ=str(args.rate), PA_WINDOW_SIZE_SAMPLES=str(args.window), PA_HOP_SIZE_SAMPLES=str(args.hop),
        PA_ANALYSIS_TIMING_PROFILE="candidate_delayed_v1" if args.mode == "candidate-p1" else "strict_v1")
    for key, value in (("PA_MODEL_BUNDLE", args.bundle), ("PA_HOST_REVIEW", args.host_review)):
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)
    os.environ.setdefault("PA_ALLOWED_ORIGINS",
        f"http://127.0.0.1:{args.port},http://localhost:{args.port}")
    import uvicorn
    from .transport import create_app
    uvicorn.run(create_app(bundle_registry=registry, bundle_loader=bundle_loader), host="127.0.0.1", port=args.port,
                workers=1, loop="asyncio", http="h11", ws="websockets-sansio")


if __name__ == "__main__":
    main()
