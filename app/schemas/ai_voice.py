from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AIVoiceTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transcript: str = Field(min_length=1, max_length=3000)
    locale: str = Field(default="en", min_length=2, max_length=16, pattern=r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
    speech_input: Literal["on_device"] = Field(default="on_device", description="Client-declared mode. Backend accepts text only and cannot independently attest the device speech engine.")


class AIVoiceCitation(BaseModel):
    citation_id: str
    source_title: str
    publisher: str
    version: str
    jurisdiction: str
    reviewed_at: str
    next_review_at: str


class AIVoiceTurnResponse(BaseModel):
    transcript: str
    spoken_response: str
    locale: str
    speech_input: Literal["on_device"]
    speech_output: Literal["on_device"]
    provider: str
    model: str
    model_version: str
    prompt_version: str
    prompt_digest: str
    citations: list[AIVoiceCitation]
    audio_uploaded: Literal[False]
    conversation_persisted: Literal[False]
    clinical_use_enabled: Literal[False]
    requires_clinician_review: Literal[True]


