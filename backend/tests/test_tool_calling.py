import json

from app.config import settings
from app.llm.base import TextDelta, ToolCall, Usage
from app.llm.factory import get_llm_provider
from app.llm.mock import MockProvider
from app.main import app

from tests.test_chat_stream import _conversation, _send, _thread, parse_sse

NORTHWIND = "northwind"
HARBOR = "harbor"


async def _ask(client, register_user, text, tenant=HARBOR, email="a@example.com"):
    a = await register_user(email, tenant_id=tenant)
    c = await _conversation(client, a["headers"])
    res = await _send(client, a["headers"], c["id"], text)
    return a, c, parse_sse(res.text)


# ------------------------------------------------------------------ the happy path
async def test_a_tool_call_streams_status_then_its_table_then_the_answer_and_is_saved(client, register_user):
    a, c, frames = await _ask(client, register_user, "what is at risk? [tool:list_at_risk_shipments]")
    names = [e for e, _ in frames]
    assert names[0] == "start" and names[-1] == "done"
    tool_events = [d for e, d in frames if e == "tool"]
    assert [t["status"] for t in tool_events] == ["running", "done"]
    assert tool_events[0]["name"] == "list_at_risk_shipments"
    # the table arrives between the two tool statuses, before the model's closing words
    assert names.index("tool") < names.index("part") < len(names) - 1
    assert [d["type"] for e, d in frames if e == "part"] == ["table"]

    saved = (await _thread(client, a["headers"], c["id"]))[1]
    assert [p["type"] for p in saved["parts"]] == ["text", "table", "text"]
    assert saved["parts"][0]["text"] == "Let me check. "
    assert saved["parts"][1]["title"].startswith("Shipments at risk")


async def test_provenance_is_saved_on_the_message_but_never_streamed(client, register_user):
    a, c, frames = await _ask(client, register_user, "[tool:list_at_risk_shipments]")
    assert all("provenance" not in json.dumps(d) for e, d in frames if e == "tool")
    meta = (await _thread(client, a["headers"], c["id"]))[1]["meta"]
    [prov] = meta["provenance"]
    assert prov["tool"] == "list_at_risk_shipments" and prov["assumptions"] and prov["as_of"].endswith("Z")
    assert prov["inputs"] == {"window_days": 7}  # the defaults that were actually applied


async def test_arguments_from_the_model_are_validated_and_applied(client, register_user):
    a, c, frames = await _ask(client, register_user, '[tool:list_at_risk_shipments {"window_days": 1}]')
    meta = (await _thread(client, a["headers"], c["id"]))[1]["meta"]
    assert meta["provenance"][0]["inputs"] == {"window_days": 1}


async def test_a_plain_message_makes_no_tool_call_and_has_no_meta(client, register_user):
    a, c, frames = await _ask(client, register_user, "hello there")
    assert "tool" not in [e for e, _ in frames]
    assert (await _thread(client, a["headers"], c["id"]))[1]["meta"] is None


# ------------------------------------------------------------------ guardrails
async def test_a_company_cannot_run_another_companys_tool(client, register_user):
    a, c, frames = await _ask(client, register_user, "[tool:list_at_risk_shipments]", tenant=NORTHWIND)
    tool_events = [d for e, d in frames if e == "tool"]
    assert [t["status"] for t in tool_events] == ["running", "error"]
    assert "part" not in [e for e, _ in frames]  # no data came back
    assert frames[-1][0] == "done"  # the reply still finishes, telling the user what happened
    saved = (await _thread(client, a["headers"], c["id"]))[1]
    assert all(p["type"] == "text" for p in saved["parts"]) and saved["meta"] is None


async def test_bad_tool_arguments_are_reported_not_crashed_on(client, register_user):
    a, c, frames = await _ask(client, register_user, '[tool:get_lane_cost_carbon {"lane": "Mars-Venus"}]')
    errors = [d for e, d in frames if e == "tool" and d["status"] == "error"]
    assert errors and "lane" in errors[0]["message"]
    assert frames[-1][0] == "done"


async def test_the_model_is_given_only_its_companys_tools_and_a_company_specific_prompt(client, register_user):
    seen = []

    class Recorder(MockProvider):
        async def stream(self, messages, *, tools=None, system=None, **kw):
            seen.append({"tools": [t["function"]["name"] for t in tools or []], "system": system})
            async for e in super().stream(messages, tools=tools, system=system, **kw):
                yield e

    app.dependency_overrides[get_llm_provider] = lambda: Recorder()
    await _ask(client, register_user, "hi", tenant=HARBOR)
    assert seen[0]["tools"] == ["list_at_risk_shipments", "get_lane_cost_carbon"]
    assert "Harbor Freight Lines" in seen[0]["system"] and "Regional logistics" in seen[0]["system"]
    assert "Never estimate, invent or recall figures" in seen[0]["system"]
    seen.clear()
    await _ask(client, register_user, "hi", tenant=NORTHWIND, email="b@example.com")
    assert "propose_rebalance" in seen[0]["tools"] and "list_at_risk_shipments" not in seen[0]["tools"]
    assert "Northwind Grocers" in seen[0]["system"]


# ------------------------------------------------------------------ the loop
async def test_the_loop_is_bounded_and_the_last_round_withholds_tools(client, register_user, monkeypatch):
    monkeypatch.setattr(settings, "llm_max_tool_rounds", 2)
    offered = []
    last_messages = []

    class Greedy:
        name = "greedy"

        async def stream(self, messages, *, tools=None, **kw):
            offered.append(bool(tools))
            last_messages[:] = messages
            if tools:
                yield ToolCall(f"c{len(offered)}", "get_lane_cost_carbon", '{"lane": "Chicago-Dallas"}')
            else:
                yield TextDelta("Final answer from what I have.")
            yield Usage(5, 7)

    app.dependency_overrides[get_llm_provider] = lambda: Greedy()
    a, c, frames = await _ask(client, register_user, "keep going")
    assert offered == [True, True, False]  # two tool rounds, then a forced answer
    assert last_messages[-1].role == "user" and "Do not call any more tools" in last_messages[-1].content  # told to answer now
    assert frames[-1][0] == "done" and frames[-1][1]["tokens_in"] == 15 and frames[-1][1]["tokens_out"] == 21  # summed over rounds
    saved = (await _thread(client, a["headers"], c["id"]))[1]
    assert saved["parts"][-1] == {"type": "text", "text": "Final answer from what I have."}
    assert len(saved["meta"]["provenance"]) == 2


async def test_the_model_sees_the_tool_result_not_the_tables_and_can_recover_from_an_error(client, register_user):
    transcripts = []

    class Learner:
        name = "learner"

        async def stream(self, messages, *, tools=None, **kw):
            transcripts.append([(m.role, m.content[:60], bool(m.tool_calls), m.tool_call_id) for m in messages])
            last = messages[-1]
            if last.role == "user":
                yield ToolCall("bad1", "get_lane_cost_carbon", '{"lane": "nowhere"}')
            elif last.role == "tool" and last.tool_call_id == "bad1":
                yield ToolCall("good1", "get_lane_cost_carbon", '{"lane": "Atlanta-Miami"}')
            else:
                yield TextDelta("Rail is cheapest and greenest.")

    app.dependency_overrides[get_llm_provider] = lambda: Learner()
    a, c, frames = await _ask(client, register_user, "compare modes")
    statuses = [(d["id"], d["status"]) for e, d in frames if e == "tool"]
    assert statuses == [("bad1", "running"), ("bad1", "error"), ("good1", "running"), ("good1", "done")]
    second = transcripts[1]
    assert second[-1][0] == "tool" and "error" in second[-1][1]  # the model was told why it failed
    assert second[-2][2] is True  # and its own tool call is part of the transcript
    third_tool_msg = transcripts[2][-1]
    assert third_tool_msg[0] == "tool" and third_tool_msg[3] == "good1"
    assert frames[-1][0] == "done"


async def test_a_reply_can_still_be_stopped_or_fail_while_tools_are_involved(client, register_user):
    class Breaks:
        name = "breaks"

        async def stream(self, messages, *, tools=None, **kw):
            if messages[-1].role == "user":
                yield ToolCall("c1", "get_lane_cost_carbon", '{"lane": "Atlanta-Miami"}')
            else:
                from app.llm.base import LLMError

                raise LLMError("llm_rate_limited", "The assistant is busy right now. Please try again in a moment.")

    app.dependency_overrides[get_llm_provider] = lambda: Breaks()
    a, c, frames = await _ask(client, register_user, "go")
    assert frames[-1][0] == "error" and frames[-1][1]["code"] == "llm_rate_limited"
    saved = (await _thread(client, a["headers"], c["id"]))[1]
    assert saved["status"] == "error"
    # what the tool already produced is kept, with its provenance
    assert [p["type"] for p in saved["parts"]][:2] == ["table", "chart"] and saved["meta"]["provenance"]
