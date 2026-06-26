from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RuntimeProfile(StrEnum):
    DEFAULT = "default"
    HEAVY = "heavy"
    COMMUNITY = "community"


class FactorStage(StrEnum):
    INGEST = "ingest"
    NORMALIZE = "normalize"
    SIGNAL_EXTRACTION = "signal_extraction"
    EVIDENCE_BUILDING = "evidence_building"
    CASE_BUILDING = "case_building"
    VERDICT_BUILDING = "verdict_building"
    INSIGHT_AGGREGATION = "insight_aggregation"


class EvidencePolicy(BaseModel):
    required: bool = True
    min_refs: int = 1
    raw_content_allowed: bool = False


class FactorSpec(BaseModel):
    id: str
    name: str
    framework_id: str
    stage: FactorStage
    runtime_profile: RuntimeProfile
    default_enabled: bool = False
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    evidence_policy: EvidencePolicy = Field(default_factory=EvidencePolicy)
    verdict_signals: list[str] = Field(default_factory=list)


class FactorResult(BaseModel):
    schema_version: str = "factor_result.v0"
    run_id: str = Field(default_factory=lambda: f"frun_{uuid4().hex}")
    factor_id: str
    factor_version: str = ""
    framework_id: str
    stage: FactorStage
    target_type: str
    target_id: str
    session_id: str = ""
    status: str = "matched"
    tags: list[dict[str, str]] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    statistics: dict[str, Any] = Field(default_factory=dict)
    datasets: list[dict[str, Any]] = Field(default_factory=list)
    presentations: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[dict[str, str]] = Field(default_factory=list)
    verdict_signals: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    confidence: float
