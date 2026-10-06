import json
from datetime import date

import pytest

from app.domain import scenario as sc
from app.domain.tools import TOOLS, ToolError, run_tool, tool_specs, tools_for
from app.schemas.parts import validate_part

TODAY = date(2026, 10, 6)  # a Tuesday; tests never depend on the real clock


def run(tenant, name, args=None):
    return run_tool(tenant, name, args, today=TODAY)


# ------------------------------------------------------------------ tenant scoping
def test_each_company_is_offered_only_its_own_tools():
    assert {t.name for t in tools_for("northwind")} == {"get_demand_forecast", "get_inventory_position", "propose_rebalance"}
    assert {t.name for t in tools_for("harbor")} == {"list_at_risk_shipments", "get_lane_cost_carbon"}
    assert tools_for("nobody") == [] and tool_specs("nobody") == []


def test_a_tool_of_another_company_looks_exactly_like_a_tool_that_does_not_exist():
    with pytest.raises(ToolError) as other:
        run("northwind", "list_at_risk_shipments", {})
    with pytest.raises(ToolError) as missing:
        run("northwind", "no_such_tool", {})
    assert other.value.code == missing.value.code == "unknown_tool"
    assert "list_at_risk_shipments" in other.value.message  # echoes the name the caller sent, nothing about other tenants
    assert "harbor" not in other.value.message.lower()


def test_specs_are_openai_function_schemas_without_leaking_other_tenants_tools():
    specs = tool_specs("harbor")
    assert [s["function"]["name"] for s in specs] == ["list_at_risk_shipments", "get_lane_cost_carbon"]
    for s in specs:
        assert s["type"] == "function" and s["function"]["parameters"]["type"] == "object"
        assert s["function"]["parameters"].get("additionalProperties") is False  # unknown arguments are rejected


# ------------------------------------------------------------------ argument validation
@pytest.mark.parametrize(
    "name,args",
    [
        ("get_demand_forecast", {}),  # missing sku
        ("get_demand_forecast", {"sku": "milk"}),  # wrong format
        ("get_demand_forecast", {"sku": "SKU-1001", "horizon_days": 99}),
        ("get_demand_forecast", {"sku": "SKU-1001", "surprise": 1}),  # unexpected argument
        ("get_inventory_position", {"location": "DC-9"}),
        ("propose_rebalance", {"sku": "SKU-1001", "from_location": "DC-2", "to_location": "DC-5", "units": 0}),
        ("propose_rebalance", {"sku": "SKU-1001", "from_location": "DC-2", "to_location": "DC-5", "units": "lots"}),
    ],
)
def test_invalid_arguments_are_a_clear_tool_error_not_a_crash(name, args):
    with pytest.raises(ToolError) as exc:
        run("northwind", name, args)
    assert exc.value.code == "invalid_arguments"


def test_arguments_may_arrive_as_a_json_string_like_real_models_send_them():
    r = run("northwind", "get_demand_forecast", json.dumps({"sku": "SKU-1001"}))
    assert r.data["sku"] == "SKU-1001"
    assert run("northwind", "get_inventory_position", "").data["rows_returned"] == 24  # empty string means no arguments
    for bad in ("{not json", "[1, 2]", "42"):
        with pytest.raises(ToolError) as exc:
            run("northwind", "get_inventory_position", bad)
        assert exc.value.code == "invalid_arguments"


def test_an_unknown_sku_is_reported_with_the_valid_choices():
    with pytest.raises(ToolError) as exc:
        run("northwind", "get_demand_forecast", {"sku": "SKU-9999"})
    assert exc.value.code == "unknown_sku" and "SKU-1001" in exc.value.message


# ------------------------------------------------------------------ results, provenance, parts
def test_every_tool_returns_valid_parts_and_complete_provenance():
    calls = {
        "northwind": [("get_demand_forecast", {"sku": "SKU-1007"}), ("get_inventory_position", {}), ("propose_rebalance", {"sku": "SKU-1006", "from_location": "DC-2", "to_location": "DC-5", "units": 500})],
        "harbor": [("list_at_risk_shipments", {}), ("get_lane_cost_carbon", {"lane": "Chicago-Dallas"})],
    }
    for tenant, items in calls.items():
        for name, args in items:
            r = run(tenant, name, args)
            assert r.parts, name
            assert all(validate_part(p) == p for p in r.parts), name  # already in canonical, valid form
            p = r.provenance
            assert p["tool"] == name and p["source"] and p["assumptions"] and p["confidence"] in {"high", "medium", "low"}
            assert p["as_of"] == "2026-10-06T06:00:00Z" and p["inputs"]


def test_results_are_deterministic_for_a_given_date():
    assert run("harbor", "list_at_risk_shipments", {}).data == run("harbor", "list_at_risk_shipments", {}).data
    assert run("northwind", "get_demand_forecast", {"sku": "SKU-1002"}).data == run("northwind", "get_demand_forecast", {"sku": "SKU-1002"}).data


def test_forecast_shows_the_deliberate_stockout_and_the_promotion():
    milk = run("northwind", "get_demand_forecast", {"sku": "SKU-1001"}).data
    assert [r["location"] for r in milk["stockout_risks"]][0] == "DC-5"  # 2.1 days of cover
    pizza = run("northwind", "get_demand_forecast", {"sku": "SKU-1007"})
    assert pizza.data["promotion"] == "Weekend pizza promotion" and pizza.data["change_vs_prior_period_pct"] > 5
    assert any("promotion" in a.lower() for a in pizza.provenance["assumptions"])


def test_forecast_chart_has_gaps_for_future_actuals_not_made_up_numbers():
    chart = run("northwind", "get_demand_forecast", {"sku": "SKU-1001"}).parts[0]
    assert chart["type"] == "chart" and len(chart["data"]) == 28
    past, future = chart["data"][:14], chart["data"][14:]
    assert all(p["actual"] is not None for p in past)
    assert all(p["actual"] is None for p in future)


def test_inventory_filters_find_the_short_and_excess_positions():
    short = run("northwind", "get_inventory_position", {"status": "short"}).data
    assert short["rows_returned"] > 0 and all(r["days_of_cover"] < 7 for r in short["rows"])
    assert short["rows"][0]["days_of_cover"] == min(r["days_of_cover"] for r in short["rows"])  # worst first
    excess = run("northwind", "get_inventory_position", {"status": "excess"}).data
    assert any("SKU-1006 at DC-2" in e for e in excess["excess_positions"])
    one = run("northwind", "get_inventory_position", {"sku": "SKU-1001", "location": "DC-5"}).data
    assert one["rows_returned"] == 1


def test_at_risk_shipments_lead_with_the_worst_and_respect_the_window():
    wide = run("harbor", "list_at_risk_shipments", {"window_days": 14}).data
    assert wide["breaching_sla"] and wide["at_risk"][0]["hours_past_sla"] == max(s["hours_past_sla"] for s in wide["at_risk"])
    assert wide["cargo_value_at_risk_usd"] == sum(s["cargo_value_usd"] for s in wide["at_risk"])
    narrow = run("harbor", "list_at_risk_shipments", {"window_days": 1}).data
    assert narrow["shipments_in_window"] < wide["shipments_in_window"]
    assert all(s["days_until_sla"] <= 1 for s in narrow["at_risk"])


def test_lane_tool_reports_cost_and_carbon_side_by_side():
    r = run("harbor", "get_lane_cost_carbon", {"lane": "Chicago-Dallas"})
    assert r.data["cheapest"] == "Intermodal rail" and r.data["lowest_carbon"] == "Intermodal rail"
    assert {o["mode"] for o in r.data["options"]} == set(sc.MODES)
    with pytest.raises(ToolError):
        run("harbor", "get_lane_cost_carbon", {"lane": "Mars-Venus"})


# ------------------------------------------------------------------ propose_rebalance guardrails
def test_a_rebalance_is_only_a_proposal_and_never_changes_the_data():
    before = sc.inventory_rows("SKU-1006")
    r = run("northwind", "propose_rebalance", {"sku": "SKU-1006", "from_location": "DC-2", "to_location": "DC-5", "units": 500})
    assert r.proposed_action == {
        "type": "rebalance",
        "payload": {"sku": "SKU-1006", "from_location": "DC-2", "to_location": "DC-5", "units": 500},
        "summary": "Move 500 units of Pasta 500g from DC-2 to DC-5",
    }
    assert "nothing has been moved" in r.data["status"]
    assert sc.inventory_rows("SKU-1006") == before


def test_a_rebalance_cannot_strip_the_source_below_target_cover():
    with pytest.raises(ToolError) as exc:
        run("northwind", "propose_rebalance", {"sku": "SKU-1001", "from_location": "DC-5", "to_location": "DC-1", "units": 100})
    assert exc.value.code == "insufficient_surplus" and "at most 0" in exc.value.message


def test_a_rebalance_to_the_same_place_is_rejected():
    with pytest.raises(ToolError) as exc:
        run("northwind", "propose_rebalance", {"sku": "SKU-1006", "from_location": "DC-2", "to_location": "DC-2", "units": 10})
    assert exc.value.code == "invalid_arguments"


def test_no_tool_is_registered_without_a_tenant():
    assert all(t.tenants for t in TOOLS.values())
