from pydantic import BaseModel, Field, model_validator
from uuid import UUID
from datetime import datetime
from urllib.parse import urlparse
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
                val = self.vertical_inputs.get(key)
                if field_def.get("required") and (not val or not str(val).strip()):
                    raise ValueError(f"Missing required vertical input: '{key}'")
                if val is None or not str(val).strip():
                    continue
                field_type = field_def.get("type")
                if field_type == "url":
                    parsed = urlparse(str(val))
                    if parsed.scheme not in ("http", "https") or not parsed.netloc:
                        raise ValueError(
                            f"Invalid vertical input '{key}': must be a valid http(s) URL"
                        )
                elif field_type == "select":
                    options = field_def.get("options", [])
                    if val not in options:
                        raise ValueError(
                            f"Invalid vertical input '{key}': must be one of {options}"
                        )
        return self

class HitlApproveRequest(BaseModel):
    instruction: Optional[str] = None

class RunResponse(BaseModel):
    id: UUID
    topic: str
    format: str
    status: RunStatus
    failed_at_status: Optional[RunStatus] = None
    workspace_id: Optional[UUID]
    vertical: Optional[str] = None
    vertical_inputs: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class RunCostResponse(BaseModel):
    id: UUID
    run_id: UUID
    agent_name: str
    input_tokens: int
    output_tokens: int
    total_cost: float
    created_at: datetime

    model_config = {"from_attributes": True}


class RunDetailResponse(RunResponse):
    updated_at: datetime
    logs: list[dict]
    research_output: Optional[str]
    analysis_output: Optional[str]
    final_output: Optional[str]
    error_message: Optional[str]
    citations: list[dict] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    costs: list[RunCostResponse] = Field(default_factory=list)
