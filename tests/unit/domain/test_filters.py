from lightdash_companion_integration_spike.domain import filters


class TestToRule:
    def test_builds_the_rule_the_server_accepted_for_the_last_seven_days(self) -> None:
        rule = filters.to_rule(
            filter_=filters.InThePast(field_id="runs_created_at_day", count=7, unit="days")
        )

        assert rule == {
            "fieldId": "runs_created_at_day",
            "fieldType": "date",
            "fieldFilterType": "date",
            "operator": "inThePast",
            "values": [7],
            "settings": {"completed": False, "unitOfTime": "days"},
        }

    def test_builds_a_between_rule_from_two_iso_dates(self) -> None:
        rule = filters.to_rule(filter_=filters.Between(field_id="d", start="2026-10-08", end="2026-10-08"))

        assert (rule["operator"], rule["values"]) == ("inBetween", ["2026-10-08", "2026-10-08"])

    def test_negates_a_string_filter(self) -> None:
        rule = filters.to_rule(filter_=filters.StringIs(field_id="s", values=["ci"], negate=True))

        assert (rule["operator"], rule["values"]) == ("notEquals", ["ci"])

    def test_wraps_a_number_threshold_as_a_single_value(self) -> None:
        rule = filters.to_rule(
            filter_=filters.NumberCompare(field_id="n", operator="greaterThan", value=100)
        )

        assert (rule["fieldFilterType"], rule["operator"], rule["values"]) == ("number", "greaterThan", [100.0])

    def test_a_current_period_filter_always_sends_one_as_its_value(self) -> None:
        rule = filters.to_rule(filter_=filters.InTheCurrent(field_id="d", unit="months"))

        assert (rule["operator"], rule["values"]) == ("inTheCurrent", [1])


class TestToDimensionFilters:
    def test_returns_none_when_there_are_no_filters(self) -> None:
        assert filters.to_dimension_filters(filters=[]) is None

    def test_combines_filters_with_and_and_leaves_the_other_groups_empty(self) -> None:
        built = filters.to_dimension_filters(
            filters=[filters.InThePast(field_id="d", count=7, unit="days"), filters.BooleanIs(field_id="b", value=True)]
        )

        assert built is not None
        assert built["type"] == "and"
        assert [rule["fieldId"] for rule in built["dimensions"]] == ["d", "b"]  # type: ignore[index]  # built above
        assert (built["metrics"], built["tableCalculations"]) == ([], [])
