"""Loopback-only Starlette adapter for the frozen PA setup/session contracts."""

from __future__ import annotations

import asyncio
import os
import tempfile
from contextlib import asynccontextmanager
from json import JSONDecodeError
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from core.contracts.validation import SETUP, validate_record

from .service import APIError, RuntimeAPI


DEFAULT_ORIGINS = {
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://testserver",
}


def _setup_error(status: int, code: str, message: str, *, retryable: bool = False) -> JSONResponse:
    payload = {"error": {"code": code, "message": message, "retryable": retryable}}
    validate_record(payload, SETUP, "SetupError")
    return JSONResponse(payload, status_code=status)


def _api(request_or_socket):
    return request_or_socket.app.state.runtime_api


def _origin_allowed(request_or_socket) -> bool:
    origin = request_or_socket.headers.get("origin")
    return origin is None or origin in request_or_socket.app.state.allowed_origins


async def _json_body(request: Request) -> dict:
    try:
        value = await request.json()
    except (JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise APIError(422, "malformed_json", "Request body must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise APIError(422, "invalid_json_object", "Request body must be a JSON object.")
    return value


async def _call(request: Request, operation):
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and not _origin_allowed(request):
        return _setup_error(403, "origin_forbidden", "Browser origin is not allowed.")
    try:
        status, payload = await operation()
        return JSONResponse(payload, status_code=status)
    except APIError as exc:
        return _setup_error(exc.status, exc.code, str(exc))
    except Exception:
        return _setup_error(503, "runtime_failure", "Runtime operation failed.", retryable=True)


async def health(request: Request):
    return await _call(request, lambda: asyncio.to_thread(_api(request).health))


async def audio_devices(request: Request):
    return await _call(request, lambda: asyncio.to_thread(_api(request).audio_devices))


async def create_project(request: Request):
    async def operation():
        body = await _json_body(request)
        return await asyncio.to_thread(_api(request).create_project, body)
    return await _call(request, operation)


async def create_song(request: Request):
    async def operation():
        body = await _json_body(request)
        return await asyncio.to_thread(_api(request).create_song, body)
    return await _call(request, operation)


async def upload_audio(request: Request):
    async def operation():
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type not in ("audio/wav", "audio/x-wav", "audio/wave"):
            raise APIError(415, "unsupported_media_type", "Audio upload must use Content-Type audio/wav.")
        length = request.headers.get("content-length")
        if length is not None:
            try:
                if int(length) > _api(request).max_upload_bytes:
                    raise APIError(413, "audio_too_large", "Audio upload exceeds the byte limit.")
            except ValueError as exc:
                raise APIError(422, "invalid_content_length", "Content-Length is invalid.") from exc
        content = bytearray()
        async for chunk in request.stream():
            if len(content) + len(chunk) > _api(request).max_upload_bytes:
                raise APIError(413, "audio_too_large", "Audio upload exceeds the byte limit.")
            content.extend(chunk)
        filename = request.headers.get("x-audio-filename", "uploaded.wav")
        return await asyncio.to_thread(
            _api(request).upload_audio, bytes(content), filename=filename
        )
    return await _call(request, operation)


async def start_reference(request: Request):
    async def operation():
        body = await _json_body(request)
        status, job = await asyncio.to_thread(
            _api(request).start_reference_job, request.path_params["song_id"], body
        )
        task = asyncio.create_task(asyncio.to_thread(_api(request).run_reference_job, job["job_id"]))
        request.app.state.background_tasks.add(task)
        task.add_done_callback(request.app.state.background_tasks.discard)
        return status, job
    return await _call(request, operation)


async def get_job(request: Request):
    return await _call(
        request, lambda: asyncio.to_thread(_api(request).get_job, request.path_params["job_id"])
    )


async def create_session(request: Request):
    async def operation():
        body = await _json_body(request)
        return await asyncio.to_thread(_api(request).create_session, body)
    return await _call(request, operation)


async def get_session(request: Request):
    return await _call(
        request, lambda: asyncio.to_thread(_api(request).get_session, request.path_params["session_id"])
    )


async def post_action(request: Request):
    async def operation():
        body = await _json_body(request)
        if body.get("action") == "accept_baseline":
            raise APIError(422, "wrong_endpoint", "accept_baseline must use the baseline endpoint.")
        return await asyncio.to_thread(
            _api(request).post_action, request.path_params["session_id"], body
        )
    return await _call(request, operation)


async def accept_baseline(request: Request):
    async def operation():
        body = await _json_body(request)
        return await asyncio.to_thread(
            _api(request).accept_baseline, request.path_params["session_id"], body
        )
    return await _call(request, operation)


async def session_events(websocket: WebSocket):
    if not _origin_allowed(websocket):
        await websocket.close(code=4403, reason="origin_forbidden")
        return
    session_id = websocket.path_params["session_id"]
    try:
        _, snapshot = _api(websocket).get_session(session_id)
    except APIError:
        await websocket.close(code=4404, reason="unknown_session")
        return
    raw_cursor = websocket.query_params.get("after_sequence")
    if raw_cursor is None:
        await websocket.close(code=4400, reason="after_sequence_required")
        return
    try:
        cursor = int(raw_cursor)
    except ValueError:
        await websocket.close(code=4400, reason="invalid_cursor")
        return
    if cursor < 0 or cursor > snapshot["event_sequence"]:
        await websocket.close(code=4409, reason="stale_or_future_cursor")
        return
    await websocket.accept()
    try:
        while True:
            _, batch = _api(websocket).connect_events(session_id, after_sequence=cursor)
            for event in batch["events"]:
                await websocket.send_json(event)
                cursor = event["event_sequence"]
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=0.05)
            except TimeoutError:
                continue
            if message["type"] == "websocket.disconnect":
                return
    except WebSocketDisconnect:
        return


ROUTES = [
    Route("/v1/health", health, methods=["GET"]),
    Route("/v1/audio-devices", audio_devices, methods=["GET"]),
    Route("/v1/projects", create_project, methods=["POST"]),
    Route("/v1/songs", create_song, methods=["POST"]),
    Route("/v1/audio-assets", upload_audio, methods=["POST"]),
    Route("/v1/songs/{song_id:str}/reference", start_reference, methods=["POST"]),
    Route("/v1/jobs/{job_id:str}", get_job, methods=["GET"]),
    Route("/v1/sessions", create_session, methods=["POST"]),
    Route("/v1/sessions/{session_id:str}", get_session, methods=["GET"]),
    Route("/v1/sessions/{session_id:str}/actions", post_action, methods=["POST"]),
    Route("/v1/sessions/{session_id:str}/baseline", accept_baseline, methods=["POST"]),
    WebSocketRoute("/v1/sessions/{session_id:str}/events", session_events),
]


def create_app(
    runtime_api: RuntimeAPI | None = None,
    *,
    ui_directory: str | Path | None = None,
) -> Starlette:
    @asynccontextmanager
    async def lifespan(application):
        if runtime_api is not None:
            application.state.runtime_api = runtime_api
        else:
            storage = Path(
                os.environ.get(
                    "PA_RUNTIME_STORAGE_DIR",
                    str(Path(tempfile.gettempdir()) / "pa-controller-runtime"),
                )
            )
            devices = {
                value.strip()
                for value in os.environ.get("PA_AUDIO_DEVICE_IDS", "").split(",")
                if value.strip()
            }
            application.state.runtime_api = RuntimeAPI(
                storage_dir=storage,
                window_size_samples=int(os.environ.get("PA_WINDOW_SIZE_SAMPLES", "192000")),
                hop_size_samples=int(os.environ.get("PA_HOP_SIZE_SAMPLES", "48000")),
                available_audio_devices=devices,
            )
        origins = os.environ.get("PA_ALLOWED_ORIGINS")
        application.state.allowed_origins = (
            {value.strip() for value in origins.split(",") if value.strip()}
            if origins
            else set(DEFAULT_ORIGINS)
        )
        application.state.background_tasks = set()
        yield
        if application.state.background_tasks:
            await asyncio.gather(*application.state.background_tasks, return_exceptions=True)

    selected_ui = (
        Path(ui_directory)
        if ui_directory is not None
        else Path(__file__).resolve().parents[1] / "ui"
    )
    routes = list(ROUTES)
    if selected_ui.is_dir():
        routes.append(
            Mount(
                "/apps/ui",
                app=StaticFiles(directory=selected_ui, html=True),
                name="ui",
            )
        )
    application = Starlette(routes=routes, lifespan=lifespan)
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )
    return application


app = create_app()
