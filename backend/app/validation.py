"""Independent Python validation adapted from codex/koi-backend.

Keep Anu's route/event names and validation result keys. Agent claims and tool
requests never supply authoritative prices, scheduling permissions, or policy.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("timestamps must include a timezone offset")
    return parsed


def money(value) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite() or result < 0 or result.as_tuple().exponent < -2:
        raise ValueError("cost must be a nonnegative amount with at most two decimal places")
    return result


def option_cost(option: dict[str, Any]) -> Decimal:
    return sum((money(leg["cost_usd"]) for leg in option["legs"]), Decimal(0)) + sum(
        (money(cost) for cost in option.get("additional_costs_usd", [])), Decimal(0))


def validate_changes(changes, scenario):
    events = {e["id"]: e for e in scenario["itinerary"]}
    selected, violations = {}, []
    fees = Decimal(0)
    for change in changes:
        event_id = change.get("event_id")
        if event_id in selected:
            violations.append("duplicate_commitment_change")
        event = events.get(event_id)
        if event is None:
            violations.append("unknown_commitment")
            continue
        selected[event_id] = None
        if event["mandatory"] or not event["flexible"]:
            violations.append("mandatory_commitment_change")
            continue
        allowed = next((c for c in event.get("allowed_changes", []) if c["id"] == change.get("change_option_id")), None)
        if allowed is None:
            violations.append("unknown_commitment_change")
            continue
        # All authoritative fields come from the supplied allowed change.
        if change.get("start", allowed["start"]) != allowed["start"] or change.get("end", allowed["end"]) != allowed["end"]:
            violations.append("commitment_change_mismatch")
        if "fee_usd" in change and money(change["fee_usd"]) != money(allowed["fee_usd"]):
            violations.append("commitment_fee_mismatch")
        start, end = parse_time(allowed["start"]), parse_time(allowed["end"])
        if (not event.get("earliest_start") or not event.get("latest_end")
                or start < parse_time(event["earliest_start"]) or end > parse_time(event["latest_end"])
                or end <= start or end - start < parse_time(event["end"]) - parse_time(event["time"])):
            violations.append("flexible_scheduling_constraints")
        selected[event_id] = allowed
        fees += money(allowed["fee_usd"])
    return selected, fees, violations


def validate_plan(plan: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    option = next((o for o in scenario["options"] if o["id"] == plan.get("route_option_id")
                   and o["available"] and o.get("discovered", True)), None)
    if option is None:
        return {"valid": False, "violations": ["route_unavailable"], "missing_information": []}
    violations, missing = [], []
    try:
        cost = option_cost(option)
        declared = money(option["total_cost_usd"])
        cost_matches = cost == declared
        if not cost_matches:
            violations.append("route_cost_does_not_match_legs")
        if not option.get("costs_complete", False):
            missing.append("complete_additional_costs")
        legs = option["legs"]
        for index, leg in enumerate(legs):
            departure, arrival = parse_time(leg["depart"]), parse_time(leg["arrive"])
            if arrival <= departure:
                violations.append("leg_timing")
            if index:
                previous = legs[index - 1]
                if previous["to"] != leg["from"]:
                    violations.append("transfer_location")
                minimum = leg.get("minimum_connection_minutes")
                if minimum is None:
                    missing.append("minimum_connection_time")
                elif minimum < 0 or parse_time(previous["arrive"]) + timedelta(minutes=minimum) > departure:
                    violations.append("transfer_timing")
        arrival = parse_time(option["venue_arrival"])
        if arrival != parse_time(legs[-1]["arrive"]):
            violations.append("venue_arrival_mismatch")
        if legs[0]["from"] != scenario["origin"] or legs[-1]["to"] != scenario["destination"]:
            violations.append("route_endpoints")
        if parse_time(legs[0]["depart"]) < parse_time(scenario["earliest_departure"]):
            violations.append("earliest_departure")
        selected, fees, errors = validate_changes(plan.get("commitment_changes", []), scenario)
        violations.extend(errors)
        cost += fees
        if cost > money(scenario["budget_usd"]):
            violations.append("hard_budget")
        mandatory_ok = True
        scheduled = []
        for event in scenario["itinerary"]:
            change = selected.get(event["id"])
            start = parse_time(change["start"] if change else event["time"])
            end = parse_time(change["end"] if change else event["end"])
            if parse_time(event["end"]) <= parse_time(scenario["earliest_departure"]):
                if event["id"] in selected:
                    violations.append("past_commitment_change")
                continue
            if arrival + timedelta(minutes=event.get("arrival_buffer_minutes", 0)) > start:
                if event["mandatory"]:
                    mandatory_ok = False
                    violations.append("mandatory_presentation" if event["id"] == "presentation" else "mandatory_commitment")
                else:
                    violations.append("flexible_commitment_missed")
            if end <= start:
                violations.append("commitment_timing")
            scheduled.append((start, end))
        scheduled.sort()
        if any(b[0] < a[1] for i, a in enumerate(scheduled) for b in scheduled[i + 1:]):
            violations.append("commitment_overlap")
        if not option.get("entry_requirements_complete", False):
            missing.append("entry_transit_coverage")
        requirements = option.get("entry_requirements", [])
        if not requirements:
            evidence = scenario.get("visa_eligibility") or {}
            if (evidence.get("status") != "not_applicable_domestic" or not evidence.get("source_id")
                    or not evidence.get("basis") or not evidence.get("evidence_complete")):
                missing.append("entry_transit_evidence")
        for req in requirements:
            if not req.get("source_id") or not req.get("source") or not req.get("evidence_complete"):
                missing.append(f"requirement_evidence:{req['id']}")
            criteria = req.get("allowed_traveler_facts", {})
            if not criteria:
                missing.append(f"requirement_criteria:{req['id']}")
            for key, allowed in criteria.items():
                actual = scenario.get("traveler_information", {}).get(key)
                if not actual or not allowed:
                    missing.append(f"traveler_information:{key}")
                elif actual not in allowed:
                    violations.append(f"entry_transit_ineligible:{req['id']}")
        violations.extend(missing)
        return {"valid": not violations, "violations": list(dict.fromkeys(violations)),
                "missing_information": list(dict.fromkeys(missing)), "route_option_id": option["id"],
                "cost_usd": float(cost), "declared_cost_usd": float(declared), "commitment_fees_usd": float(fees),
                "cost_matches_legs": cost_matches, "venue_arrival": option["venue_arrival"],
                "arrives_before_mandatory_event": mandatory_ok, "budget_usd": scenario["budget_usd"],
                "within_budget": cost <= money(scenario["budget_usd"])}
    except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
        return {"valid": False, "violations": ["invalid_supplied_data"], "missing_information": [str(exc)]}
