from typing import Annotated, Literal

import pydantic


class MarkdownBlock(pydantic.BaseModel):
    type: Literal["markdown"] = "markdown"
    text: str


class ChartBlock(pydantic.BaseModel):
    type: Literal["lightdash_chart"] = "lightdash_chart"
    artifact_id: str
    version: int
    title: str
    query_uuid: str
    query_args: dict[str, object]
    rows: list[dict[str, object]]
    fields: dict[str, object]
    explore_url: str | None = None


class FollowUpsBlock(pydantic.BaseModel):
    type: Literal["follow_ups"] = "follow_ups"
    suggestions: list[str]


Block = Annotated[
    MarkdownBlock | ChartBlock | FollowUpsBlock, pydantic.Field(discriminator="type")
]

BlockList = pydantic.TypeAdapter(list[Block])
