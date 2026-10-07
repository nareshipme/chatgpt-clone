import asyncio
import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from tests.test_chat_stream import _conversation, _send, _thread, parse_sse

PROPOSE = '[tool:propose_rebalance {"sku": "SKU-1006", "from_location": "DC-2", "to_location": "DC-5", "units": 500}]'


async def _propose(client, headers):
    c = await _conversation(client, headers)
    res = await _send(client, headers, c["id"], PROPOSE)
    frames = parse_sse(res.text)
    proposal = next(d for e, d in frames if e == "part" and d["type"] == "proposal")
    return c, frames, proposal


async def _sql(migrated_db, statement, **params):
    engine = create_async_engine(migrated_db)
    async with engine.begin() as conn:
        await conn.execute(text(statement), params)
    await engine.dispose()


async def _audit(client, headers):
    return (await client.get("/api/v1/audit", headers=headers)).json()["items"]


# ------------------------------------------------------------------ proposing
async def test_a_rebalance_in_chat_becomes_a_proposal_card_backed_by_a_server_side_action(client, register_user):
    a = await register_user("a@x.com", tenant_id="northwind")
    c, frames, proposal = await _propose(client, a["headers"])
    assert set(proposal) == {"type", "action_id", "action_type", "summary"}  # the card carries an id, not the payload
    assert proposal["summary"] == "Move 500 units of Pasta 500g from DC-2 to DC-5"
    saved = (await _thread(client, a["headers"], c["id"]))[1]
    assert [p["type"] for p in saved["parts"]] == ["text", "table", "proposal", "text"]
    action = (await client.get(f"/api/v1/actions/{proposal['action_id']}", headers=a["headers"])).json()
    assert action["status"] == "proposed" and action["can_decide"] is True
    assert action["payload"] == {"sku": "SKU-1006", "from_location": "DC-2", "to_location": "DC-5", "units": 500}
    assert [e["action"] for e in await _audit(client, a["headers"])] == ["action.proposed"]


# ------------------------------------------------------------------ approving
async def test_approving_records_who_and_what_and_carries_out_a_simulated_effect(client, register_user):
    a = await register_user("a@x.com", tenant_id="northwind")
    _, _, proposal = await _propose(client, a["headers"])
    r = await client.post(f"/api/v1/actions/{proposal['action_id']}/execute", headers=a["headers"])
    body = r.json()
    assert r.status_code == 200 and body["status"] == "approved" and body["decided_at"]
    assert body["result"]["simulated"] is True and "no real warehouse" in body["result"]["note"]
    # the effect is computed from the data (pasta: DC-2 had 41 days of cover, DC-5 had 18), not invented
    assert body["result"]["source_cover_after_days"] < 41 and body["result"]["destination_cover_after_days"] > 18
    assert body["can_decide"] is False
    events = await _audit(client, a["headers"])
    assert [e["action"] for e in events] == ["action.approved", "action.proposed"]  # newest first
    assert events[0]["actor_name"] == "Test User" and events[0]["payload"]["payload"]["units"] == 500


async def test_approving_twice_is_idempotent_and_audits_once(client, register_user):
    a = await register_user("a@x.com", tenant_id="northwind")
    _, _, proposal = await _propose(client, a["headers"])
    url = f"/api/v1/actions/{proposal['action_id']}/execute"
    first = (await client.post(url, headers=a["headers"])).json()
    second = await client.post(url, headers=a["headers"])
    assert second.status_code == 200 and second.json()["decided_at"] == first["decided_at"]
    assert [e["action"] for e in await _audit(client, a["headers"])].count("action.approved") == 1


async def test_two_simultaneous_approvals_produce_one_approval(client, register_user):
    a = await register_user("a@x.com", tenant_id="northwind")
    _, _, proposal = await _propose(client, a["headers"])
    url = f"/api/v1/actions/{proposal['action_id']}/execute"
    results = await asyncio.gather(client.post(url, headers=a["headers"]), client.post(url, headers=a["headers"]))
    assert [r.status_code for r in results] == [200, 200] and {r.json()["status"] for r in results} == {"approved"}
    assert [e["action"] for e in await _audit(client, a["headers"])].count("action.approved") == 1


async def test_the_client_cannot_change_what_is_approved(client, register_user):
    a = await register_user("a@x.com", tenant_id="northwind")
    _, _, proposal = await _propose(client, a["headers"])
    r = await client.post(
        f"/api/v1/actions/{proposal['action_id']}/execute", headers=a["headers"],
        json={"payload": {"sku": "SKU-1001", "from_location": "DC-1", "to_location": "DC-5", "units": 99999}, "units": 99999},
    )
    assert r.status_code == 200 and r.json()["payload"]["units"] == 500 and r.json()["payload"]["sku"] == "SKU-1006"


# ------------------------------------------------------------------ dismissing and conflicts
async def test_dismissing_ends_the_proposal_and_blocks_a_later_approval(client, register_user):
    a = await register_user("a@x.com", tenant_id="northwind")
    _, _, proposal = await _propose(client, a["headers"])
    base = f"/api/v1/actions/{proposal['action_id']}"
    d = await client.post(f"{base}/dismiss", headers=a["headers"])
    assert d.status_code == 200 and d.json()["status"] == "dismissed" and d.json()["result"] is None
    late = await client.post(f"{base}/execute", headers=a["headers"])
    assert late.status_code == 409 and late.json()["error"]["code"] == "action_not_pending"
    assert (await client.post(f"{base}/dismiss", headers=a["headers"])).status_code == 200  # dismissing again is harmless
    assert [e["action"] for e in await _audit(client, a["headers"])] == ["action.dismissed", "action.proposed"]


async def test_an_approved_action_cannot_be_dismissed(client, register_user):
    a = await register_user("a@x.com", tenant_id="northwind")
    _, _, proposal = await _propose(client, a["headers"])
    base = f"/api/v1/actions/{proposal['action_id']}"
    await client.post(f"{base}/execute", headers=a["headers"])
    r = await client.post(f"{base}/dismiss", headers=a["headers"])
    assert r.status_code == 409 and "already approved" in r.json()["error"]["message"]


# ------------------------------------------------------------------ isolation and roles
async def test_another_company_gets_404_for_read_approve_and_dismiss(client, register_user):
    a = await register_user("a@x.com", tenant_id="northwind")
    h = await register_user("h@x.com", tenant_id="harbor")
    _, _, proposal = await _propose(client, a["headers"])
    base = f"/api/v1/actions/{proposal['action_id']}"
    for call in (client.get(base, headers=h["headers"]), client.post(f"{base}/execute", headers=h["headers"]), client.post(f"{base}/dismiss", headers=h["headers"])):
        r = await call
        assert r.status_code == 404 and r.json()["error"]["code"] == "action_not_found"
    assert (await client.get(base, headers=a["headers"])).json()["status"] == "proposed"  # untouched


async def test_a_viewer_can_read_but_not_decide_or_read_the_audit(client, register_user, migrated_db):
    a = await register_user("a@x.com", tenant_id="northwind")
    _, _, proposal = await _propose(client, a["headers"])
    await _sql(migrated_db, "UPDATE users SET role = 'viewer' WHERE email = 'a@x.com'")
    base = f"/api/v1/actions/{proposal['action_id']}"
    got = (await client.get(base, headers=a["headers"])).json()
    assert got["status"] == "proposed" and got["can_decide"] is False  # the UI hides what the server would refuse
    for path in ("execute", "dismiss"):
        r = await client.post(f"{base}/{path}", headers=a["headers"])
        assert r.status_code == 403 and r.json()["error"]["code"] == "role_not_allowed"
    assert (await client.get("/api/v1/audit", headers=a["headers"])).status_code == 403
    assert (await client.get(base, headers=a["headers"])).json()["status"] == "proposed"


async def test_the_audit_log_is_tenant_scoped_authenticated_and_read_only(client, register_user):
    a = await register_user("a@x.com", tenant_id="northwind")
    h = await register_user("h@x.com", tenant_id="harbor")
    await _propose(client, a["headers"])
    assert len(await _audit(client, a["headers"])) == 1
    assert await _audit(client, h["headers"]) == []  # nothing from the other company
    assert (await client.get("/api/v1/audit")).status_code == 401
    for method in ("delete", "put", "patch", "post"):
        assert (await getattr(client, method)("/api/v1/audit", headers=a["headers"])).status_code in (404, 405)
    assert (await client.get("/api/v1/audit?limit=0", headers=a["headers"])).status_code == 422


# ------------------------------------------------------------------ expiry and re-validation
async def test_an_overdue_proposal_expires_once_and_cannot_be_approved(client, register_user, monkeypatch):
    monkeypatch.setattr(settings, "action_expiry_minutes", -1)
    a = await register_user("a@x.com", tenant_id="northwind")
    _, _, proposal = await _propose(client, a["headers"])
    base = f"/api/v1/actions/{proposal['action_id']}"
    assert (await client.get(base, headers=a["headers"])).json()["status"] == "expired"
    r = await client.post(f"{base}/execute", headers=a["headers"])
    assert r.status_code == 409 and "expired" in r.json()["error"]["message"]
    assert [e["action"] for e in await _audit(client, a["headers"])].count("action.expired") == 1


async def test_approval_rechecks_the_proposal_against_the_data_as_it_is_now(client, register_user, migrated_db):
    a = await register_user("a@x.com", tenant_id="northwind")
    _, _, proposal = await _propose(client, a["headers"])
    # simulate the world changing (or a corrupted row): the stored move is now bigger than the source can release
    bad = json.dumps({"sku": "SKU-1006", "from_location": "DC-2", "to_location": "DC-5", "units": 90000})
    await _sql(migrated_db, "UPDATE proposed_actions SET payload = :p", p=bad)
    r = await client.post(f"/api/v1/actions/{proposal['action_id']}/execute", headers=a["headers"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "action_no_longer_valid"
    assert (await client.get(f"/api/v1/actions/{proposal['action_id']}", headers=a["headers"])).json()["status"] == "proposed"
    assert "action.approved" not in [e["action"] for e in await _audit(client, a["headers"])]


# ------------------------------------------------------------------ basics
async def test_actions_need_sign_in_and_a_valid_id(client, register_user):
    import uuid

    assert (await client.get(f"/api/v1/actions/{uuid.uuid4()}")).status_code == 401
    a = await register_user("a@x.com")
    assert (await client.get(f"/api/v1/actions/{uuid.uuid4()}", headers=a["headers"])).status_code == 404
    assert (await client.get("/api/v1/actions/not-a-uuid", headers=a["headers"])).status_code == 422


@pytest.mark.parametrize("name", ["execute", "dismiss"])
async def test_the_other_companys_tool_cannot_create_a_proposal(client, register_user, name):
    h = await register_user("h@x.com", tenant_id="harbor")
    c = await _conversation(client, h["headers"])
    res = await _send(client, h["headers"], c["id"], PROPOSE)  # propose_rebalance is a Northwind tool
    frames = parse_sse(res.text)
    assert "proposal" not in json.dumps([d for e, d in frames if e == "part"])
    assert await _audit(client, h["headers"]) == []


async def test_a_stale_read_cannot_double_approve_the_claim_is_atomic(client, register_user, migrated_db, monkeypatch):
    """Forces the race: requests 2 and 3 read the action as 'proposed' before request 1 approved it. Only the guarded
    UPDATE ... WHERE status = 'proposed' stops them from deciding (and auditing) again."""
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models import ProposedAction, User
    from app.services import action_service

    a = await register_user("a@x.com", tenant_id="northwind")
    _, _, proposal = await _propose(client, a["headers"])
    action_id, user_id = uuid.UUID(proposal["action_id"]), uuid.UUID(a["user"]["id"])
    engine = create_async_engine(migrated_db)
    async with AsyncSession(engine, expire_on_commit=False) as s1, AsyncSession(engine, expire_on_commit=False) as s2, AsyncSession(engine, expire_on_commit=False) as s3:
        u1, u2, u3 = await s1.get(User, user_id), await s2.get(User, user_id), await s3.get(User, user_id)
        stale_for_2, stale_for_3 = await s2.get(ProposedAction, action_id), await s3.get(ProposedAction, action_id)
        assert stale_for_2.status == stale_for_3.status == "proposed"
        await action_service.decide(s1, u1, action_id, "approved")  # request 1 wins

        stale = iter([stale_for_2, stale_for_3])

        async def fake_get_visible(session, user, aid):
            return next(stale)  # these requests still believe the action is pending

        monkeypatch.setattr(action_service, "get_visible", fake_get_visible)
        again = await action_service.decide(s2, u2, action_id, "approved")  # same decision: returns the winner's result
        assert again.status == "approved"
        await s2.commit()  # SQLite keeps its write lock until the transaction ends (Postgres would not)
        with pytest.raises(action_service.ActionNotPendingError):  # the opposite decision loses the same race
            await action_service.decide(s3, u3, action_id, "dismissed")
    await engine.dispose()
    events = [e["action"] for e in await _audit(client, a["headers"])]
    assert events.count("action.approved") == 1 and "action.dismissed" not in events
