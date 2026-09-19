"""Explicit local host launcher; adapter imports are host CLI choices, never manifest code."""
import argparse
import importlib
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("bundle", "fake"), default="bundle")
    parser.add_argument("--bundle")
    parser.add_argument("--host-review")
    parser.add_argument("--storage", required=True)
    parser.add_argument("--adapter", action="append", default=[], metavar="ID=MODULE:FACTORY")
    parser.add_argument("--rate", type=int, default=48000)
    parser.add_argument("--window", type=int, default=192000)
    parser.add_argument("--hop", type=int, default=48000)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    registry = {}
    for value in args.adapter:
        identity, location = value.split("=", 1)
        module, name = location.split(":", 1)
        if identity in registry:
            parser.error("duplicate adapter ID")
        registry[identity] = getattr(importlib.import_module(module), name)
    os.environ.update(PA_ANALYZER_MODE=args.mode, PA_RUNTIME_STORAGE_DIR=args.storage,
        PA_ANALYSIS_RATE_HZ=str(args.rate), PA_WINDOW_SIZE_SAMPLES=str(args.window), PA_HOP_SIZE_SAMPLES=str(args.hop))
    for key, value in (("PA_MODEL_BUNDLE", args.bundle), ("PA_HOST_REVIEW", args.host_review)):
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)
    import uvicorn
    from .transport import create_app
    uvicorn.run(create_app(bundle_registry=registry), host="127.0.0.1", port=args.port,
                workers=1, loop="asyncio", http="h11", ws="websockets-sansio")


if __name__ == "__main__":
    main()
