from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AIOperationsInsightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_run_id: UUID
    question: str = Field(min_length=5, max_length=1200)


