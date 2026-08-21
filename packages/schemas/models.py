from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


def utcnow() -> datetime:
    return datetime.now(UTC)


class ReplicationStatus(StrEnum):
    QUEUED = "queued"
    READING = "reading"
    PLANNING = "planning"
    CODING = "coding"
    RUNNING = "running"
    VERIFYING = "verifying"
    REPORTED = "reported"
    FAILED_SYSTEM = "failed_system"


class VerdictStatus(StrEnum):
    REPRODUCED = "REPRODUCED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"


class Budget(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    max_job_minutes: float = Field(default=20, gt=0, le=360)
    max_usd: float = Field(default=1.0, gt=0, le=100)


class Spend(BaseModel):
    usd: float = Field(default=0, ge=0)
    job_minutes: float = Field(default=0, ge=0)


class ReplicationCreate(BaseModel):
    source_url: HttpUrl
    budget: Budget = Field(default_factory=Budget)


class Replication(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    trace_id: str = Field(default_factory=lambda: uuid4().hex)
    source_url: str
    pdf_gcs_uri: str | None = None
    status: ReplicationStatus = ReplicationStatus.QUEUED
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    budget: Budget = Field(default_factory=Budget)
    spent: Spend = Field(default_factory=Spend)
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    report_gcs_uri: str | None = None
    summary_verdict: str | None = None


class Claim(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    replication_id: str
    index: int = Field(ge=0)
    text: str
    claim_type: str
    metric_name: str | None = None
    reported_value: float | None = None
    unit: str | None = None
    tolerance_pct: float = Field(default=5, gt=0)
    figure_ref: str | None = None
    figure_gcs_uri: str | None = None
    table_ref: str | None = None
    priority: int = Field(default=2, ge=1, le=3)
    feasible: bool = True
    feasibility_reason: str = ""


class PaperExtraction(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    full_text: str
    page_count: int = Field(ge=1)
    figure_paths: list[str] = Field(default_factory=list)
    injection_suspected: bool = False
    injection_reasons: list[str] = Field(default_factory=list)


class ClaimExtraction(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    claims: list[Claim]


class ClaimCandidate(BaseModel):
    text: str
    claim_type: str
    metric_name: str | None = None
    reported_value: float | None = None
    unit: str | None = None
    tolerance_pct: float = Field(default=5, gt=0)
    figure_ref: str | None = None
    figure_image_index: int | None = Field(default=None, ge=0)
    table_ref: str | None = None
    priority: int = Field(default=2, ge=1, le=3)
    feasible: bool = False
    feasibility_reason: str = "Model did not establish feasibility"

    @field_validator("tolerance_pct", "priority", mode="before")
    @classmethod
    def numeric_defaults_for_null(cls, value: Any, info: Any) -> Any:
        fallback = 5 if info.field_name == "tolerance_pct" else 2
        if value is None:
            return fallback
        if info.field_name == "tolerance_pct" and float(value) <= 0:
            return fallback
        return value

    @field_validator("feasible", mode="before")
    @classmethod
    def feasibility_defaults_to_false(cls, value: Any) -> Any:
        return False if value is None else value

    @field_validator("feasibility_reason", mode="before")
    @classmethod
    def reason_defaults_for_null(cls, value: Any) -> Any:
        return "Model did not establish feasibility" if value is None else value


class ReaderResult(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    claims: list[ClaimCandidate]

    @classmethod
    def model_json_schema(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Inline the nested claim schema for Vertex's OpenAPI subset."""
        schema = super().model_json_schema(*args, **kwargs)
        definitions = schema.pop("$defs", {})
        claim_schema = definitions.get("ClaimCandidate")
        if claim_schema:
            tolerance = claim_schema["properties"]["tolerance_pct"]
            tolerance.pop("exclusiveMinimum", None)
            tolerance["minimum"] = 0
            schema["properties"]["claims"]["items"] = claim_schema
        return schema


class ExperimentPlan(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    replication_id: str
    claim_ids: list[str]
    strategy: str
    repo_url: str | None = None
    dataset_sources: list[str] = Field(default_factory=list)
    estimated_minutes: float = Field(gt=0)
    estimated_usd: float = Field(ge=0)
    base_image: str = "python:3.11-slim"
    steps: list[str]
    risks: list[str] = Field(default_factory=list)


class Attempt(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    plan_id: str
    n: int = Field(ge=1)
    status: str = "queued"
    code_gcs_uri: str | None = None
    dockerfile: str | None = None
    job_name: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exit_code: int | None = None
    stdout_gcs_uri: str | None = None
    error_signature: str | None = None
    diagnosis: str | None = None
    patch_summary: str | None = None
    metrics_gcs_uri: str | None = None
    figures_gcs_uri: list[str] = Field(default_factory=list)


class Verdict(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    claim_id: str
    attempt_id: str | None = None
    status: VerdictStatus
    obtained_value: float | None = None
    delta_pct: float | None = None
    figure_similarity_score: float | None = None
    vision_assessment: str = ""
    reasoning: str
    evidence_links: list[str] = Field(default_factory=list)


class Memory(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    key: str
    lesson: str
    fix_snippet: str
    times_used: int = 0
    last_used_at: datetime = Field(default_factory=utcnow)
    origin_replication_id: str


class ExecutionResult(BaseModel):
    exit_code: int
    job_minutes: float = Field(ge=0)
    cost_usd: float = Field(ge=0)
    stdout_uri: str
    metrics_uri: str | None = None
    figure_uris: list[str] = Field(default_factory=list)
    stderr_tail: str = ""


class RepairDecision(BaseModel):
    error_signature: str
    diagnosis: str
    patch_summary: str
    patch: str
    reusable_lesson: str


class ReportManifest(BaseModel):
    replication_id: str
    report_sha256: str
    generated_at: datetime = Field(default_factory=utcnow)
    verdict_ids: list[str]
    evidence_uris: list[str]
    signature: str | None = None
    signature_algorithm: str | None = None


class VisionAssessment(BaseModel):
    same_trend: bool
    same_series_ordering: bool
    comparable_scale: bool
    same_scientific_conclusion: bool
    specific_evidence: list[str] = Field(min_length=1)
    caveats: list[str] = Field(default_factory=list)


class GeneratedExperiment(BaseModel):
    run_py: str
    requirements_txt: str
    rationale: str


class PlanProposal(BaseModel):
    strategy: str
    repo_url: str | None = None
    dataset_sources: list[str] = Field(default_factory=list)
    estimated_minutes: float = Field(gt=0)
    estimated_usd: float = Field(ge=0)
    base_image: str = "python:3.11-slim"
    steps: list[str] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)

    @classmethod
    def model_json_schema(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        schema = super().model_json_schema(*args, **kwargs)
        minutes = schema["properties"]["estimated_minutes"]
        minutes.pop("exclusiveMinimum", None)
        minutes["minimum"] = 0
        return schema


class WorkMessage(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    event_type: str
    replication_id: str
    claim_id: str | None = None
    plan_id: str | None = None
    attempt_id: str | None = None
    trace_id: str = Field(default_factory=lambda: uuid4().hex)
    occurred_at: datetime = Field(default_factory=utcnow)


class Event(BaseModel):
    sequence: int = 0
    replication_id: str
    kind: str
    stage: str
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class PubSubEnvelope(BaseModel):
    message: dict[str, Any]
    subscription: str | None = None

    @model_validator(mode="after")
    def has_data(self) -> PubSubEnvelope:
        if "data" not in self.message:
            raise ValueError("Pub/Sub message.data is required")
        return self
