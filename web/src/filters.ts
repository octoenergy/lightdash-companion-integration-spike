import * as common from "@lightdash/common";

import * as types from "./types";

type WireRule = {
    fieldId: string;
    operator: string;
    values?: unknown[];
    settings?: { unitOfTime?: string; completed?: boolean };
};

type WireFilters = { type: string; dimensions: WireRule[] | null } | null;

/** Filters as the MCP accepts them: flat typed rules joined by `type`. */
export function wireFilters(args: types.ChartArgs): WireFilters {
    return (args.queryConfig.filters as WireFilters | undefined) ?? null;
}

export function describeRule(rule: WireRule): string {
    const field = rule.fieldId.split("_").slice(-3).join(" ");
    const values = (rule.values ?? []).join(" and ");
    const unit = rule.settings?.unitOfTime ? ` ${rule.settings.unitOfTime}` : "";
    return `${field} ${rule.operator} ${values}${unit}`.trim();
}

export function describeFilters(args: types.ChartArgs): string[] {
    return (wireFilters(args)?.dimensions ?? []).map(describeRule);
}

/** Remove one dimension filter, returning null when none remain so the query runs unfiltered. */
export function withoutRule(args: types.ChartArgs, index: number): types.ChartArgs {
    const current = wireFilters(args);
    const remaining = (current?.dimensions ?? []).filter((_, position) => position !== index);
    const filters = remaining.length ? { ...current, dimensions: remaining } : null;
    return { ...args, queryConfig: { ...args.queryConfig, filters } };
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
