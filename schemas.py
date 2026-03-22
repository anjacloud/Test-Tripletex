from typing import Any

from pydantic import BaseModel, Field


class TripletexCredentials(BaseModel):
    base_url: str
    session_token: str


class SolveFile(BaseModel):
    filename: str = "unnamed_file"
    content_base64: str = ""
    mime_type: str | None = None


class SolveRequest(BaseModel):
    prompt: str = ""
    files: list[SolveFile] = Field(default_factory=list)
    tripletex_credentials: TripletexCredentials


class SolveResult(BaseModel):
    status: str
    message: str | None = None
    debug: dict[str, Any] | None = None
