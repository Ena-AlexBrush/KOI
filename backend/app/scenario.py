"""Typed supplied evidence, using Anu's existing fixture field names."""
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Leg(InputModel):
    mode: str = Field(min_length=1)
    origin: str = Field(alias="from", min_length=1)
    destination: str = Field(alias="to", min_length=1)
    depart: AwareDatetime
    arrive: AwareDatetime
    cost_usd: Money
    minimum_connection_minutes: int | None = Field(default=None, ge=0)


class AllowedChange(InputModel):
    id: str
    start: AwareDatetime
    end: AwareDatetime
    fee_usd: Money


class Event(InputModel):
    id: str
    name: str
    time: AwareDatetime
    end: AwareDatetime
    mandatory: bool
    flexible: bool
    arrival_buffer_minutes: int = Field(default=0, ge=0)
    earliest_start: AwareDatetime | None = None
    latest_end: AwareDatetime | None = None
    allowed_changes: list[AllowedChange] = Field(default_factory=list)

    @model_validator(mode="after")
    def schedule(self):
        if self.end <= self.time:
            raise ValueError("event end must follow start")
        if self.mandatory and (self.flexible or self.allowed_changes):
            raise ValueError("mandatory events cannot be flexible or have changes")
        if self.allowed_changes and (not self.flexible or self.earliest_start is None or self.latest_end is None):
            raise ValueError("allowed changes require flexible events and supplied scheduling bounds")
        if len({c.id for c in self.allowed_changes}) != len(self.allowed_changes):
            raise ValueError("duplicate allowed change IDs")
        return self


class Requirement(InputModel):
    id: str
    country: str
    kind: Literal["entry", "transit"]
    source_id: str | None = None
    source: str | None = None
    evidence_complete: bool = False
    allowed_traveler_facts: dict[str, list[str]] = Field(default_factory=dict)


class RouteOption(InputModel):
    id: str
    name: str
    method: str = Field(min_length=1)
    available: bool
    alternative_only: bool = False
    # Discovery is distinct from availability: tools cannot revive an unavailable route.
    discovered: bool = True
    legs: list[Leg] = Field(min_length=1, max_length=12)
    total_cost_usd: Money
    additional_costs_usd: list[Money] = Field(default_factory=list)
    costs_complete: bool = False
    venue_arrival: AwareDatetime
    source_id: str
    commitment_changes: list[dict] = Field(default_factory=list, max_length=20)
    entry_requirements_complete: bool = False
    entry_requirements: list[Requirement] = Field(default_factory=list)


class VisaEvidence(InputModel):
    status: str
    basis: str | None = None
    source_id: str | None = None
    evidence_complete: bool = False


class Scenario(InputModel):
    label: str
    original_method: Literal["flight", "train", "bus", "car", "ferry", "walk"]
    origin: str
    destination: str
    timezone: str
    budget_usd: Money
    earliest_departure: AwareDatetime
    traveler_information: dict[str, str] = Field(default_factory=dict)
    visa_eligibility: VisaEvidence | None = None
    canceled_route_id: str
    itinerary: list[Event] = Field(default_factory=list, max_length=20)
    options: list[RouteOption] = Field(min_length=1, max_length=20)
    note: str | None = None

    @model_validator(mode="after")
    def unique_ids(self):
        for items in (self.itinerary, self.options):
            if len({x.id for x in items}) != len(items):
                raise ValueError("duplicate event or route IDs")
        return self
