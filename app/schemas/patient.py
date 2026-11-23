from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class PatientCreate(BaseModel):
    medical_record_number: str = Field(min_length=1, max_length=80)
    given_name: str = Field(min_length=1, max_length=120)
    family_name: str = Field(min_length=1, max_length=120)
    date_of_birth: date | None = None
    administrative_sex: str | None = Field(default=None, max_length=24)
    phone_number: str | None = Field(default=None, max_length=40)

class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    medical_record_number: str
    given_name: str
    family_name: str
    date_of_birth: date | None
    administrative_sex: str | None
    status: str
    created_at: datetime
