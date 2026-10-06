"""The copilot's tools: small, typed, tenant-scoped functions over the scenario data.

Rules every tool follows (the system prompt and the tests rely on them):
  * Arguments are validated with Pydantic before anything runs; a bad call is a ToolError, never a crash.
  * A tool is only offered to, and only runnable by, the tenants it is registered for.
  * Numbers in an answer must come from a tool result. Each result carries provenance (source, as-of time,
    confidence, assumptions) so the UI can show "why this answer".
  * Tools never change anything. `propose_rebalance` only *proposes*; a human approves it separately.
"""
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain import scenario as sc
from app.schemas.parts import validate_part


class ToolError(Exception):
    """A failure the model can read and the user can be told about. The message is always safe to show."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@dataclass
class ToolResult:
    data: dict  # compact facts for the model to quote
    parts: list[dict] = field(default_factory=list)  # validated table/chart parts for the user
    provenance: dict = field(default_factory=dict)
    proposed_action: dict | None = None  # {type, payload, summary}: stored server-side, approved by a human


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")  # an unexpected argument is a mistake worth surfacing


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[_Args]
    tenants: frozenset[str]
    run: Callable[[BaseModel, date], ToolResult]


def _provenance(tool: str, source: str, today: date, confidence: str, assumptions: list[str], args: BaseModel) -> dict:
    return {
        "tool": tool,
        "source": source,
        "as_of": sc.AsOf(today).iso(),
        "confidence": confidence,
        "assumptions": assumptions,
        "inputs": args.model_dump(),
    }


def _good(part: dict) -> dict:
    valid = validate_part(part)
    if valid is None:  # a bug in a tool, not in the user's input
        raise ToolError("tool_failed", "The tool produced a result that could not be displayed.")
    return valid


# ----------------------------------------------------------------------------- get_demand_forecast
class ForecastArgs(_Args):
    sku: str = Field(pattern=r"^SKU-\d{4}$", description="SKU id such as SKU-1001")
    horizon_days: int = Field(default=14, ge=1, le=14, description="How many days ahead to cover")


def _require_sku(sku: str) -> None:
    if sku not in sc.SKUS:
        raise ToolError("unknown_sku", f"Unknown SKU {sku}. Known SKUs: {', '.join(sc.SKUS)}.")


def get_demand_forecast(args: ForecastArgs, today: date) -> ToolResult:
    _require_sku(args.sku)
    series = sc.forecast_series(args.sku, today)
    history = [p for p in series if "actual" in p]
    future = [p for p in series if "actual" not in p][: args.horizon_days]
    mape = round(100 * sum(abs(p["actual"] - p["forecast"]) / p["actual"] for p in history) / len(history), 1)
    next_total = sum(p["forecast"] for p in future)
    prior_total = sum(p["actual"] for p in history[-args.horizon_days :])
    change_pct = round(100 * (next_total / prior_total - 1), 1)
    promo = sc.PROMOS.get(args.sku)

    risks = []
    for row in sc.inventory_rows(sku=args.sku):
        if row["days_of_cover"] < args.horizon_days:
            risks.append({**row, "stockout_on": (today.fromordinal(today.toordinal() + int(row["days_of_cover"]))).isoformat()})
    risks.sort(key=lambda r: r["days_of_cover"])

    name = sc.SKUS[args.sku]["name"]
    chart = _good(
        {
            "type": "chart", "kind": "line", "title": f"{name}: forecast vs actual", "x": "date",
            "series": [{"key": "forecast", "label": "Forecast"}, {"key": "actual", "label": "Actual"}],
            "data": [{"date": p["date"], "forecast": p["forecast"], "actual": p.get("actual")} for p in series],
        }
    )
    parts = [chart]
    if risks:
        parts.append(
            _good(
                {
                    "type": "table", "title": f"Stock-out risk in the next {args.horizon_days} days",
                    "columns": ["Location", "On hand", "Daily demand", "Days of cover", "Runs out on"],
                    "rows": [[r["location"], r["on_hand"], r["daily_demand"], r["days_of_cover"], r["stockout_on"]] for r in risks],
                }
            )
        )
    assumptions = [
        "Cover assumes average daily demand and no inbound receipts that are not yet confirmed.",
        "Accuracy is the mean absolute percentage error of the last 14 days of forecast vs actual.",
    ]
    if promo:
        assumptions.append(f"Forecast includes {promo['label']} (+{int(promo['uplift'] * 100)}% on days {promo['from_day']}-{promo['to_day']}).")
    data = {
        "sku": args.sku, "name": name, "horizon_days": args.horizon_days,
        "forecast_units_next_period": next_total, "actual_units_prior_period": prior_total,
        "change_vs_prior_period_pct": change_pct, "forecast_error_mape_pct": mape,
        "promotion": promo["label"] if promo else None,
        "stockout_risks": [{"location": r["location"], "days_of_cover": r["days_of_cover"], "runs_out_on": r["stockout_on"]} for r in risks],
    }
    prov = _provenance("get_demand_forecast", "Northwind demand planning (demo data)", today, "high" if mape < 6 else "medium", assumptions, args)
    return ToolResult(data=data, parts=parts, provenance=prov)


# ----------------------------------------------------------------------------- get_inventory_position
class InventoryArgs(_Args):
    sku: str | None = Field(default=None, pattern=r"^SKU-\d{4}$")
    location: Literal["DC-1", "DC-2", "DC-5"] | None = None
    status: Literal["all", "short", "excess"] = Field(default="all", description="short: below 7 days of cover; excess: above 21")


def get_inventory_position(args: InventoryArgs, today: date) -> ToolResult:
    if args.sku:
        _require_sku(args.sku)
    rows = sc.inventory_rows(sku=args.sku, location=args.location)
    if args.status == "short":
        rows = [r for r in rows if r["days_of_cover"] < sc.TARGET_COVER_DAYS]
    elif args.status == "excess":
        rows = [r for r in rows if r["days_of_cover"] > sc.EXCESS_COVER_DAYS]
    rows.sort(key=lambda r: r["days_of_cover"], reverse=args.status == "excess")
    table = _good(
        {
            "type": "table", "title": "Inventory position",
            "columns": ["SKU", "Item", "Location", "On hand", "Daily demand", "Days of cover"],
            "rows": [[r["sku"], r["name"], r["location"], r["on_hand"], r["daily_demand"], r["days_of_cover"]] for r in rows],
        }
    )
    data = {
        "filter": args.model_dump(), "rows_returned": len(rows),
        "short_positions": [f"{r['sku']} at {r['location']} ({r['days_of_cover']} days)" for r in rows if r["days_of_cover"] < sc.TARGET_COVER_DAYS],
        "excess_positions": [f"{r['sku']} at {r['location']} ({r['days_of_cover']} days)" for r in rows if r["days_of_cover"] > sc.EXCESS_COVER_DAYS],
        "target_cover_days": sc.TARGET_COVER_DAYS, "excess_threshold_days": sc.EXCESS_COVER_DAYS,
        "rows": rows,
    }
    prov = _provenance(
        "get_inventory_position", "Northwind warehouse inventory (demo data)", today, "high",
        ["On hand excludes stock in transit.", f"Short means under {sc.TARGET_COVER_DAYS:g} days of cover; excess means over {sc.EXCESS_COVER_DAYS:g}."], args,
    )
    return ToolResult(data=data, parts=[table], provenance=prov)


# ----------------------------------------------------------------------------- list_at_risk_shipments
class AtRiskArgs(_Args):
    window_days: int = Field(default=7, ge=1, le=14, description="Only shipments whose SLA falls within this many days")


def list_at_risk_shipments(args: AtRiskArgs, today: date) -> ToolResult:
    rows = [s for s in sc.shipments(today) if s["days_until_sla"] <= args.window_days]
    flagged = [s for s in rows if s["hours_past_sla"] > 0 or (s["delay_hours"] > 0 and s["slack_hours_left"] <= 6)]
    flagged.sort(key=lambda s: (-s["hours_past_sla"], s["slack_hours_left"]))
    table = _good(
        {
            "type": "table", "title": f"Shipments at risk in the next {args.window_days} days",
            "columns": ["Shipment", "Lane", "Carrier", "Current ETA", "SLA due", "Hours past SLA", "Reason", "Cargo value (USD)"],
            "rows": [[s["id"], s["lane"], s["carrier"], s["current_eta"], s["sla_due"], s["hours_past_sla"], s["reason"], s["cargo_value_usd"]] for s in flagged],
        }
    )
    data = {
        "window_days": args.window_days, "shipments_in_window": len(rows), "at_risk_count": len(flagged),
        "breaching_sla": [s["id"] for s in flagged if s["hours_past_sla"] > 0],
        "cargo_value_at_risk_usd": sum(s["cargo_value_usd"] for s in flagged),
        "at_risk": flagged,
    }
    prov = _provenance(
        "list_at_risk_shipments", "Harbor transportation visibility feed (demo data)", today, "medium",
        ["Current ETA is the carrier's latest estimate and can still change.", "At risk means already past SLA, or delayed with 6 hours or less of slack left."], args,
    )
    return ToolResult(data=data, parts=[table], provenance=prov)


# ----------------------------------------------------------------------------- propose_rebalance
class RebalanceArgs(_Args):
    sku: str = Field(pattern=r"^SKU-\d{4}$")
    from_location: Literal["DC-1", "DC-2", "DC-5"]
    to_location: Literal["DC-1", "DC-2", "DC-5"]
    units: int = Field(ge=1, le=100000)


def propose_rebalance(args: RebalanceArgs, today: date) -> ToolResult:
    _require_sku(args.sku)
    if args.from_location == args.to_location:
        raise ToolError("invalid_arguments", "The source and destination must be different locations.")
    src = sc.inventory_rows(args.sku, args.from_location)[0]
    dst = sc.inventory_rows(args.sku, args.to_location)[0]
    movable = max(0, src["on_hand"] - round(sc.TARGET_COVER_DAYS * src["daily_demand"]))
    if args.units > movable:
        raise ToolError(
            "insufficient_surplus",
            f"{args.from_location} can release at most {movable} units of {args.sku} while keeping {sc.TARGET_COVER_DAYS:g} days of cover.",
        )
    after_src = round((src["on_hand"] - args.units) / src["daily_demand"], 1)
    after_dst = round((dst["on_hand"] + args.units) / dst["daily_demand"], 1)
    cost, co2 = round(args.units * 0.42), round(args.units * 0.011)
    summary = f"Move {args.units} units of {sc.SKUS[args.sku]['name']} from {args.from_location} to {args.to_location}"
    table = _good(
        {
            "type": "table", "title": "Proposed rebalance (not yet approved)",
            "columns": ["Location", "On hand now", "On hand after", "Days of cover now", "Days of cover after"],
            "rows": [
                [args.from_location, src["on_hand"], src["on_hand"] - args.units, src["days_of_cover"], after_src],
                [args.to_location, dst["on_hand"], dst["on_hand"] + args.units, dst["days_of_cover"], after_dst],
            ],
        }
    )
    payload = {"sku": args.sku, "from_location": args.from_location, "to_location": args.to_location, "units": args.units}
    data = {
        "proposal": summary, "estimated_cost_usd": cost, "estimated_co2e_kg": co2,
        "source_cover_after_days": after_src, "destination_cover_after_days": after_dst,
        "status": "proposed: nothing has been moved; a planner must approve it",
    }
    prov = _provenance(
        "propose_rebalance", "Northwind warehouse inventory (demo data)", today, "medium",
        ["Cost and carbon use flat demo rates per unit moved.", "The source keeps at least the target days of cover.", "No transfer happens until a planner approves."], args,
    )
    return ToolResult(data=data, parts=[table], provenance=prov, proposed_action={"type": "rebalance", "payload": payload, "summary": summary})


# ----------------------------------------------------------------------------- get_lane_cost_carbon
class LaneArgs(_Args):
    lane: Literal["Chicago-Dallas", "Atlanta-Miami", "Denver-Phoenix", "Seattle-Portland"]


def get_lane_cost_carbon(args: LaneArgs, today: date) -> ToolResult:
    options = sc.lane_options(args.lane)
    cheapest = min(options, key=lambda o: o["cost_usd"])
    greenest = min(options, key=lambda o: o["co2e_kg"])
    table = _good(
        {
            "type": "table", "title": f"{args.lane}: cost and carbon by mode",
            "columns": ["Mode", "Cost (USD)", "CO2e (kg)", "Transit days"],
            "rows": [[o["mode"], o["cost_usd"], o["co2e_kg"], o["transit_days"]] for o in options],
        }
    )
    chart = _good(
        {
            "type": "chart", "kind": "bar", "title": "CO2e by mode (kg)", "x": "mode",
            "series": [{"key": "co2e_kg", "label": "CO2e (kg)"}],
            "data": [{"mode": o["mode"], "co2e_kg": o["co2e_kg"]} for o in options],
        }
    )
    data = {"lane": args.lane, "miles": sc.LANES[args.lane]["miles"], "options": options,
            "cheapest": cheapest["mode"], "lowest_carbon": greenest["mode"]}
    prov = _provenance(
        "get_lane_cost_carbon", "Harbor rate card and emissions factors (demo data)", today, "medium",
        ["Costs use flat per-mile demo rates; no fuel surcharge or accessorials.", "Carbon is estimated from distance and mode, not measured."], args,
    )
    return ToolResult(data=data, parts=[table, chart], provenance=prov)


# ----------------------------------------------------------------------------- registry
RETAIL = frozenset({"northwind"})
LOGISTICS = frozenset({"harbor"})

TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool("get_demand_forecast", "Forecast vs actual demand for one SKU, plus stock-out risk by DC.", ForecastArgs, RETAIL, get_demand_forecast),
        Tool("get_inventory_position", "On-hand units and days of cover by SKU and DC; can filter short or excess positions.", InventoryArgs, RETAIL, get_inventory_position),
        Tool("propose_rebalance", "Propose (never perform) moving units of a SKU between DCs. A planner must approve.", RebalanceArgs, RETAIL, propose_rebalance),
        Tool("list_at_risk_shipments", "Shipments at risk of missing their SLA within a window.", AtRiskArgs, LOGISTICS, list_at_risk_shipments),
        Tool("get_lane_cost_carbon", "Cost, carbon and transit time by transport mode for one lane.", LaneArgs, LOGISTICS, get_lane_cost_carbon),
    ]
}


def tools_for(tenant_id: str) -> list[Tool]:
    return [t for t in TOOLS.values() if tenant_id in t.tenants]


def tool_specs(tenant_id: str) -> list[dict]:
    """The tools in the OpenAI function-calling format, limited to what this tenant may use."""
    specs = []
    for t in tools_for(tenant_id):
        schema = t.args_model.model_json_schema()
        schema.pop("title", None)
        specs.append({"type": "function", "function": {"name": t.name, "description": t.description, "parameters": schema}})
    return specs


def run_tool(tenant_id: str, name: str, raw_args: dict | str | None, today: date | None = None) -> ToolResult:
    """Validate and run one tool call for a tenant. Raises ToolError for anything the caller should report."""
    tool = TOOLS.get(name)
    if tool is None or tenant_id not in tool.tenants:
        # Same answer for "does not exist" and "belongs to another tenant": do not reveal what others can do.
        raise ToolError("unknown_tool", f"There is no tool called {name} available for this company.")
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError:
            raise ToolError("invalid_arguments", "The tool arguments were not valid JSON.") from None
    if raw_args is None:
        raw_args = {}
    if not isinstance(raw_args, dict):
        raise ToolError("invalid_arguments", "The tool arguments must be a JSON object.")
    try:
        args = tool.args_model.model_validate(raw_args)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in exc.errors()[:4])
        raise ToolError("invalid_arguments", f"Invalid arguments for {name}: {problems}") from None
    return tool.run(args, today or sc.utc_today())
