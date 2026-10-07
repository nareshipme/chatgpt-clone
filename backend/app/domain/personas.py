"""Personas: who the copilot is talking to. A persona changes the system prompt and the starter prompts; it never
changes what data a user may see (that is the tenant and role, which come from the database)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    id: str
    tenant_id: str
    name: str
    description: str
    focus: str  # appended to the system prompt
    starters: tuple[str, ...]


PERSONAS: tuple[Persona, ...] = (
    Persona(
        "demand_planner", "northwind", "Demand planner",
        "Forecast accuracy, promotions and stock-outs.",
        "The user is a demand planner. Care about forecast accuracy, promotion effects and the risk of stock-outs. "
        "Lead with the SKUs most at risk and explain what drives the forecast.",
        (
            "Which SKUs are likely to stock out in the next two weeks, and where?",
            "How is the frozen pizza forecast affected by the promotion?",
            "How accurate was the forecast for whole milk over the last two weeks?",
        ),
    ),
    Persona(
        "dc_manager", "northwind", "DC manager",
        "Inventory, balance between distribution centres and what to move.",
        "The user manages distribution centres. Care about days of cover, excess stock and where stock can be moved "
        "without creating a shortage elsewhere. When a move would help, propose it with the proposal tool.",
        (
            "Where do I have excess inventory I could move?",
            "Which positions are below 7 days of cover?",
            "Can we fix the milk shortage at DC-5 by moving stock from another DC?",
        ),
    ),
    Persona(
        "transport_planner", "harbor", "Transportation planner",
        "ETAs, delays, SLA risk, and cost and carbon per lane.",
        "The user plans transportation. Care about which shipments will miss their SLA and why, and about cost and "
        "carbon side by side when comparing modes. Lead with breaches, then at-risk loads.",
        (
            "Which shipments are at risk of missing their SLA this week?",
            "Compare cost and carbon by mode for Chicago to Dallas.",
            "What is the total cargo value at risk right now?",
        ),
    ),
)

_BY_ID = {p.id: p for p in PERSONAS}
DEFAULT_PERSONA = {"northwind": "demand_planner", "harbor": "transport_planner"}


def personas_for(tenant_id: str) -> list[Persona]:
    return [p for p in PERSONAS if p.tenant_id == tenant_id]


def get_persona(persona_id: str | None, tenant_id: str) -> Persona | None:
    """The persona if it exists and belongs to this tenant; otherwise None."""
    p = _BY_ID.get(persona_id or "")
    return p if p and p.tenant_id == tenant_id else None


def effective_persona(persona_id: str | None, tenant_id: str) -> Persona | None:
    """The user's choice, or the tenant's default when none was made (or the choice no longer applies)."""
    return get_persona(persona_id, tenant_id) or get_persona(DEFAULT_PERSONA.get(tenant_id), tenant_id)
