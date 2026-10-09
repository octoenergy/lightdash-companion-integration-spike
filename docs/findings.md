# Spike findings

Instance: KTL Lightdash **2.427.4**, project `ktl_data_services_prod_core`.

## Step 0

| Question | Result |
|---|---|
| Does the MCP return rows + fields at 2.427.4 (older than the 2.459 assumed)? | **Yes.** `run_metric_query` returned `status: done`, `queryUuid`, raw `rows` keyed by field id, full `fields` metadata and `exploreUrl`. Charting data is not blocked by version. |
| Is `exploreUrl` an embed link? | **No.** It is `https://lightdash.ktl.data.ktl.net/share/<id>`, a share link into the normal app that needs a Lightdash login. Explore-from-here still needs the embed route. |
| Does `@lightdash/visualization` exist at the instance version? | Yes, `2.427.4` (with matching `@lightdash/common`). |
| Bundle size of a naive full import | 2.9 MB / 709 KB gzipped (upper bound, no tree-shaking). |
| Does `structuredContent` carry the query result? | **Yes**, verified live with `scripts/probe_mcp.py` over fastmcp. `run_metric_query` returns two text blocks plus `structuredContent.result` with `status`, `queryUuid`, `rows`, `fields` and `exploreUrl`. `_meta` is empty for this tool. The PAT authenticates and the session lists 30 tools. |
| Does PydanticAI's MCP toolset pass `structuredContent` through? | Not yet tested. The plan sidesteps it by wrapping the MCP calls in our own tools, which use the raw result from `call_tool_raw`. |

## Capabilities

Agent scoping is deliberately last. Nothing below has been run end to end in a chat yet; "proven" means against a real KTL query result saved as `tests/fixtures/run_metric_query_result.json`, drawn in headless Chromium.

| # | Capability | Status | Notes |
|---|---|---|---|
| 1 | Charts drawn in chat | **Proven end to end** | Browser test against live KTL data: the agent's answer arrives over SSE and an interactive ECharts canvas appears inline in the chat. |
| 2 | Results table | **Proven end to end** | Table view of the same rows, using Lightdash's formatted values (e.g. `2,542.825`). |
| 3 | CSV / image download | **Proven end to end** | CSV built in the browser from the table model (header + formatted rows); PNG from `echarts.getDataURL()` (valid PNG, ~65 KB). Both downloaded in Chromium. Note CSV carries *formatted* values (`"2,542.825"`), so a numeric export would need the raw rows. |
| 5 | Switching chart type | **Proven end to end** | bar, horizontal, line, pie and table switched in the live chat from the cached rows, no network call. |
| 12 | Follow-ups that build on the previous result | **Proven live** (agent level) | With `history.build_message_history` injecting each chart's latest `query_args`, "Now split that by month of creation" edited the earlier query (added `fct_dbt_runs_created_at_month`) instead of starting over. |
| 13 | Chart versions across turns | **Proven end to end** | A follow-up became v2 of the same artifact, and the v1/v2 switcher on the card swapped between the stored queries. **Open design question:** the agent also filed "Show the run count by status" (same dimension, different metric) as v2 of "Average execution time by status". That was a deliberate reading ("I updated the chart"), but it means "what counts as an edit vs a new chart" is the agent's judgement, not a rule. Decide this before relying on version labels. |
| 6 | Editing filters/metrics/dimensions without the LLM | **Proven end to end** | The "Edit query" panel changed the limit to 2, `POST /api/queries/rerun` called the MCP directly, and the card redrew with 2 rows. No model call. The panel edits dimensions, metrics and limit only; filters are not editable in the spike UI. |
| 10 | Streaming text + live tool steps | **Proven end to end** | `POST /api/threads/{id}/messages` streams SSE: a `tool_step` event per tool call ("Searching fields…", "Running query…") then one `answer` event. The answer is not token-streamed, and the MCP itself returns whole results, so this is progress streaming, not text streaming. |
| 11 | Threads, history, feedback, follow-up chips | **Proven end to end** | In the browser: thread list, history surviving a page reload, thumbs feedback stored against the message, and follow-up chips that send the next prompt when clicked. |
| 4 | Row-level security | **Blocked** | See below. |
| 7 | Explore from here | **Proven live, with caveats** | Our own signed JWT opened `/embed/{project}/explore/{explore}?create_saved_chart_version=...#jwt` on the KTL instance with the unsaved query pre-selected (dimension, metric and sort loaded) and, after clicking Run, real results. Caveats below. |
| 8 | Save chart to space | **Proven live** (API only) | `create_content` wrote a real chart into the dedicated sandbox space via the MCP, using only the user PAT. Verified by listing the space: exactly one chart, in the right place. The Save button and `/api/charts/save` are built and unit-tested but the button was not clicked in a browser, to avoid creating duplicate charts. Limits and gotchas below. |

### Gotchas found while building the chart module
- **`getRunQueryChartConfig` and `toolRunQueryArgsSchemaTransformed` are exported from the root of `@lightdash/common@2.427.4`.** The MCP-args-to-chart-config bridge needs no deep imports.
- **The transformed zod schema is stricter than the MCP input schema.** It rejects missing `customMetrics`, `tableCalculations`, `parameters`, `groupBy`, `xAxisType`, `stackBars`, `lineType`, and a `filters` object without `type`, `dimensions`, `metrics` and `tableCalculations`. The types did not catch this; it only failed at runtime. `web/src/chart.ts` fills these defaults.
- **The browser builds its own `MetricQuery`** from the tool's `queryConfig`, since Lightdash does that server-side. Fine for simple governed queries. Filters and table calculations would need real conversion.
- **Bundle size with chart code is 3.96 MB (1.05 MB gzipped)**, including echarts. Not yet tree-shaken.

### Gotchas found while building the agent
- **The LLM does not reliably build a valid `queryConfig` from a free-form `dict`.** Given no schema it invented a raw-SQL table calculation (`AVG(${...})`) instead of using the real metric, and the server rejected it. A typed `QuerySpec` model plus an instruction not to write SQL fixed it. Companion should type its query tool the same way.
- **MCP validation errors arrive as text, not exceptions.** A rejected call returns no `structuredContent`; the reason is only in a text block (`MCP error -32602: ...`). `queries.MissingStructuredResult` now carries it as `server_message`; without that, every failure looks identical.
- **`chartConfig` is all-or-nothing.** If present it needs `defaultVizType`, `xAxisLabel` and `yAxisLabel`; the only valid way to omit it is `null`.
- **Empty env vars break the MCP.** `AGENT_UUID=` in `.env` was sent as `""` and failed `Invalid UUID at agentUuid`. Blank optional settings are now treated as unset.
- **`get_metadata` takes tagged requests** (`{"type": "field", "fields": [{"exploreId", "fieldId"}]}` or `{"type": "explore", "exploreIds": [...]}`), not a bare explore name.
- **Tool steps are observable.** The agent's tools emit "Searching fields…" and "Running query…" via an `on_step` callback, ready to stream.

### Row-level security (capability 4): blocked, partial findings
- **The admin token in `.env` is rejected by Lightdash itself** (`GET /api/v1/user` -> 401 "Failed to authorize user"), while the user token works. The test needs an org-admin token, so it could not be run.
- **No explore in `ktl_data_services_prod_core` is filtered by user attributes.** `required_attributes` (HiBob/People Ops tables, whole-table gating) and `${lightdash.attributes.*}` row filters exist only in other projects' models (`company_id`, `site_ids`, `org_names_in_static_data`). So even with a working token there is nothing here to show a narrowed result; the test needs a project that has an attribute-filtered explore.
- **A non-admin token with a valid `X-Lightdash-User-Attributes` header was accepted** (query returned rows, no rejection). The research said the override is admin-only, but on an explore with no attribute filter the header has nothing to act on, so this does **not** show the admin check is missing. Needs retesting on a filtered explore.
- **Not tested: malformed JSON fails open.** It needs the admin token. This is the main risk to confirm, because a silently ignored header means no row-level restriction.

### Gotchas found while building the chat UI
- **Follow-up chips must be written as instructions, not questions.** Left alone, the model offered "Do you want to filter to a specific time period?"; clicking it produced a prose reply and no chart. The prompt now requires imperative follow-ups ("Split by month").
- **EventSource cannot POST**, so the SSE answer stream is read with `fetch` and a manual frame parser (`web/src/api.ts`).
- **ECharts instances outlive their DOM.** `replaceChildren()` removes the canvas but not the instance bound to the node; redrawing without `dispose()` throws `Cannot read properties of undefined (reading 'hasOwnProperty')`.
- **fastmcp prints `Unknown SSE event: connect`** on every Lightdash MCP connection. It is harmless noise from the server's heartbeat event.

### Explore from here (capability 7)
- **It works with an unsaved chat query.** The MCP's own `exploreUrl` is a `/share/<id>` link into the normal app and needs a Lightdash login. Building our own embed URL from the same `{tableName, metricQuery, tableConfig, chartConfig}` payload, signed with the embed secret, opened a working explore with no login.
- **The right JWT content type is `metricsCatalog` with `canExplore: true`.** The first version used `dashboard`, which the schema rejects without a `dashboardUuid`/`dashboardSlug`. `metricsCatalog` needs no saved dashboard or chart.
- **The query does not run on load.** The page waits at "Run query to see your results" until clicked, as `EmbedExplore.tsx:118-120` predicted. Companion cannot skip this without Lightdash changing the route.
- **The page shows a "Back to Metrics Catalog" button** (a side effect of the content type), which needs hiding or it lets the user navigate away from the embed.
- **Three peripheral calls return 403** (`colorPalette`, `code/sync-settings`, `aiAgents/settings`). None affects data or the explore, but they would show in the browser console and may mean default theming.
- **The embed route is undocumented for unsaved charts.** It works today at 2.427.4, but Lightdash has not committed to supporting it (an open question on the Notion page).
- **`userAttributes` in the JWT is where per-user row-level security would go** for embeds, the same mechanism the dashboard embeds use. Not exercised: no attribute-filtered explore exists in this project.

### Save chart to space (capability 8)
- **It works with the existing user PAT.** No separate write token was needed. The org setting `mcpContentWritesEnabled` defaults to on, so this is open by default, which matters for the "locked-down write permissions" concern on the Notion page. Writes are scoped only by what that user can do, so a dedicated service account on a dedicated project would be needed to make this safe.
- **The chart is built by us, not the model.** `create_content` takes chart-as-code JSON, not the `run_metric_query` args. `content.build_bar_chart_content` converts a query into that shape. It supports only a single dimension with one or more metrics as a bar chart; anything else is refused, because an unused dimension silently adds a GROUP BY and gives wrong numbers. A general converter (line, pie, pivots) is real work.
- **The schema is stricter than the docs.** Required but easy to miss: `verified` (we send `false`), `dashboardSlug` and `metricQuery.tableCalculations`. The skill says a reusable chart has no `dashboardSlug`, yet the schema marks it required and non-null. An **empty string worked**, and no dashboard was created.
- **A successful save has no `structuredContent`.** It returns `<chart href="/projects/.../saved/<uuid>/view#chart-link" />` followed by the persisted JSON as text. Failure is signalled only by `is_error`. The first version of the wrapper treated the missing structured content as a failure and reported a successful write as rejected.
- **Slugs are not guaranteed.** Lightdash may append a suffix to the requested slug, so the returned link, not the requested slug, is the reference.
- **Cleanup is manual.** The spike creates charts but does not delete them. One test chart (`Spike: avg dbt execution time by run status`) is in the sandbox space.
- **Saving does not answer "how does a saved chart reach the dashboard builder in the support site"** (an open question on the Notion page). It lands in Lightdash and needs a separate path into the support site.

## Agent context experiment (can the agent know enough about the data?)

Joe's diagnosis: our agent writes queries with little knowledge of what metrics and tables exist. The Lightdash assistant suggested configuring a Lightdash agent (`route_agent`) or using the agents REST API. Neither is available on KTL: `list_agents` returns `Copilot is not enabled` and `route_agent` returns `No accessible AI agents are available`; the REST agent methods are behind the same `AiCopilot` flag. The assistant also named `find_fields`/`find_explores`; KTL has neither (the tool is `grep_fields`).

What is available over MCP: a published `lightdash-analyst` prompt (1.9 KB) and `get_metadata`. The method: 10 fixed questions (`src/.../evaluation.py`, `scripts/eval_questions.py`), one run each, results in `docs/eval/*.json`. The mechanical checks only catch obvious failures; metric correctness was judged by reading the printed queries.

| Run | Change | Mechanical pass | Tokens | What actually changed |
|---|---|---|---|---|
| `baseline` | none | 6/10 | 413K | Agent used only `grep_fields`+`run_query`. |
| `discovery` | server prompt + `describe_explore`/`describe_fields` | 6/10 | 468K | Metric choice now follows metric descriptions. Headline unchanged. |
| `filters` | typed filters in `QuerySpec`, `lookup_values`, "ask when vague" rule | 8/10 | 398K | Time windows now applied; vague question declined. Two answers still wrong on reading (below). |

**What discovery fixed (stable across 3 repeats):**
- `single-value` ("how many active supply points") now consistently picks `fact_cost_per_supply_point_monthly` (2,093,569,283). Baseline used a *weekly* pre-aggregated metric (9.04B). The metric's own description says it "cannot be rolled up or broken down further into finer timeframes" - text the agent never saw before.
- "Yesterday" is now declined honestly instead of answered with a weekly figure labelled as yesterday. (The first scorecard marked this FAIL because the case expectation was wrong, not the agent.)
- Every answerable case now reads metadata before querying.

**What it did not fix:**
- **Time filters.** `QuerySpec` has no `filters`, so "last 7 days" still returns all-time (500 rows). Needs the filter work.
- **Vague questions are still guessed at, unstably.** "How are we doing?" ran a query in 2 of 3 repeats, against a different explore each time (messaging, warehouse performance). The server prompt says "if ambiguous, ask the user, never guess", but our output type has no clarifying-question path.

**Cost:** +13% tokens for the extra metadata calls.

**Caveat:** one sample per case. Only 3 cases were repeated, so the other results could be noise.

**Filters + clarifying rule (`filters` run):**
- `relative-date` ("last 7 days, by day") now returns 8 rows dated 2026-10-02..10-09 (baseline: 500 rows of all-time data). KTL accepts the *object* filter shape (`fieldId`, `fieldType`, `fieldFilterType`, `operator`, `values`, `settings`); the `filter-expressions` skill describes a string mode that this instance rejects (`expected array, received string`), so following the skill would have produced broken filters.
- "How are we doing?" now declines with no tool calls (1.7K tokens vs 33K) instead of running a query.
- Tokens fell to 398K because declined/filtered cases are cheaper.

**The mechanical score overstates quality - two answers are wrong when read:**
- `yesterday` (FAIL, correctly): the agent found a real daily explore but used `average_active_supply_points`, described as "average per day/fabric", and presented 1,535,117.63 as "active supply points across all clients". That is an average per fabric, not a total. Discovery tells the agent the grain, not whether the *aggregation* matches the question. Open problem.
- `ambiguous` (PASS): it declined correctly but offered "Revenue trend / Orders volume / Conversion rate". `grep_fields` finds no `orders` or `conversion` fields in the project, and `revenue` only matches a narrow VEE metric. The options were invented, not looked up.

**Where agent-context stands:** discovery + filters fixed metric grain and time windows. Still open: aggregation mismatches, and invented follow-up/clarification options. Not tested: the raw pass-through option (D) and a configured Lightdash agent (blocked, Copilot off).
