from lightdash_companion_integration_spike.agent import chart_config


class TestNormalize:
    def test_keeps_a_missing_config_as_null(self) -> None:
        assert chart_config.normalize(chart_config=None) is None

    def test_adds_the_fields_the_server_requires(self) -> None:
        normalized = chart_config.normalize(chart_config={"xAxisDimension": "d"})

        assert normalized == {
            "defaultVizType": "table",
            "xAxisLabel": "",
            "yAxisLabel": "",
            "xAxisDimension": "d",
        }

    def test_keeps_values_the_model_supplied(self) -> None:
        normalized = chart_config.normalize(
            chart_config={"defaultVizType": "bar", "xAxisLabel": "Status", "yAxisLabel": "Seconds"}
        )

        assert normalized == {"defaultVizType": "bar", "xAxisLabel": "Status", "yAxisLabel": "Seconds"}
