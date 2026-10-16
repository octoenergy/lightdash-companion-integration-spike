import * as api from "./api";
import * as mcpApp from "./mcp_app";

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

function saveAction(block: api.ChartBlock): HTMLElement {
    const status = el("span", "save-status");
    const save = button("Save", async () => {
        status.textContent = "Saving…";
        try {
            const saved = await api.saveChart(block.query_args);
            const link = el("a", undefined, "Saved to Lightdash");
            link.href = saved.href;
            link.target = "_blank";
            link.rel = "noopener";
            status.replaceChildren(link);
        } catch (error) {
            status.textContent = String(error);
        }
    });
    const wrapper = el("span", "action");
    wrapper.append(save, status);
    return wrapper;
}

// Opens an embedded explore of this query. A bare tab is used here; in Companion it would be a modal.
function exploreAction(block: api.ChartBlock): HTMLElement {
    return button("Explore", async () => {
        try {
            window.open(await api.exploreUrl(block.query_args), "_blank", "noopener");
        } catch (error) {
            alert(String(error));
        }
    });
}

async function showApp(block: api.ChartBlock, target: HTMLElement): Promise<void> {
    if (!block.app_input || !block.app_result) {
        target.textContent = "This chart has no MCP App result stored.";
        target.dataset.kind = "error";
        return;
    }
    try {
        await mcpApp.mount(target, { input: block.app_input, result: block.app_result });
    } catch (error) {
        console.error("MCP App render failed", { title: block.title, error });
        target.textContent = `The MCP App could not be shown: ${String(error)}`;
        target.dataset.kind = "error";
    }
}

export function renderCard(block: api.ChartBlock): HTMLElement {
    const card = el("section", "card");
    card.dataset.artifact = block.artifact_id;
    const heading = el("h3", undefined, `${block.title} · v${block.version}`);
    const body = el("div", "card-body");
    const actions = el("div", "controls");
    actions.append(saveAction(block), exploreAction(block));
    card.append(heading, body, actions);
    void showApp(block, body);
    return card;
}
