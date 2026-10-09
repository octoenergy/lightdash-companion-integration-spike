from collections.abc import Mapping

DEFAULT_VIZ_TYPE = "table"


def normalize(*, chart_config: Mapping[str, object] | None) -> dict[str, object] | None:
    """
    Fill in the fields the MCP requires whenever a chart config is present.

    The server rejects a chart config without a viz type and axis labels, and the only valid
    way to omit one entirely is null.
    """
    if chart_config is None:
        return None
    return {
        "defaultVizType": DEFAULT_VIZ_TYPE,
        "xAxisLabel": "",
        "yAxisLabel": "",
        **chart_config,
    }
