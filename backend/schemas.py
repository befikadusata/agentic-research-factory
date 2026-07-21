from pydantic import BaseModel, Field, model_validator
from uuid import UUID
from datetime import datetime
from urllib.parse import urlparse
from models import RunStatus
from typing import Optional, Any
from configs.verticals import VALID_VERTICALS, VERTICALS

class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    # bcrypt only uses the first 72 bytes; cap length so nothing is silently ignored.
    password: str = Field(..., min_length=8, max_length=72)
    name: Optional[str] = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=72)


class UserResponse(BaseModel):
    email: str
    name: Optional[str] = None


class RegisterResponse(BaseModel):
    email: str
    name: Optional[str] = None
    verification_required: bool = True
    # Only populated in development so the flow is testable without real email.
    dev_verification_url: Optional[str] = None


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=1)


class VerifyEmailResponse(BaseModel):
    email: str
    verified: bool


class ResendVerificationRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)


class SimpleStatusResponse(BaseModel):
    status: str = "ok"
    dev_verification_url: Optional[str] = None


def validate_vertical_inputs(vertical: Optional[str], vertical_inputs: dict[str, Any]) -> None:
    """Validate a vertical key and its structured inputs. Shared by run and
    monitor request models (a monitor is a saved run template). Raises
    ValueError on any problem so it surfaces as a 422 from Pydantic."""
    if vertical is None:
        return
    if vertical not in VALID_VERTICALS:
        raise ValueError(
            f"Unknown vertical '{vertical}'. Valid options: {VALID_VERTICALS}"
        )
    schema = VERTICALS[vertical].get("input_schema", {})
    for key, field_def in schema.items():
        val = vertical_inputs.get(key)
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


class CreateRunRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    format: str = Field(..., pattern="^(report|linkedin|summary)$")
    doc_ids: list[str] = Field(default_factory=list)
    workspace_id: Optional[UUID] = None
    vertical: Optional[str] = None
    vertical_inputs: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_vertical(self) -> "CreateRunRequest":
        validate_vertical_inputs(self.vertical, self.vertical_inputs)
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


class LogEntryResponse(BaseModel):
    agent: str
    message: str
    ts: str


class RunDetailResponse(RunResponse):
    updated_at: datetime
    logs: list[LogEntryResponse]
    research_output: Optional[str]
    analysis_output: Optional[str]
    final_output: Optional[str]
    error_message: Optional[str]
    citations: list[dict] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    costs: list[RunCostResponse] = Field(default_factory=list)


# Cadence bounds: at least every 15 min (LLM-heavy pipeline; tighter would
# just pile up cost), at most every 30 days.
_MIN_INTERVAL = 15
_MAX_INTERVAL = 60 * 24 * 30


class CreateMonitorRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    topic: str = Field(..., min_length=3, max_length=500)
    format: str = Field(..., pattern="^(report|linkedin|summary)$")
    doc_ids: list[str] = Field(default_factory=list)
    workspace_id: Optional[UUID] = None
    vertical: Optional[str] = None
    vertical_inputs: dict[str, Any] = Field(default_factory=dict)
    interval_minutes: int = Field(default=1440, ge=_MIN_INTERVAL, le=_MAX_INTERVAL)
    enabled: bool = True
    notify_channel: Optional[str] = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def validate_vertical(self) -> "CreateMonitorRequest":
        validate_vertical_inputs(self.vertical, self.vertical_inputs)
        return self


class UpdateMonitorRequest(BaseModel):
    """Partial update — only schedule/label/toggle fields. The run template
    (topic, vertical, docs) is immutable so a monitor's history stays coherent;
    create a new monitor to watch something different."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    interval_minutes: Optional[int] = Field(default=None, ge=_MIN_INTERVAL, le=_MAX_INTERVAL)
    enabled: Optional[bool] = None
    notify_channel: Optional[str] = Field(default=None, max_length=512)


class MonitorResponse(BaseModel):
    id: UUID
    user_id: str
    workspace_id: Optional[UUID]
    name: str
    topic: str
    format: str
    vertical: Optional[str]
    vertical_inputs: dict[str, Any] = Field(default_factory=dict)
    interval_minutes: int
    enabled: bool
    next_run_at: datetime
    last_run_id: Optional[UUID]
    last_run_at: Optional[datetime]
    notify_channel: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
