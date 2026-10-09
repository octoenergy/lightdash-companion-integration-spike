from typing import Annotated, Literal

import pydantic

TimeUnit = Literal["days", "weeks", "months", "quarters", "years"]


class InThePast(pydantic.BaseModel):
    """
    A date field within the last N units, e.g. the last 7 days.
    """

    kind: Literal["in_the_past"] = "in_the_past"
    field_id: str
    count: int = pydantic.Field(gt=0)
    unit: TimeUnit
    completed_only: bool = pydantic.Field(
        default=False,
        description="True to exclude the current partial period (e.g. only whole past weeks).",
    )


class Between(pydantic.BaseModel):
    """
    A date field between two ISO dates (YYYY-MM-DD), e.g. for 'yesterday' use the same date twice.
    """

    kind: Literal["between"] = "between"
    field_id: str
    start: str = pydantic.Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = pydantic.Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class InTheCurrent(pydantic.BaseModel):
    """
    A date field within the current period, e.g. this month.
    """

    kind: Literal["in_the_current"] = "in_the_current"
    field_id: str
    unit: TimeUnit


class StringIs(pydantic.BaseModel):
    """
    A text dimension equal to, or not equal to, one or more values. Look values up first.
    """

    kind: Literal["string_is"] = "string_is"
    field_id: str
    values: list[str] = pydantic.Field(min_length=1)
    negate: bool = False


class NumberCompare(pydantic.BaseModel):
    """
    A number field compared with a single threshold.
    """

    kind: Literal["number_compare"] = "number_compare"
    field_id: str
    operator: Literal["lessThan", "lessThanOrEqual", "greaterThan", "greaterThanOrEqual", "equals"]
    value: float


class BooleanIs(pydantic.BaseModel):
    kind: Literal["boolean_is"] = "boolean_is"
    field_id: str
    value: bool


Filter = Annotated[
    InThePast | Between | InTheCurrent | StringIs | NumberCompare | BooleanIs,
    pydantic.Field(discriminator="kind"),
]


def to_rule(*, filter_: "Filter") -> dict[str, object]:
    """
    Convert a filter into the typed rule object the Lightdash MCP expects.

    The server's schema is strict (field type, filter type, operator and values must agree), so
    this is the one place that shape is produced.
    """
    base: dict[str, object] = {"fieldId": filter_.field_id}
    match filter_:
        case InThePast():
            return {
                **base,
                "fieldType": "date",
                "fieldFilterType": "date",
                "operator": "inThePast",
                "values": [filter_.count],
                "settings": {"completed": filter_.completed_only, "unitOfTime": filter_.unit},
            }
        case Between():
            return {
                **base,
                "fieldType": "date",
                "fieldFilterType": "date",
                "operator": "inBetween",
                "values": [filter_.start, filter_.end],
            }
        case InTheCurrent():
            return {
                **base,
                "fieldType": "date",
                "fieldFilterType": "date",
                "operator": "inTheCurrent",
                "values": [1],
                "settings": {"completed": False, "unitOfTime": filter_.unit},
            }
        case StringIs():
            return {
                **base,
                "fieldType": "string",
                "fieldFilterType": "string",
                "operator": "notEquals" if filter_.negate else "equals",
                "values": filter_.values,
            }
        case NumberCompare():
            return {
                **base,
                "fieldType": "number",
                "fieldFilterType": "number",
                "operator": filter_.operator,
                "values": [filter_.value],
            }
        case BooleanIs():
            return {
                **base,
                "fieldType": "boolean",
                "fieldFilterType": "boolean",
                "operator": "equals",
                "values": [filter_.value],
            }


def to_dimension_filters(*, filters: list["Filter"]) -> dict[str, object] | None:
    """
    Build the `queryConfig.filters` object for dimension filters, or None when there are none.

    Only dimension filters are supported: filtering a metric is a different part of the schema.
    """
    if not filters:
        return None
    return {
        "type": "and",
        "dimensions": [to_rule(filter_=filter_) for filter_ in filters],
        "metrics": [],
        "tableCalculations": [],
    }
