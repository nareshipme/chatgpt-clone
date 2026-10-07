"""The typed parts a message is made of, and the validation every part must pass before it is stored or sent.

A message is a list of parts. Real models speak Markdown inside text parts. Structured parts (table, chart,
image, actions) are built by the server (for example from tool results), never trusted from raw model output,
and every one is validated here first so a bug or a hostile input cannot put junk or unsafe URLs in a thread.
"""
import logging
import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, field_validator, model_validator

log = logging.getLogger("app.parts")

MAX_TABLE_COLUMNS = 12
MAX_TABLE_ROWS = 200
MAX_CHART_POINTS = 200
MAX_CHART_SERIES = 6
MAX_ACTIONS = 6

Cell = str | int | float | bool | None


class TextPart(BaseModel):
    type: Literal["text"]
    text: str


class TablePart(BaseModel):
    type: Literal["table"]
    title: str | None = Field(default=None, max_length=200)
    columns: list[str] = Field(min_length=1, max_length=MAX_TABLE_COLUMNS)
    rows: list[list[Cell]] = Field(max_length=MAX_TABLE_ROWS)

    @model_validator(mode="after")
    def _rows_match_columns(self):
        width = len(self.columns)
        for row in self.rows:
            if len(row) != width:
                raise ValueError("every row must have exactly one cell per column")
        return self


class ChartSeries(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=60)


class ChartPart(BaseModel):
    type: Literal["chart"]
    kind: Literal["bar", "line"]
    title: str | None = Field(default=None, max_length=200)
    x: str = Field(min_length=1, max_length=40)  # the data key used for the horizontal axis
    series: list[ChartSeries] = Field(min_length=1, max_length=MAX_CHART_SERIES)
    # A null value is a gap in that series (for example, no actuals yet for future days).
    data: list[dict[str, str | int | float | None]] = Field(max_length=MAX_CHART_POINTS)

    @model_validator(mode="after")
    def _data_has_the_declared_keys(self):
        needed = {self.x, *(s.key for s in self.series)}
        for point in self.data:
            if not needed <= point.keys():
                raise ValueError("every data point needs the x key and one value per series")
        return self


class ImagePart(BaseModel):
    type: Literal["image"]
    url: str = Field(max_length=2000)
    alt: str = Field(max_length=200)

    @field_validator("url")
    @classmethod
    def _https_only(cls, v: str) -> str:
        # No http (mixed content), no data:/javascript: URLs, no relative paths.
        if not re.match(r"^https://[^\s/]+", v):
            raise ValueError("image url must be an absolute https URL")
        return v


class ActionOption(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,40}$")
    label: str = Field(min_length=1, max_length=60)
    value: str = Field(min_length=1, max_length=500)  # sent as the user's next message when chosen


class ActionsPart(BaseModel):
    type: Literal["actions"]
    prompt: str | None = Field(default=None, max_length=300)
    options: list[ActionOption] = Field(min_length=1, max_length=MAX_ACTIONS)

    @field_validator("options")
    @classmethod
    def _unique_ids(cls, v: list[ActionOption]) -> list[ActionOption]:
        if len({o.id for o in v}) != len(v):
            raise ValueError("option ids must be unique")
        return v


class ProposalPart(BaseModel):
    """A card with Approve / Dismiss for something the copilot proposes. It holds only the id of the server-side
    action; the current status and the details are fetched from the API, never trusted from this part."""

    type: Literal["proposal"]
    action_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    action_type: str = Field(min_length=1, max_length=30)
    summary: str = Field(min_length=1, max_length=300)


Part = Annotated[TextPart | TablePart | ChartPart | ImagePart | ActionsPart | ProposalPart, Field(discriminator="type")]
_adapter: TypeAdapter = TypeAdapter(Part)


def validate_part(raw: object) -> dict | None:
    """Return the cleaned part as a plain dict, or None (and log why) if it is not a valid part."""
    try:
        return _adapter.validate_python(raw).model_dump()
    except ValidationError as exc:
        # Log the shape of the problem, never the content (it may be user-derived).
        log.warning("dropped an invalid message part: %s", [e["type"] + ":" + ".".join(map(str, e["loc"])) for e in exc.errors()][:5])
        return None
