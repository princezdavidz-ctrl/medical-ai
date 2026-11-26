from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


Channel = Literal["in_app", "email", "sms", "push"]


class NotificationPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
    sms_enabled: bool | None = None
    push_enabled: bool | None = None
    locale: str | None = Field(default=None, min_length=2, max_length=12, pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    timezone_name: str | None = Field(default=None, min_length=1, max_length=64)
    quiet_start: str | None = Field(default=None, pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    quiet_end: str | None = Field(default=None, pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")

    @field_validator("quiet_end")
    @classmethod
    def paired_quiet_hours(cls, value, info):
        start = info.data.get("quiet_start")
        if (value is None) != (start is None):
            raise ValueError("quiet_hours_must_be_set_or_cleared_together")
        return value


class NotificationTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_.-]+$")
    channel: Channel
    content_classification: Literal["operational", "administrative", "sensitive"] = "operational"
    title_template: str = Field(min_length=1, max_length=160)
    body_template: str = Field(min_length=1, max_length=2000)
    allowed_placeholders: list[str] = Field(default_factory=list, max_length=20)


class NotificationTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    template_code: str
    version: int
    channel: str
    content_classification: str
    title_template: str
    body_template: str
    allowed_placeholders: list[str]
    status: str
    created_at: datetime


class NotificationTemplatePublish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve_sensitive: bool = False


class NotificationEnqueue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_id: UUID
    recipient_user_id: UUID
    patient_id: UUID | None = None
    consent_id: UUID | None = None
    purpose: str = Field(min_length=3, max_length=120)
    idempotency_key: str = Field(min_length=8, max_length=128)
    variables: dict[str, str] = Field(default_factory=dict, max_length=20)


class NotificationIntentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    template_id: UUID
    recipient_user_id: UUID
    patient_id: UUID | None
    channel: str
    purpose: str
    rendered_title: str
    rendered_body: str
    status: str
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime
    created_at: datetime
