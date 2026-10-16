import * as common from "@lightdash/common";

import * as types from "./types";

type WireFilters = { type: string; dimensions: unknown[] | null } | null;

/** Filters as the MCP accepts them: flat typed rules joined by `type`. */
export function wireFilters(args: types.ChartArgs): WireFilters {
    return (args.queryConfig.filters as WireFilters | undefined) ?? null;
}

// The explore and saved charts store filters as groups with ids, not as the MCP's flat rules.
// Lightdash's own schema does that conversion, so it is reused rather than re-implemented.
export function toLightdashFilters(args: types.ChartArgs): unknown {
    const parsed = common.toolRunQueryArgsSchemaTransformed.parse({
        title: args.title,
        description: args.description,
        queryConfig: {
            customMetrics: [],
            tableCalculations: [],
            parameters: null,
            ...args.queryConfig,
            filters: wireFilters(args) ?? { type: "and", dimensions: [], metrics: [], tableCalculations: [] },
        },
        chartConfig: null,
    });
    return parsed.queryConfig.filters;
}
