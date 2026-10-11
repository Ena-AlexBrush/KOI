from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from .scenario import Scenario


Decision = Literal["accept", "reject", "needs_information"]
Status = Literal["consensus", "keep_disagreement", "needs_human", "error", "running"]


class ToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class PlanRef(BaseModel):
    plan_id: str
    plan_version: int
    route_option_id: str
    commitment_changes: list[dict[str, Any]] = Field(default_factory=list)


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


class AgentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    in_reply_to: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=4)
    proposed_plan: PlanRef | None
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
    objections: list[Objection]
    requested_capabilities: list[str]
    evaluations: list[Evaluation]
    missing_information: list[str]
    proposal_changed: bool
    change_reason: str
    tool_calls: list[ToolCall]
    tool_results: list[dict[str, Any]]
    call_status: Literal["success", "timeout", "model_error", "invalid_output"]
    timestamp: datetime
    error: str | None = None


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: Literal["nyc_recovery", "infeasible"] = "nyc_recovery"
    mode: Literal["live", "demo_playback"] = "live"
    # Optional supplied dataset; uses the same schema as the built-in fixtures.
    scenario: Scenario | None = None


class EvidenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["option_c_unavailable", "update_information"]
    unavailable_option_ids: list[str] = Field(default_factory=list)
    traveler_information: dict[str, str] = Field(default_factory=dict)
    reason: str = "Supplied information changed."

