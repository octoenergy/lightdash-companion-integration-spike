export type RawRow = Record<string, unknown>;

export type QueryConfig = {
    exploreName: string;
    dimensions: string[];
    metrics: string[];
    sorts: { fieldId: string; descending: boolean }[];
    limit: number | null;
};

export type ChartArgs = {
    title: string;
    description: string;
    queryConfig: QueryConfig;
    chartConfig: Record<string, unknown> | null;
};

export type ChartPayload = {
    queryUuid: string;
    rows: RawRow[];
    fields: Record<string, unknown>;
    exploreUrl: string | null;
    args: ChartArgs;
};

export type VizType =
    | "table"
    | "bar"
    | "horizontal"
    | "line"
    | "scatter"
    | "pie"
    | "funnel";

export const VIZ_TYPES: VizType[] = [
    "table",
    "bar",
    "horizontal",
    "line",
    "scatter",
    "pie",
    "funnel",
];
