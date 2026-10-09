import * as echarts from "echarts";

import * as api from "./api";
import * as chart from "./chart";
import * as download from "./download";
import * as table from "./table";
import * as types from "./types";

const CHART_SIZE = { width: 640, height: 340 };

function el<K extends keyof HTMLElementTagNameMap>(
    tag: K,
    className?: string,
    text?: string,
): HTMLElementTagNameMap[K] {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function button(label: string, onClick: () => void): HTMLButtonElement {
    const node = el("button", undefined, label);
    node.type = "button";
    node.addEventListener("click", onClick);
    return node;
}

function toPayload(block: api.ChartBlock): types.ChartPayload {
    return {
        queryUuid: block.query_uuid,
        rows: block.rows,
        fields: block.fields,
        exploreUrl: block.explore_url,
        args: block.query_args,
    };
}

function draw(payload: types.ChartPayload, vizType: types.VizType, target: HTMLElement): void {
    echarts.getInstanceByDom(target)?.dispose();
    target.replaceChildren();
    let rendered: ReturnType<typeof chart.render>;
    try {
        rendered = chart.render(payload, vizType, CHART_SIZE);
    } catch (error) {
        // A chart that cannot be drawn must not stop the rest of the conversation rendering.
        console.error("Chart render failed", { title: payload.args.title, vizType, error });
        target.textContent = `This chart could not be drawn as ${vizType}: ${describeError(error)}`;
        target.dataset.kind = "error";
        return;
    }
    if (rendered.kind === "echarts") {
        echarts.init(target, undefined, CHART_SIZE).setOption(rendered.option);
    } else if (rendered.kind === "table") {
        table.renderTable(target, rendered);
    } else {
        target.textContent = `Cannot draw this as a chart (${rendered.kind}).`;
    }
    target.dataset.kind = rendered.kind;
}

// Zod errors stringify as a JSON array; name the failing fields instead.
function describeError(error: unknown): string {
    const issues = (error as { issues?: { path: (string | number)[]; message: string }[] }).issues;
    if (!issues) return String(error);
    return issues.slice(0, 3).map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`).join("; ");
}

function initialViz(payload: types.ChartPayload): types.VizType {
    const requested = payload.args.chartConfig?.defaultVizType;
    return types.VIZ_TYPES.find((viz) => viz === requested) ?? "table";
}

export function renderCard(block: api.ChartBlock, versions: api.ChartBlock[]): HTMLElement {
    const card = el("section", "card");
    card.dataset.artifact = block.artifact_id;
    let payload = toPayload(block);
    let vizType = initialViz(payload);

    const heading = el("h3", undefined, `${block.title} · v${block.version}`);
    const body = el("div", "card-body");
    const controls = el("div", "controls");
    const editor = el("div", "editor");
    editor.hidden = true;

    const select = el("select");
    for (const viz of types.VIZ_TYPES) select.add(new Option(viz, viz, false, viz === vizType));
    select.addEventListener("change", () => {
        vizType = select.value as types.VizType;
        redraw();
    });

    const redraw = (): void => {
        draw(payload, vizType, body);
    };

    const csvButton = button("CSV", () => {
        const rendered = chart.render(payload, "table", CHART_SIZE);
        if (rendered.kind === "table") {
            download.downloadCsv(`${block.title}.csv`, download.tableToCsv(rendered.model));
        }
    });
    const pngButton = button("PNG", () => {
        const instance = echarts.getInstanceByDom(body);
        if (!instance) return;
        download.saveFile(
            `${block.title}.png`,
            instance.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" }),
        );
    });
    const editButton = button("Edit query", () => {
        editor.hidden = !editor.hidden;
    });
    const saveStatus = el("span", "save-status");
    const saveButton = button("Save", async () => {
        saveStatus.textContent = "Saving…";
        try {
            const saved = await api.saveChart(payload.args);
            const link = el("a", undefined, "Saved to Lightdash");
            link.href = saved.href;
            link.target = "_blank";
            link.rel = "noopener";
            saveStatus.replaceChildren(link);
        } catch (error) {
            saveStatus.textContent = String(error);
        }
    });
    controls.append(select, csvButton, pngButton, editButton, saveButton, saveStatus);

    // Opens an embedded explore of this query. A bare tab is used here; in Companion it would be a modal.
    controls.append(
        button("Explore", async () => {
            try {
                window.open(await api.exploreUrl(payload.args), "_blank", "noopener");
            } catch (error) {
                alert(String(error));
            }
        }),
    );

    if (versions.length > 1) {
        const switcher = el("span", "versions");
        for (const version of versions) {
            const chip = button(`v${version.version}`, () => {
                card.replaceWith(renderCard(version, versions));
            });
            chip.disabled = version.version === block.version;
            switcher.append(chip);
        }
        controls.append(switcher);
    }

    buildEditor(editor, payload, async (next) => {
        const status = editor.querySelector<HTMLElement>(".status");
        if (status) status.textContent = "Running…";
        try {
            payload = await api.rerunQuery(next);
            redraw();
            if (status) status.textContent = `Updated · ${payload.rows.length} rows (no LLM call)`;
        } catch (error) {
            if (status) status.textContent = String(error);
        }
    });

    card.append(heading, controls, editor, body);
    redraw();
    return card;
}

function buildEditor(
    container: HTMLElement,
    payload: types.ChartPayload,
    onRun: (args: types.ChartArgs) => Promise<void>,
): void {
    const config = payload.args.queryConfig;
    const dimensions = el("input");
    dimensions.value = config.dimensions.join(", ");
    dimensions.setAttribute("aria-label", "Dimensions");
    const metrics = el("input");
    metrics.value = config.metrics.join(", ");
    metrics.setAttribute("aria-label", "Metrics");
    const limit = el("input");
    limit.type = "number";
    limit.value = String(config.limit ?? 500);
    limit.setAttribute("aria-label", "Limit");

    const split = (value: string): string[] =>
        value.split(",").map((part) => part.trim()).filter(Boolean);
    const run = button("Re-run", () => {
        void onRun({
            ...payload.args,
            queryConfig: {
                ...config,
                dimensions: split(dimensions.value),
                metrics: split(metrics.value),
                limit: Number(limit.value) || null,
            },
        });
    });
    const labelled = (label: string, input: HTMLElement): HTMLElement => {
        const wrapper = el("label", undefined, label);
        wrapper.append(input);
        return wrapper;
    };
    container.append(
        labelled("Dimensions", dimensions),
        labelled("Metrics", metrics),
        labelled("Limit", limit),
        run,
        el("span", "status"),
    );
}
