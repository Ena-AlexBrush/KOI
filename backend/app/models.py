from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Decision = Literal["accept", "reject", "needs_information"]
Status = Literal["consensus", "keep_disagreement", "needs_human", "research_complete", "error", "running"]


class ToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class PlanRef(BaseModel):
    plan_id: str
    plan_version: int
    route_option_id: str
    commitment_changes: list[dict[str, Any]] = Field(default_factory=list)


class AgentPlanSelection(BaseModel):
    plan_id: str
    plan_version: int
    route_option_id: str


class Objection(BaseModel):
    challenged_plan_id: str
    challenged_plan_version: int
    concern: str
    resolution_needed: str


class Evaluation(BaseModel):
    plan_id: str
    plan_version: int
    decision: Decision
    reason: str


class WebFinding(BaseModel):
    title: str
    transport_mode: str
    summary: str
    price: str | None = None
    departure: str | None = None
    arrival: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    booking_source_id: str | None = None


class WebObjection(BaseModel):
    agent_name: str | None = None
    concern: str
    question: str


class WebAgentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendation: str
    findings: list[WebFinding] = Field(default_factory=list, max_length=5)
    objections: list[WebObjection] = Field(default_factory=list, max_length=5)
    supporting_source_ids: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    proposal_changed: bool = False
    change_reason: str = ""


class AgentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=4)
    proposed_plan: AgentPlanSelection | None
    reason: str
    supporting_facts: list[str] = Field(default_factory=list)
    objections: list[Objection] = Field(default_factory=list)
    requested_capabilities: list[str] = Field(default_factory=list)
    evaluations: list[Evaluation] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    proposal_changed: bool = False
    change_reason: str


class AgentResponse(BaseModel):
    message_id: str
    run_id: str
    agent_name: str
    round_number: int
    phase: Literal["initial_proposal", "negotiation"]
    evidence_version: int
    recipients: list[str]
    in_reply_to: list[str]
    proposed_plan: PlanRef | None
    reason: str
    supporting_facts: list[str]
    objections: list[Objection | WebObjection]
    requested_capabilities: list[str]
    evaluations: list[Evaluation]
    missing_information: list[str]
    proposal_changed: bool
    change_reason: str
    tool_calls: list[ToolCall]
    tool_results: list[dict[str, Any]]
    call_status: Literal["success", "fallback", "timeout", "model_error", "invalid_output"]
    timestamp: datetime
    error: str | None = None
    findings: list[dict[str, Any]] = Field(default_factory=list)


class TripDetails(BaseModel):
    flight_number: str = Field(min_length=1, max_length=16)
    airline: str = Field(min_length=1, max_length=80)
    origin: str = Field(min_length=2, max_length=100)
    destination: str = Field(min_length=2, max_length=100)
    travel_date: date
    budget_usd: int = Field(gt=0, le=100000)
    arrive_by: str | None = Field(default=None, max_length=120)
    important_plans: list[str] = Field(default_factory=list, max_length=8)


class RunCreate(BaseModel):
    scenario_id: Literal["nyc_recovery", "infeasible"] | None = None
    mode: Literal["live", "demo_playback"] = "live"
    trip_details: TripDetails | None = None


class EvidenceUpdate(BaseModel):
    action: Literal["option_c_unavailable"]

