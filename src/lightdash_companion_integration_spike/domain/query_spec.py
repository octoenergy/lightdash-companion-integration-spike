import pydantic

from lightdash_companion_integration_spike.domain import filters as filters_module


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
    filters: list[filters_module.Filter] = pydantic.Field(
        default_factory=list,
        description=(
            "Restrict rows, e.g. 'last 7 days' or one client. Use filters for any time window or "
            "specific value in the question. A field used only to filter must not be added to dimensions."
        ),
    )
    limit: int | None = 500

    def to_mcp(self) -> dict[str, object]:
        """
        Build the `queryConfig` the MCP expects, with filters converted to its rule shape.
        """
        built = self.model_dump(by_alias=True, exclude={"filters"})
        built["filters"] = filters_module.to_dimension_filters(filters=self.filters)
        return built
