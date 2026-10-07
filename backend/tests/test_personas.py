from datetime import date

from app.domain.personas import PERSONAS, effective_persona, get_persona, personas_for
from app.domain.prompt import copilot_prompt


async def test_each_company_lists_only_its_own_personas_with_the_default_selected(client, register_user):
    n = await register_user("n@x.com", tenant_id="northwind")
    h = await register_user("h@x.com", tenant_id="harbor")
    pn = (await client.get("/api/v1/personas", headers=n["headers"])).json()
    ph = (await client.get("/api/v1/personas", headers=h["headers"])).json()
    assert [p["id"] for p in pn] == ["demand_planner", "dc_manager"]
    assert [p["id"] for p in ph] == ["transport_planner"]
    assert [p["id"] for p in pn if p["selected"]] == ["demand_planner"]  # default for the company
    assert all(len(p["starters"]) == 3 for p in pn + ph)


async def test_choosing_a_persona_is_saved_and_reflected(client, register_user):
    a = await register_user("a@x.com", tenant_id="northwind")
    r = await client.patch("/api/v1/me/settings", json={"persona": "dc_manager"}, headers=a["headers"])
    assert r.status_code == 200 and r.json()["persona"] == "dc_manager"
    assert (await client.get("/api/v1/me", headers=a["headers"])).json()["persona"] == "dc_manager"
    sel = [p["id"] for p in (await client.get("/api/v1/personas", headers=a["headers"])).json() if p["selected"]]
    assert sel == ["dc_manager"]


async def test_another_companys_or_an_unknown_persona_is_rejected(client, register_user):
    a = await register_user("a@x.com", tenant_id="northwind")
    for bad in ("transport_planner", "wizard", ""):
        r = await client.patch("/api/v1/me/settings", json={"persona": bad}, headers=a["headers"])
        assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_persona"
    assert (await client.get("/api/v1/me", headers=a["headers"])).json()["persona"] is None  # nothing was saved


async def test_personas_and_settings_need_sign_in(client):
    assert (await client.get("/api/v1/personas")).status_code == 401
    assert (await client.patch("/api/v1/me/settings", json={"persona": "dc_manager"})).status_code == 401


def test_a_stale_choice_falls_back_to_the_companys_default():
    assert effective_persona("transport_planner", "northwind").id == "demand_planner"
    assert effective_persona(None, "harbor").id == "transport_planner"
    assert effective_persona("x", "nobody") is None


def test_every_persona_has_prompt_focus_and_starters_and_belongs_to_a_known_company():
    assert {p.tenant_id for p in PERSONAS} == {"northwind", "harbor"}
    for p in PERSONAS:
        assert p.focus and p.starters and get_persona(p.id, p.tenant_id) is p
    assert len(personas_for("northwind")) == 2


def test_the_persona_focus_reaches_the_system_prompt_without_dropping_the_trust_rules():
    base = copilot_prompt("Northwind Grocers", "Grocery retail", date(2026, 10, 7))
    with_focus = copilot_prompt("Northwind Grocers", "Grocery retail", date(2026, 10, 7), get_persona("dc_manager", "northwind").focus)
    assert "Who you are helping" not in base
    assert "Who you are helping: The user manages distribution centres" in with_focus
    assert "Never estimate, invent or recall figures" in with_focus


async def test_the_chat_uses_the_users_persona_in_the_system_prompt(client, register_user):
    from app.llm.factory import get_llm_provider
    from app.llm.mock import MockProvider
    from app.main import app
    from tests.test_chat_stream import _conversation, _send

    seen = []

    class Recorder(MockProvider):
        async def stream(self, messages, *, system=None, **kw):
            seen.append(system)
            async for e in super().stream(messages, system=system, **kw):
                yield e

    app.dependency_overrides[get_llm_provider] = lambda: Recorder()
    a = await register_user("a@x.com", tenant_id="northwind")
    c = await _conversation(client, a["headers"])
    await _send(client, a["headers"], c["id"], "hi")
    assert "demand planner" in seen[-1]  # the default for Northwind
    await client.patch("/api/v1/me/settings", json={"persona": "dc_manager"}, headers=a["headers"])
    await _send(client, a["headers"], c["id"], "hi again")
    assert "distribution centres" in seen[-1] and "demand planner" not in seen[-1]


def test_the_prompt_lists_the_ids_the_tools_expect_for_each_company_and_never_the_others():
    nw = copilot_prompt("Northwind Grocers", "Grocery retail", date(2026, 10, 7), "", "northwind")
    hb = copilot_prompt("Harbor Freight Lines", "Regional logistics", date(2026, 10, 7), "", "harbor")
    assert "SKU-1007 = Frozen Pizza" in nw and "DC-5 = West DC" in nw and "Chicago-Dallas" not in nw
    assert "Chicago-Dallas" in hb and "SKU-1007" not in hb and "DC-5" not in hb
    assert "SKU-1007" not in copilot_prompt("X", "Y", date(2026, 10, 7))  # no tenant, no catalog


def test_every_id_in_the_catalog_is_accepted_by_the_tools():
    from app.domain import scenario as sc
    from app.domain.tools import run_tool

    for sku in sc.SKUS:
        assert run_tool("northwind", "get_demand_forecast", {"sku": sku}, today=date(2026, 10, 7)).data["sku"] == sku
    for lane in sc.LANES:
        assert run_tool("harbor", "get_lane_cost_carbon", {"lane": lane}, today=date(2026, 10, 7)).data["lane"] == lane


async def test_the_chat_gives_the_model_the_catalog_of_the_users_company(client, register_user):
    from app.llm.factory import get_llm_provider
    from app.llm.mock import MockProvider
    from app.main import app
    from tests.test_chat_stream import _conversation, _send

    seen = []

    class Recorder(MockProvider):
        async def stream(self, messages, *, system=None, **kw):
            seen.append(system)
            async for e in super().stream(messages, system=system, **kw):
                yield e

    app.dependency_overrides[get_llm_provider] = lambda: Recorder()
    for tenant, email, expect, absent in (("northwind", "n@x.com", "SKU-1007 = Frozen Pizza", "Seattle-Portland"), ("harbor", "h@x.com", "Seattle-Portland", "SKU-1007")):
        u = await register_user(email, tenant_id=tenant)
        c = await _conversation(client, u["headers"])
        await _send(client, u["headers"], c["id"], "hi")
        assert expect in seen[-1] and absent not in seen[-1]
