from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class AIPatientAssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: UUID
    question: str = Field(min_length=1, max_length=4000)


