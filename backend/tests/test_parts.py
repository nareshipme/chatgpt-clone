import pytest

from app.schemas.parts import validate_part

TABLE = {"type": "table", "title": "Sales", "columns": ["Region", "Q1"], "rows": [["North", 10], ["South", None]]}
CHART = {
    "type": "chart", "kind": "bar", "title": "Revenue", "x": "month",
    "series": [{"key": "sales", "label": "Sales"}],
    "data": [{"month": "Jan", "sales": 10}, {"month": "Feb", "sales": 14.5}],
}
IMAGE = {"type": "image", "url": "https://example.com/a.png", "alt": "A picture"}
ACTIONS = {
    "type": "actions", "prompt": "Pick one",
    "options": [{"id": "a", "label": "A", "value": "I choose A"}, {"id": "b_2", "label": "B", "value": "I choose B"}],
}


@pytest.mark.parametrize("part", [TABLE, CHART, IMAGE, ACTIONS, {"type": "text", "text": "hi"}])
def test_valid_parts_pass_through_unchanged_in_shape(part):
    cleaned = validate_part(part)
    assert cleaned is not None and cleaned["type"] == part["type"]


def test_unknown_types_and_garbage_are_rejected():
    for bad in ({"type": "script", "code": "x"}, {"text": "no type"}, "a string", None, 42, []):
        assert validate_part(bad) is None


def test_extra_keys_are_stripped_not_stored():
    cleaned = validate_part({**IMAGE, "onerror": "alert(1)"})
    assert cleaned is not None and "onerror" not in cleaned


@pytest.mark.parametrize(
    "url",
    ["http://example.com/a.png", "javascript:alert(1)", "data:image/svg+xml;base64,AAAA", "/relative.png", "//example.com/a.png", "https://", "ftp://x/y"],
)
def test_images_must_be_absolute_https_urls(url):
    assert validate_part({**IMAGE, "url": url}) is None


def test_table_rows_must_match_the_columns():
    assert validate_part({**TABLE, "rows": [["only one cell"]]}) is None
    assert validate_part({**TABLE, "rows": [["a", 1, "extra"]]}) is None


def test_table_size_limits():
    assert validate_part({**TABLE, "columns": [f"c{i}" for i in range(13)], "rows": []}) is None
    assert validate_part({**TABLE, "rows": [["a", 1]] * 201}) is None
    assert validate_part({**TABLE, "columns": [], "rows": []}) is None


def test_table_cells_must_be_plain_values():
    assert validate_part({**TABLE, "rows": [[{"nested": "object"}, 1]]}) is None
    assert validate_part({**TABLE, "rows": [[["a", "list"], 1]]}) is None


def test_chart_points_need_the_declared_keys():
    assert validate_part({**CHART, "data": [{"month": "Jan"}]}) is None  # missing the 'sales' value
    assert validate_part({**CHART, "data": [{"sales": 3}]}) is None  # missing the x value


def test_chart_limits_and_kinds():
    assert validate_part({**CHART, "kind": "pie"}) is None
    assert validate_part({**CHART, "data": [{"month": "m", "sales": 1}] * 201}) is None
    assert validate_part({**CHART, "series": []}) is None
    too_many = [{"key": f"s{i}", "label": f"S{i}"} for i in range(7)]
    assert validate_part({**CHART, "series": too_many}) is None


def test_action_option_rules():
    dup = {**ACTIONS, "options": [{"id": "a", "label": "A", "value": "x"}, {"id": "a", "label": "B", "value": "y"}]}
    assert validate_part(dup) is None  # duplicate ids
    assert validate_part({**ACTIONS, "options": []}) is None
    assert validate_part({**ACTIONS, "options": [{"id": "Bad Id!", "label": "A", "value": "x"}]}) is None
    seven = [{"id": f"o{i}", "label": "L", "value": "v"} for i in range(7)]
    assert validate_part({**ACTIONS, "options": seven}) is None
    assert validate_part({**ACTIONS, "options": [{"id": "a", "label": "A", "value": ""}]}) is None


def test_a_chart_series_may_have_gaps_but_the_keys_must_still_be_there():
    chart = {"type": "chart", "kind": "line", "x": "d", "series": [{"key": "a", "label": "A"}, {"key": "b", "label": "B"}],
             "data": [{"d": "1", "a": 1, "b": 2}, {"d": "2", "a": 3, "b": None}]}
    assert validate_part(chart)["data"][1]["b"] is None
    chart["data"][1].pop("b")
    assert validate_part(chart) is None  # a missing key is still a malformed point
