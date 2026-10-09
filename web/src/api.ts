import * as types from "./types";

export type ChartBlock = {
    type: "lightdash_chart";
    artifact_id: string;
    version: number;
    title: string;
    query_uuid: string;
    query_args: types.ChartArgs;
    rows: types.RawRow[];
    fields: Record<string, unknown>;
    explore_url: string | null;
};

export type Block =
    | { type: "markdown"; text: string }
    | ChartBlock
    | { type: "follow_ups"; suggestions: string[] };

export type Message = {
    id: string;
    role: "user" | "assistant";
    text: string;
    blocks: Block[];
    feedback: string | null;
};

export type SseHandlers = {
    onStep: (step: string) => void;
    onAnswer: (answer: { id: string; blocks: Block[] }) => void;
    onError: (message: string) => void;
};

export async function createThread(): Promise<string> {
    const response = await fetch("/api/threads", { method: "POST" });
    return (await response.json()).id;
}

export async function listThreads(): Promise<{ id: string; title: string }[]> {
    return (await fetch("/api/threads")).json();
}

export async function getThread(threadId: string): Promise<Message[]> {
    return (await fetch(`/api/threads/${threadId}`)).json();
}

export async function sendFeedback(messageId: string, rating: "up" | "down"): Promise<void> {
    await fetch(`/api/messages/${messageId}/feedback`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ rating }),
    });
}

export async function rerunQuery(args: types.ChartArgs): Promise<types.ChartPayload> {
    const response = await fetch("/api/queries/rerun", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
            title: args.title,
            description: args.description,
            query_config: args.queryConfig,
        }),
    });
    if (!response.ok) throw new Error((await response.json()).detail ?? "Query failed");
    const result = await response.json();
    return { ...result, args };
}

// EventSource can't POST, so the stream is read by hand.
export async function streamAnswer(
    threadId: string,
    text: string,
    handlers: SseHandlers,
): Promise<void> {
    const response = await fetch(`/api/threads/${threadId}/messages`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text }),
    });
    const reader = response.body?.getReader();
    if (!reader) return;
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() ?? "";
        for (const frame of frames) dispatch(frame, handlers);
    }
}

function dispatch(frame: string, handlers: SseHandlers): void {
    let event = "message";
    let data = "";
    for (const line of frame.split(/\r?\n/)) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    if (!data) return;
    const payload = JSON.parse(data);
    if (event === "tool_step") handlers.onStep(payload.step);
    else if (event === "answer") handlers.onAnswer(payload);
    else if (event === "error") handlers.onError(payload.message);
}

export async function exploreUrl(args: types.ChartArgs): Promise<string> {
    const response = await fetch("/api/explore-url", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ query_config: args.queryConfig }),
    });
    if (!response.ok) throw new Error((await response.json()).detail ?? "Explore unavailable");
    return (await response.json()).url;
}

export async function saveChart(args: types.ChartArgs): Promise<{ href: string }> {
    const response = await fetch("/api/charts/save", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
            title: args.title,
            description: args.description,
            query_config: args.queryConfig,
        }),
    });
    if (!response.ok) throw new Error((await response.json()).detail ?? "Save failed");
    return response.json();
}
