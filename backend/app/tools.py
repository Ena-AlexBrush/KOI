from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from .validation import option_cost, parse_time, validate_changes, validate_plan


def check_option(option: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    return validate_plan({"route_option_id": option["id"],
                          "commitment_changes": option.get("commitment_changes", [])}, scenario)


def search_routes(scenario: dict[str, Any], *, original_method_only: bool, include_alternatives: bool) -> list[dict[str, Any]]:
    result = []
    for option in scenario["options"]:
        if not option["available"] or not option.get("discovered", True):
            continue
        if original_method_only and option["method"] != scenario["original_method"]:
            continue
        if option.get("alternative_only") and not include_alternatives:
            continue
        result.append({"id": option["id"], "name": option["name"], "method": option["method"], "total_cost_usd": float(option_cost(option)), "venue_arrival": option["venue_arrival"], "source_id": option["source_id"], "legs": option["legs"]})
    return result


def execute_tool(agent: str, tool_call: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    name = tool_call["tool_name"]
    args = tool_call.get("arguments", {})
    scenario = state["scenario"]
    capabilities = state["capabilities"].get(agent, set())
    if name not in capabilities:
        raise ValueError(f"{agent} cannot use {name}")
    if name == "route_search":
        return {"routes": search_routes(scenario, original_method_only=True, include_alternatives=state["alternative_active"])}
    if name == "alternative_route_search":
        if not state["alternative_active"]:
            state["alternative_requested_by"].append(agent)
        return {"routes": search_routes(scenario, original_method_only=False, include_alternatives=True)}
    if name == "cost_calculator":
        option = _get_option(scenario, args.get("route_option_id"))
        checked = check_option(option, scenario)
        return {"route_option_id": option["id"], "cost_usd": checked.get("cost_usd"), "leg_costs_usd": [leg["cost_usd"] for leg in option["legs"]], "commitment_fees_usd": checked.get("commitment_fees_usd"), "budget_usd": scenario["budget_usd"], "validation": checked}
    if name == "arrival_feasibility":
        option = _get_option(scenario, args.get("route_option_id"))
        return check_option(option, scenario)
    if name == "schedule_change_proposal":
        _, fees, violations = validate_changes(args.get("commitment_changes", []), scenario)
        return {"flexible_events": [event["id"] for event in scenario["itinerary"] if event["flexible"]], "mandatory_events": [event["id"] for event in scenario["itinerary"] if event["mandatory"]], "proposed_changes": args.get("commitment_changes", []), "valid": not violations, "violations": violations, "additional_fees_usd": float(fees)}
    raise ValueError(f"Unknown tool: {name}")


class NoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RouteArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route_option_id: str = Field(min_length=1)


class ScheduleArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commitment_changes: list[dict[str, Any]] = Field(default_factory=list, max_length=10)


def validate_tool_arguments(tool_call: dict[str, Any]) -> dict[str, Any]:
    name = tool_call["tool_name"]
    schema = {"route_search":NoArguments,"alternative_route_search":NoArguments,"cost_calculator":RouteArguments,"arrival_feasibility":RouteArguments,"schedule_change_proposal":ScheduleArguments}.get(name)
    if schema is None:
        raise ValueError(f"Unknown tool: {name}")
    return schema.model_validate(tool_call.get("arguments", {})).model_dump()


def _get_option(scenario: dict[str, Any], option_id: str | None) -> dict[str, Any]:
    option = next((item for item in scenario["options"] if item["id"] == option_id), None)
    if option is None or not option["available"] or not option.get("discovered", True):
        raise ValueError("route_option_id must refer to an available fixture route")
    return option


def validate_dataset_refs(draft: dict[str, Any], scenario: dict[str, Any]) -> None:
    visible = [option for option in scenario["options"] if option["available"] and option.get("discovered", True)]
    valid_sources = {option["source_id"] for option in visible}
    valid_sources.update(r["source_id"] for o in visible for r in o.get("entry_requirements", []) if r.get("source_id"))
    visa_metadata = scenario.get("visa_eligibility")
    if visa_metadata and visa_metadata.get("source_id"):
        valid_sources.add(visa_metadata["source_id"])
    invalid = set(draft.get("supporting_facts", [])) - valid_sources
    if invalid:
        raise ValueError(f"unknown supporting fact IDs: {sorted(invalid)}")
    route_ids = {option["id"] for option in visible}
    plan = draft.get("proposed_plan")
    if plan and plan["route_option_id"] not in route_ids:
        raise ValueError("proposed plan references an unavailable route")

