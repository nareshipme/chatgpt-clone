import json

import pytest

from app.llm.toolmarkup import ToolMarkupFilter

GLM = "<tool_call>get_demand_forecast<arg_key>sku</arg_key><arg_value>SKU-1004</arg_value><arg_key>horizon_days</arg_key><arg_value>14</arg_value></tool_call>"
HERMES = '<tool_call>{"name": "get_lane_cost_carbon", "arguments": {"lane": "Atlanta-Miami"}}</tool_call>'


def run(chunks):
    f = ToolMarkupFilter()
    shown = "".join(f.feed(c) for c in chunks) + f.flush()
    return shown, f.calls


def test_plain_text_passes_through_unchanged():
    assert run(["Hello ", "world, 3 < 5 and <b>bold</b>."]) == ("Hello world, 3 < 5 and <b>bold</b>.", [])


def test_a_glm_style_block_becomes_a_tool_call_with_typed_arguments():
    shown, calls = run(["Let me look. ", GLM])
    assert shown == "Let me look. " and len(calls) == 1
    assert calls[0].name == "get_demand_forecast"
    assert json.loads(calls[0].arguments) == {"sku": "SKU-1004", "horizon_days": 14}  # 14 is a number, not "14"


def test_a_hermes_style_json_block_is_understood_too():
    shown, calls = run([HERMES])
    assert shown == "" and calls[0].name == "get_lane_cost_carbon"
    assert json.loads(calls[0].arguments) == {"lane": "Atlanta-Miami"}


@pytest.mark.parametrize("size", [1, 2, 3, 5, 7, 13])
def test_it_works_however_the_stream_is_cut_into_pieces(size):
    text = "Before. " + GLM + " After."
    shown, calls = run([text[i : i + size] for i in range(0, len(text), size)])
    assert shown == "Before.  After." and len(calls) == 1 and calls[0].name == "get_demand_forecast"


def test_nothing_of_the_markup_is_ever_shown_even_mid_stream():
    f = ToolMarkupFilter()
    seen = ""
    for piece in ["ok <tool", "_call>get_inventory_position", "<arg_key>status</arg_key><arg_value>short</arg_value>", "</tool_call>", " done"]:
        seen += f.feed(piece)
        assert "<" not in seen and "tool_call" not in seen
    assert seen + f.flush() == "ok  done" and f.calls[0].name == "get_inventory_position"


def test_several_calls_in_one_reply():
    shown, calls = run([GLM + "\n" + HERMES])
    assert [c.name for c in calls] == ["get_demand_forecast", "get_lane_cost_carbon"] and [c.id for c in calls] == ["call-text-1", "call-text-2"]


def test_an_unfinished_block_at_the_end_is_still_used_and_never_shown():
    shown, calls = run(["Checking. <tool_call>get_inventory_position<arg_key>status</arg_key><arg_value>short</arg_value>"])
    assert shown == "Checking. " and calls[0].name == "get_inventory_position"


def test_a_lone_angle_bracket_at_the_end_is_released_not_swallowed():
    assert run(["a < b <"]) == ("a < b <", [])


def test_garbage_in_a_block_is_dropped_safely():
    shown, calls = run(["x <tool_call>{not json</tool_call> y <tool_call></tool_call>"])
    assert shown == "x  y " and calls == []
