import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from agent import TripletexAgent
from schemas import SolveRequest, SolveResult

app = FastAPI()
logger = logging.getLogger(__name__)


def _summarize_http_request(
    request: Request,
    payload: dict[str, Any] | None = None,
    raw_body: bytes | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    expected_keys = {"prompt", "files", "tripletex_credentials"}
    files = payload.get("files")
    credentials = payload.get("tripletex_credentials")
    prompt = payload.get("prompt")

    return {
        "method": request.method,
        "path": request.url.path,
        "content_type": request.headers.get("content-type"),
        "user_agent": request.headers.get("user-agent"),
        "body_bytes": len(raw_body or b""),
        "top_level_keys": sorted(payload.keys()),
        "unexpected_top_level_keys": sorted(set(payload.keys()) - expected_keys),
        "has_prompt": isinstance(prompt, str) and bool(prompt.strip()),
        "prompt_length": len(prompt) if isinstance(prompt, str) else None,
        "prompt_preview": prompt[:200] if isinstance(prompt, str) else None,
        "files_count": len(files) if isinstance(files, list) else None,
        "files": [
            {
                "filename": file_obj.get("filename"),
                "mime_type": file_obj.get("mime_type"),
                "content_base64_length": len(file_obj.get("content_base64", "") or ""),
            }
            for file_obj in files
            if isinstance(file_obj, dict)
        ]
        if isinstance(files, list)
        else None,
        "has_tripletex_credentials": isinstance(credentials, dict),
        "tripletex_base_url": credentials.get("base_url")
        if isinstance(credentials, dict)
        else None,
        "session_token_length": len(credentials.get("session_token", "") or "")
        if isinstance(credentials, dict)
        else None,
    }


async def _handle_solve_request(request: Request) -> JSONResponse:
    raw_body = await request.body()

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    request_summary = _summarize_http_request(request, payload, raw_body)
    logger.info("Incoming request summary: %s", request_summary)

    try:
        solve_request = SolveRequest.model_validate(payload)
    except ValidationError as exc:
        logger.warning("SolveRequest validation failed: %s", exc.errors())
        return JSONResponse(
            status_code=400,
            content=SolveResult(
                status="error",
                message="Invalid request payload",
                debug={
                    "request_summary": request_summary,
                    "validation_errors": exc.errors(),
                },
            ).model_dump(exclude_none=True),
        )

    try:
        agent = TripletexAgent(
            base_url=solve_request.tripletex_credentials.base_url,
            session_token=solve_request.tripletex_credentials.session_token,
        )
        result = await agent.solve(solve_request)
        debug = {
            "request_summary": request_summary,
            **(result.get("debug") or {}),
        }
        logger.info(
            "Solve classified request as task_type=%s unsupported=%s",
            debug.get("task_type"),
            debug.get("unsupported"),
        )

        return JSONResponse(
            status_code=200,
            content=SolveResult(
                status="completed",
                message=result.get("message"),
                debug=debug,
            ).model_dump(exclude_none=True),
        )

    except Exception as exc:
        logger.exception("Unhandled solve failure")
        return JSONResponse(
            status_code=500,
            content=SolveResult(
                status="error",
                message=str(exc),
                debug={"request_summary": request_summary},
            ).model_dump(exclude_none=True),
        )


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/")
async def solve_root(request: Request) -> JSONResponse:
    return await _handle_solve_request(request)


@app.post("/solve")
async def solve(request: Request) -> JSONResponse:
    return await _handle_solve_request(request)
