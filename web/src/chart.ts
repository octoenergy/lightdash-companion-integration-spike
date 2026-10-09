import * as common from "@lightdash/common";
import * as visualization from "@lightdash/visualization";

import * as types from "./types";

// A metric query needs more than the tool's queryConfig, but for governed queries the extra
// parts are empty. Lightdash's backend fills in the same defaults.
function buildMetricQuery(queryConfig: types.QueryConfig): common.MetricQuery {
    return {
        exploreName: queryConfig.exploreName,
        dimensions: queryConfig.dimensions,
        metrics: queryConfig.metrics,
        filters: {},
        sorts: queryConfig.sorts.map((sort) => ({ ...sort, nullsFirst: undefined })),
        limit: queryConfig.limit ?? 500,
        tableCalculations: [],
        additionalMetrics: [],
    };
}

// The transformed schema rejects missing optional parts that the MCP schema allows to be null.
function withToolDefaults(
    payload: types.ChartPayload,
    vizType: types.VizType,
): unknown {
    return {
        ...payload.args,
        queryConfig: {
            customMetrics: [],
            tableCalculations: [],
            filters: { type: "and", dimensions: [], metrics: [], tableCalculations: [] },
            parameters: null,
            ...payload.args.queryConfig,
        },
        chartConfig: {
            xAxisLabel: "",
            yAxisLabel: "",
            xAxisDimension: null,
            yAxisMetrics: null,
            groupBy: [],
            xAxisType: "category",
            stackBars: false,
            lineType: "line",
            ...payload.args.chartConfig,
            defaultVizType: vizType,
        },
    };
}

function buildChartConfig(
    payload: types.ChartPayload,
    vizType: types.VizType,
): common.ChartConfig {
    const queryTool = common.toolRunQueryArgsSchemaTransformed.parse(
        withToolDefaults(payload, vizType),
    );
    return common.getRunQueryChartConfig({
        queryTool,
        metricQuery: buildMetricQuery(payload.args.queryConfig),
        fieldsMap: payload.fields as common.ItemsMap,
        overrideChartType: vizType,
    });
}

export function render(
    payload: types.ChartPayload,
    vizType: types.VizType,
    size: { width: number; height: number },
): visualization.RenderedChart {
    const chartConfig = buildChartConfig(payload, vizType);
    const fields = payload.fields as visualization.ChartFields;
    return visualization.renderChart(
        {
            chartConfig,
            tableConfig: {
                columnOrder: [
                    ...payload.args.queryConfig.dimensions,
                    ...payload.args.queryConfig.metrics,
                ],
            },
        },
        {
            rows: visualization.toResultRows(payload.rows, fields),
            fields,
        },
        { theme: visualization.LIGHT_VISUALIZATION_THEME, size },
    );
}
