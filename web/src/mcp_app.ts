import * as appBridge from "@modelcontextprotocol/ext-apps/app-bridge";

import * as api from "./api";
import * as types from "./types";

const HOST_INFO = { name: "lightdash-companion-spike", version: "0.0.0" };
const FRAME_HEIGHT = 380;

let cachedHtml: Promise<string> | null = null;

function loadHtml(): Promise<string> {
    cachedHtml ??= api.mcpAppHtml();
    return cachedHtml;
}

function createFrame(html: string): HTMLIFrameElement {
    const frame = document.createElement("iframe");
    // Without allow-same-origin the app's origin is opaque, so it cannot reach this page's cookies or DOM.
    frame.setAttribute("sandbox", "allow-scripts");
    frame.style.width = "100%";
    frame.style.height = `${FRAME_HEIGHT}px`;
    frame.style.border = "0";
    frame.srcdoc = html;
    return frame;
}

function waitForLoad(frame: HTMLIFrameElement): Promise<void> {
    return new Promise((resolve) => frame.addEventListener("load", () => resolve(), { once: true }));
}

export async function mount(target: HTMLElement, app: types.AppRender): Promise<void> {
    const html = await loadHtml();

    const frame = createFrame(html);
    const loaded = waitForLoad(frame);
    target.replaceChildren(frame);
    await loaded;

    const bridge = new appBridge.AppBridge(null, HOST_INFO, { openLinks: {} });
    bridge.oninitialized = () => {
        void bridge.sendToolInput({ arguments: app.input });
        void bridge.sendToolResult(app.result as Parameters<typeof bridge.sendToolResult>[0]);
    };
    bridge.onsizechange = ({ height }) => {
        if (height !== undefined) frame.style.height = `${height}px`;
    };
    bridge.onopenlink = async ({ url }) => {
        window.open(url, "_blank", "noopener");
        return {};
    };

    const contentWindow = frame.contentWindow;
    if (!contentWindow) throw new Error("MCP App frame has no window");
    await bridge.connect(new appBridge.PostMessageTransport(contentWindow, contentWindow));
}
