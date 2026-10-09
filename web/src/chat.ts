import * as api from "./api";
import * as card from "./card";

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

function chartsByArtifact(messages: api.Message[]): Map<string, api.ChartBlock[]> {
    const grouped = new Map<string, api.ChartBlock[]>();
    for (const message of messages) {
        for (const block of message.blocks) {
            if (block.type !== "lightdash_chart") continue;
            grouped.set(block.artifact_id, [...(grouped.get(block.artifact_id) ?? []), block]);
        }
    }
    return grouped;
}

export class Chat {
    private threadId: string | null = null;
    private messages: api.Message[] = [];
    private readonly log = el("div", "log");
    private readonly status = el("div", "status-line");
    private readonly input = el("input");
    private readonly threadList = el("ul", "threads");

    constructor(private readonly root: HTMLElement) {}

    async start(): Promise<void> {
        const form = el("form", "composer");
        this.input.placeholder = "Ask a data question…";
        const send = el("button", undefined, "Send");
        form.append(this.input, send);
        form.addEventListener("submit", (event) => {
            event.preventDefault();
            const text = this.input.value.trim();
            if (text) void this.ask(text);
        });
        const newChat = el("button", undefined, "New chat");
        newChat.addEventListener("click", () => void this.open(null));
        const side = el("aside");
        side.append(newChat, this.threadList);
        const main = el("main");
        main.append(this.log, this.status, form);
        this.root.append(side, main);
        await this.refreshThreads();
        const threads = await api.listThreads();
        await this.open(threads[0]?.id ?? null);
    }

    private async refreshThreads(): Promise<void> {
        const threads = await api.listThreads();
        this.threadList.replaceChildren(
            ...threads.map((thread) => {
                const item = el("li");
                const open = el("button", undefined, thread.title);
                open.addEventListener("click", () => void this.open(thread.id));
                item.append(open);
                return item;
            }),
        );
    }

    private async open(threadId: string | null): Promise<void> {
        this.threadId = threadId;
        this.messages = threadId ? await api.getThread(threadId) : [];
        this.render();
    }

    private render(): void {
        const charts = chartsByArtifact(this.messages);
        this.log.replaceChildren(
            ...this.messages.map((message) => this.renderMessageSafely(message, charts)),
        );
        this.log.scrollTop = this.log.scrollHeight;
    }

    private renderMessageSafely(message: api.Message, charts: Map<string, api.ChartBlock[]>): HTMLElement {
        try {
            return this.renderMessage(message, charts);
        } catch (error) {
            console.error("Message render failed", { id: message.id, error });
            const failed = el("article", `message ${message.role} render-error`);
            failed.textContent = `Could not display this message. ${message.text}`;
            return failed;
        }
    }

    private renderMessage(message: api.Message, charts: Map<string, api.ChartBlock[]>): HTMLElement {
        const wrapper = el("article", `message ${message.role}`);
        wrapper.dataset.id = message.id;
        for (const block of message.blocks) {
            if (block.type === "markdown") wrapper.append(el("p", undefined, block.text));
            else if (block.type === "lightdash_chart") {
                wrapper.append(card.renderCard(block, charts.get(block.artifact_id) ?? [block]));
            } else if (block.type === "follow_ups") {
                const chips = el("div", "chips");
                for (const suggestion of block.suggestions) {
                    const chip = el("button", "chip", suggestion);
                    chip.addEventListener("click", () => void this.ask(suggestion));
                    chips.append(chip);
                }
                wrapper.append(chips);
            }
        }
        if (message.role === "assistant") wrapper.append(this.feedbackButtons(message));
        return wrapper;
    }

    private feedbackButtons(message: api.Message): HTMLElement {
        const row = el("div", "feedback");
        for (const rating of ["up", "down"] as const) {
            const button = el("button", undefined, rating === "up" ? "👍" : "👎");
            button.setAttribute("aria-label", `Thumbs ${rating}`);
            button.setAttribute("aria-pressed", String(message.feedback === rating));
            button.addEventListener("click", async () => {
                await api.sendFeedback(message.id, rating);
                message.feedback = rating;
                this.render();
            });
            row.append(button);
        }
        return row;
    }

    private async ask(text: string): Promise<void> {
        if (!this.threadId) this.threadId = await api.createThread();
        const threadId = this.threadId;
        this.input.value = "";
        this.input.disabled = true;
        this.messages.push({ id: "pending", role: "user", text, blocks: [{ type: "markdown", text }], feedback: null });
        this.render();
        let failure: string | null = null;
        try {
            await api.streamAnswer(threadId, text, {
                onStep: (step) => (this.status.textContent = step),
                onAnswer: () => undefined,
                onError: (message) => (failure = message),
            });
        } catch (error) {
            failure = String(error);
        }
        this.status.textContent = failure ? `Something went wrong: ${failure}` : "";
        this.status.classList.toggle("error", failure !== null);
        this.input.disabled = false;
        await this.open(threadId);
        await this.refreshThreads();
    }
}
