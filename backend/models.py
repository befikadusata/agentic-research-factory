from sqlalchemy import Column, String, DateTime, Text, Enum as SAEnum, JSON, ForeignKey, Integer, Float, Boolean, func, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid, enum
from datetime import datetime, timezone
from database import Base


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    ready   = "ready"
    failed  = "failed"


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


class User(Base):
    """Credential store for the email/password auth provider.

    Identity across the app is the email string (see `user_id` everywhere), so
    this table only holds what password login needs — it does not replace or
    change the existing email-as-principal model. Google users never get a row
    here; they authenticate entirely through NextAuth/Google.
    """
    __tablename__ = "users"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email            = Column(String(255), unique=True, nullable=False, index=True)
    password_hash    = Column(String(255), nullable=False)
    name             = Column(String(255), nullable=True)
    # NULL until the user clicks the verification link; login is gated on this.
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at       = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                              server_default=func.now())


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

class Document(Base):
    __tablename__ = "documents"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id    = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    uploaded_by     = Column(String(255), nullable=False)
    filename        = Column(String(255), nullable=False)
    file_path       = Column(String(512), nullable=False)
    status          = Column(SAEnum(DocumentStatus), default=DocumentStatus.pending, nullable=False)
    vertical        = Column(String, nullable=True)
    chunk_count     = Column(Integer, nullable=True)
    error_message   = Column(Text, nullable=True)
    file_size_bytes = Column(Integer, nullable=False)
    created_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Run(Base):
    __tablename__ = "runs"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(String, nullable=False, index=True)
    workspace_id    = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True, index=True)
    # Set when this run was spawned by a scheduled Monitor rather than a manual
    # request; NULL for ordinary one-off runs. Lets monitor_service diff a
    # monitor's successive runs and lets the UI group them into a timeline.
    monitor_id      = Column(UUID(as_uuid=True), ForeignKey("monitors.id"), nullable=True, index=True)
    topic           = Column(Text, nullable=False)
    format          = Column(String, nullable=False)
    status          = Column(SAEnum(RunStatus), default=RunStatus.pending, nullable=False)
    failed_at_status = Column(SAEnum(RunStatus), nullable=True)
    vertical        = Column(String, nullable=True, index=True)
    vertical_inputs = Column(JSON, default=dict, server_default=text("'{}'::json"))
    doc_paths       = Column(JSON, default=list, server_default=text("'[]'::json"))
    research_output = Column(Text)
    analysis_output = Column(Text)
    final_output    = Column(Text)
    logs            = Column(JSON, default=list, server_default=text("'[]'::json"))
    error_message   = Column(Text, nullable=True)
    metrics         = Column(JSON, default=dict, server_default=text("'{}'::json"))  # { latency_ms, eval_scores, citation_count }
    costs           = relationship("RunCost", backref="run")
    created_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                             server_default=func.now())
    updated_at      = Column(DateTime(timezone=True),
                             default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc),
                             server_default=func.now())


class Monitor(Base):
    """A saved research request that re-runs on a schedule (continuous
    market-surveillance mode). A Monitor is effectively a Run template plus a
    cadence: the Celery-beat dispatcher periodically finds monitors whose
    `next_run_at` is due, spawns a fresh Run (with `Run.monitor_id` set), and
    advances `next_run_at`. Diffing successive runs and sending change alerts also
    live in monitor_service.

    Note: no ORM relationships are declared between Monitor and Run on purpose.
    There are two FK paths between the tables (`Run.monitor_id` and
    `Monitor.last_run_id`), so any relationship would need explicit
    `foreign_keys=`; services query the columns directly instead.
    """
    __tablename__ = "monitors"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id          = Column(String(255), nullable=False, index=True)
    workspace_id     = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True, index=True)
    name             = Column(String(255), nullable=False)  # human label for the watchlist entry
    # Run template: mirrors the fields create_run reads.
    topic            = Column(Text, nullable=False)
    format           = Column(String, nullable=False)
    vertical         = Column(String, nullable=True)
    vertical_inputs  = Column(JSON, default=dict, server_default=text("'{}'::json"))
    doc_paths        = Column(JSON, default=list, server_default=text("'[]'::json"))
    interval_minutes = Column(Integer, nullable=False, default=1440)  # default: daily
    enabled          = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    # When the dispatcher should next spawn a run. Advanced by interval_minutes
    # each dispatch; the dispatcher selects monitors where next_run_at <= now().
    next_run_at      = Column(DateTime(timezone=True), nullable=False,
                              default=lambda: datetime.now(timezone.utc), index=True)
    # use_alter: monitors↔runs is a mutual FK (Run.monitor_id points back here),
    # so this side must be emitted as a separate ALTER — otherwise create_all/
    # drop_all (used by the test suite) can't topologically order the two tables
    # and raises CircularDependencyError.
    last_run_id      = Column(UUID(as_uuid=True),
                              ForeignKey("runs.id", use_alter=True,
                                         name="fk_monitors_last_run_id_runs"),
                              nullable=True)
    last_run_at      = Column(DateTime(timezone=True), nullable=True)
    # Where change alerts go (email address or webhook URL); NULL = no alerts.
    notify_channel   = Column(String(512), nullable=True)
    created_at       = Column(DateTime(timezone=True),
                              default=lambda: datetime.now(timezone.utc),
                              server_default=func.now())
    updated_at       = Column(DateTime(timezone=True),
                              default=lambda: datetime.now(timezone.utc),
                              onupdate=lambda: datetime.now(timezone.utc),
                              server_default=func.now())
