from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone offset")
    return parsed


def option_cost(option: dict[str, Any]) -> int:
    return sum(int(leg["cost_usd"]) for leg in option["legs"])


def check_option(option: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    event = next(item for item in scenario["itinerary"] if item["mandatory"])
    arrival = parse_time(option["venue_arrival"])
    deadline = parse_time(event["time"])
    cost = option_cost(option)
    leg_total = cost
    declared_total = int(option["total_cost_usd"])
    return {
        "route_option_id": option["id"],
        "cost_usd": cost,
        "declared_cost_usd": declared_total,
        "cost_matches_legs": leg_total == declared_total,
        "venue_arrival": option["venue_arrival"],
        "arrives_before_mandatory_event": arrival <= deadline,
        "budget_usd": scenario["budget_usd"],
        "within_budget": cost <= scenario["budget_usd"],
    }


def search_routes(scenario: dict[str, Any], *, original_method_only: bool, include_alternatives: bool) -> list[dict[str, Any]]:
    result = []
    for option in scenario["options"]:
        if not option["available"]:
            continue
        if original_method_only and option["method"] != "flight":
            continue
        if option.get("alternative_only") and not include_alternatives:
            continue
        result.append({"id": option["id"], "name": option["name"], "method": option["method"], "total_cost_usd": option_cost(option), "venue_arrival": option["venue_arrival"], "source_id": option["source_id"], "legs": option["legs"]})
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
        return {"route_option_id": option["id"], "cost_usd": option_cost(option), "leg_costs_usd": [leg["cost_usd"] for leg in option["legs"]], "budget_usd": scenario["budget_usd"]}
    if name == "arrival_feasibility":
        option = _get_option(scenario, args.get("route_option_id"))
        return check_option(option, scenario)
    if name == "schedule_change_proposal":
        return {"flexible_events": [event["id"] for event in scenario["itinerary"] if event["flexible"]], "mandatory_events": [event["id"] for event in scenario["itinerary"] if event["mandatory"]], "proposed_changes": args.get("commitment_changes", [])}
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
    if option is None or not option["available"]:
        raise ValueError("route_option_id must refer to an available fixture route")
    return option


def validate_dataset_refs(draft: dict[str, Any], scenario: dict[str, Any]) -> None:
    valid_sources = {option["source_id"] for option in scenario["options"] if option["available"]}
    visa_metadata = scenario.get("visa_eligibility")
    if visa_metadata and visa_metadata.get("source_id"):
        valid_sources.add(visa_metadata["source_id"])
    invalid = set(draft.get("supporting_facts", [])) - valid_sources
    if invalid:
        raise ValueError(f"unknown supporting fact IDs: {sorted(invalid)}")
    route_ids = {option["id"] for option in scenario["options"] if option["available"]}
    plan = draft.get("proposed_plan")
    if plan and plan["route_option_id"] not in route_ids:
        raise ValueError("proposed plan references an unavailable route")

