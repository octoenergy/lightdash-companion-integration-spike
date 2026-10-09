import * as visualization from "@lightdash/visualization";

function escapeCell(value: string): string {
    return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

export function tableToCsv(model: visualization.TableModel): string {
    const columns = model.columns.filter((column) => column.isVisible);
    const header = columns.map((column) => escapeCell(column.labelOverride ?? column.header.label));
    const lines = model.rows.map((row) =>
        columns.map((column) => escapeCell(row[column.id]?.value.formatted ?? "")).join(","),
    );
    return [header.join(","), ...lines].join("\n");
}

export function saveFile(filename: string, href: string): void {
    const link = document.createElement("a");
    link.href = href;
    link.download = filename;
    link.click();
}

export function downloadCsv(filename: string, csv: string): void {
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    saveFile(filename, url);
    URL.revokeObjectURL(url);
}
