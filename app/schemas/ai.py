from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.ai.contracts import AICapability


class AIRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: AICapability
    prompt: str = Field(min_length=1, max_length=8000)
    patient_context_id: UUID | None = None


class AICapabilityStatus(BaseModel):
    capability: AICapability
    approved: bool
    operating_mode: str
    status: str
