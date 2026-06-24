from pydantic import BaseModel, Field, model_validator
from uuid import UUID
from datetime import datetime
from models import RunStatus
from typing import Optional, Any
from configs.verticals import VALID_VERTICALS, VERTICALS

class CreateRunRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    format: str = Field(..., pattern="^(report|linkedin|summary)$")
    doc_ids: list[str] = Field(default_factory=list)
    workspace_id: Optional[UUID] = None
    vertical: Optional[str] = None
    vertical_inputs: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_vertical(self) -> "CreateRunRequest":
        if self.vertical is not None:
            if self.vertical not in VALID_VERTICALS:
                raise ValueError(
                    f"Unknown vertical '{self.vertical}'. "
                    f"Valid options: {VALID_VERTICALS}"
                )
            vertical_config = VERTICALS[self.vertical]
            schema = vertical_config.get("input_schema", {})
            for key, field_def in schema.items():
                if field_def.get("required"):
                    val = self.vertical_inputs.get(key)
                    if not val or not str(val).strip():
                        raise ValueError(f"Missing required vertical input: '{key}'")
        return self

class HitlApproveRequest(BaseModel):
    instruction: Optional[str] = None

class RunResponse(BaseModel):
    id: UUID
    topic: str
    format: str
    status: RunStatus
    workspace_id: Optional[UUID]
    vertical: Optional[str] = None
    vertical_inputs: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class RunDetailResponse(RunResponse):
    updated_at: datetime
    logs: list[dict]
    research_output: Optional[str]
    analysis_output: Optional[str]
    final_output: Optional[str]
    error_message: Optional[str]
