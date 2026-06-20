from sqlalchemy import Column, String, DateTime, Text, Enum as SAEnum, JSON, ForeignKey, Integer, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid, enum
from datetime import datetime, timezone
from database import Base


class RunStatus(str, enum.Enum):
    pending                    = "pending"
    researching                = "researching"
    awaiting_research_approval = "awaiting_research_approval"
    analyzing                  = "analyzing"
    awaiting_analysis_approval = "awaiting_analysis_approval"
    writing                    = "writing"
    awaiting_final_approval    = "awaiting_final_approval"
    complete                   = "complete"
    failed                     = "failed"


class Workspace(Base):
    __tablename__ = "workspaces"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(255), nullable=False)
    owner_id   = Column(String(255), nullable=False, index=True)
    settings   = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), primary_key=True)
    user_id      = Column(String(255), nullable=False, primary_key=True)
    role         = Column(String(50), nullable=False, default="viewer")  # viewer | operator | admin


class RunCost(Base):
    __tablename__ = "run_costs"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id     = Column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    total_cost = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Run(Base):
    __tablename__ = "runs"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(String, nullable=False, index=True)
    workspace_id    = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True, index=True)
    topic           = Column(Text, nullable=False)
    format          = Column(String, nullable=False)
    status          = Column(SAEnum(RunStatus), default=RunStatus.pending, nullable=False)
    vertical        = Column(String, nullable=True, index=True)
    vertical_inputs = Column(JSON, default=dict)
    doc_paths       = Column(JSON, default=list)
    research_output = Column(Text)
    analysis_output = Column(Text)
    final_output    = Column(Text)
    logs            = Column(JSON, default=list)
    metrics         = Column(JSON, default=dict)  # { latency_ms, eval_scores, citation_count }
    costs           = relationship("RunCost", backref="run")
    created_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime(timezone=True),
                             default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))
