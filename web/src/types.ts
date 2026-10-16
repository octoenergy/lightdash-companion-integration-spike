export type QueryConfig = {
    exploreName: string;
    dimensions: string[];
    metrics: string[];
    sorts: { fieldId: string; descending: boolean }[];
    limit: number | null;
    filters?: unknown;
};

export type ChartArgs = {
    title: string;
    description: string;
    queryConfig: QueryConfig;
    chartConfig: Record<string, unknown> | null;
};

export type AppRender = {
    input: Record<string, unknown>;
    result: Record<string, unknown>;
};
