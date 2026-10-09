import * as visualization from "@lightdash/visualization";

export function renderTable(
    container: HTMLElement,
    rendered: Extract<visualization.RenderedChart, { kind: "table" }>,
): void {
    const columns = rendered.model.columns.filter((column) => column.isVisible);
    const table = document.createElement("table");
    const head = table.createTHead().insertRow();
    for (const column of columns) {
        head.insertCell().textContent = column.labelOverride ?? column.header.label;
    }
    const body = table.createTBody();
    for (const row of rendered.model.rows) {
        const tr = body.insertRow();
        for (const column of columns) {
            tr.insertCell().textContent = row[column.id]?.value.formatted ?? "";
        }
    }
    container.replaceChildren(table);
}
