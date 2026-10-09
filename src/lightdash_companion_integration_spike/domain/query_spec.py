import pydantic


class Sort(pydantic.BaseModel):
    field_id: str = pydantic.Field(serialization_alias="fieldId")
    descending: bool = False


class QuerySpec(pydantic.BaseModel):
    """
    A governed metric query. Every id must come from find_fields.
    """

    model_config = pydantic.ConfigDict(populate_by_name=True)

    explore_name: str = pydantic.Field(serialization_alias="exploreName")
    dimensions: list[str] = pydantic.Field(
        description="Dimension field ids to group by, e.g. orders_status."
    )
    metrics: list[str] = pydantic.Field(
        description="Existing metric field ids, e.g. orders_total_revenue. Never write SQL."
    )
    sorts: list[Sort] = pydantic.Field(default_factory=list)
    limit: int | None = 500

    def to_mcp(self) -> dict[str, object]:
        return self.model_dump(by_alias=True)
