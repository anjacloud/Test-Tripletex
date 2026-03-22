from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agent import TripletexAgent
from schemas import SolveRequest, SolveResult

app = FastAPI()


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def _handle_solve(request: SolveRequest) -> JSONResponse:
    try:
        agent = TripletexAgent(
            base_url=request.tripletex_credentials.base_url,
            session_token=request.tripletex_credentials.session_token,
        )
        result = await agent.solve(request)

        return JSONResponse(
            status_code=200,
            content=SolveResult(
                status="completed",
                message=result.get("message"),
                debug=result.get("debug"),
            ).model_dump(exclude_none=True),
        )

    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content=SolveResult(
                status="error",
                message=str(exc),
            ).model_dump(exclude_none=True),
        )


@app.post("/")
async def solve_root(request: SolveRequest) -> JSONResponse:
    return await _handle_solve(request)


@app.post("/solve")
async def solve(request: SolveRequest) -> JSONResponse:
    return await _handle_solve(request)

