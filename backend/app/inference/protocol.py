from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class CompletionRequest(BaseModel):
    role: str
    prompt: str
    schema_name: str | None = None
    max_tokens: int | None = None
    prompt_version: str
    project_id: str | None = None
    workflow_id: str | None = None
    agent: str


class CompletionResult(BaseModel):
    text: str
    parsed: dict[str, Any] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str
    provider: str


class ChatProvider(ABC):
    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResult: ...


class TTSRequest(BaseModel):
    text: str
    voice: str
    speed: float = Field(ge=0.5, le=2)
    output_path: str


class TTSResult(BaseModel):
    duration_seconds: float
    sha256: str
    path: str


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResult: ...


class AlignmentResult(BaseModel):
    segments: list[dict]


class AlignmentProvider(ABC):
    @abstractmethod
    async def align(self, audio_path: str) -> AlignmentResult: ...
