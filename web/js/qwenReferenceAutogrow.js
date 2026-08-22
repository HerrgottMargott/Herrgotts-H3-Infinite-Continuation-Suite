import { app } from "../../scripts/app.js";

const TARGET_CLASSES = new Set([
    "H3ContinuousStartV13",
    "H3ContinuousContinueV13",
    "H3ContinuousStartV14",
    "H3ContinuousContinueV14",
]);
const PREFIX = "qwen_reference_";
const MAX_REFERENCES = 9;
const NAME_RE = /^qwen_reference_([1-9])$/;

function targetNames(node) {
    return new Set([
        node?.type,
        node?.comfyClass,
        node?.constructor?.type,
        node?.constructor?.comfyClass,
        node?.constructor?.ComfyClass,
        node?.constructor?.nodeData?.name,
    ].filter(Boolean));
}

function isTarget(node) {
    for (const name of targetNames(node)) {
        if (TARGET_CLASSES.has(name)) return true;
    }
    return false;
}

function isTargetDefinition(nodeType, nodeData) {
    const names = [
        nodeData?.name,
        nodeType?.type,
        nodeType?.comfyClass,
        nodeType?.ComfyClass,
        nodeType?.nodeData?.name,
    ].filter(Boolean);
    return names.some((name) => TARGET_CLASSES.has(name));
}

function qwenIndex(input) {
    const match = NAME_RE.exec(String(input?.name ?? ""));
    return match ? Number(match[1]) : null;
}

function isConnected(input) {
    if (!input) return false;
    if (input.link !== null && input.link !== undefined) return true;
    if (Array.isArray(input.links) && input.links.length > 0) return true;
    return false;
}

function setLabels(node) {
    for (const input of node?.inputs ?? []) {
        const index = qwenIndex(input);
        if (index !== null) input.label = `Qwen Reference ${index}`;
        if (input?.name === "first_frame") input.label = "First Frame";
        if (input?.name === "last_frame") input.label = "Last Frame";
    }
}

function findInput(node, name) {
    return (node?.inputs ?? []).find((input) => input?.name === name);
}

function addQwenInput(node, index) {
    if (!node || index < 1 || index > MAX_REFERENCES) return;
    const name = `${PREFIX}${index}`;
    if (findInput(node, name)) return;
    const slot = node.addInput?.(name, "IMAGE");
    const input = slot ?? findInput(node, name);
    if (input) input.label = `Qwen Reference ${index}`;
}

function refreshNodeLayout(node) {
    node?.setDirtyCanvas?.(true, true);
    node?.graph?.setDirtyCanvas?.(true, true);
    requestAnimationFrame(() => {
        try {
            if (typeof node?.computeSize !== "function" || typeof node?.setSize !== "function") return;
            const computed = node.computeSize();
            if (!Array.isArray(computed) || !Number.isFinite(computed[0]) || !Number.isFinite(computed[1])) return;
            const currentWidth = Array.isArray(node.size) && Number.isFinite(node.size[0])
                ? node.size[0]
                : computed[0];
            node.setSize([Math.max(currentWidth, computed[0]), computed[1]]);
        } catch (_) {
            // The frontend will recalculate layout on its next pass.
        }
    });
}

function reconcileQwenInputs(node) {
    if (!isTarget(node) || !Array.isArray(node.inputs)) return;
    if (node.__herrgottsQwenAutogrowReconciling) return;
    node.__herrgottsQwenAutogrowReconciling = true;
    try {
        // qwen_reference_1 is supplied by INPUT_TYPES. This fallback also makes
        // partially migrated / manually edited workflows self-heal.
        addQwenInput(node, 1);

        const qwenInputs = (node.inputs ?? [])
            .map((input) => ({ input, index: qwenIndex(input) }))
            .filter((entry) => entry.index !== null)
            .sort((a, b) => a.index - b.index);

        let highestConnected = 0;
        for (const { input, index } of qwenInputs) {
            if (isConnected(input)) highestConnected = Math.max(highestConnected, index);
        }

        // Always keep one empty socket after the highest connected reference,
        // unless the user has reached the explicit v1.3 cap of nine images.
        const desiredHighest = Math.min(MAX_REFERENCES, Math.max(1, highestConnected + 1));
        for (let index = 1; index <= desiredHighest; index += 1) {
            addQwenInput(node, index);
        }

        // Remove only unused trailing dynamic sockets. Never touch a connected
        // socket or an internal gap, so graph links and Picture ordinals stay stable.
        for (let slot = node.inputs.length - 1; slot >= 0; slot -= 1) {
            const input = node.inputs[slot];
            const index = qwenIndex(input);
            if (index === null || index <= desiredHighest || isConnected(input)) continue;
            node.removeInput?.(slot);
        }

        setLabels(node);
        refreshNodeLayout(node);
    } finally {
        node.__herrgottsQwenAutogrowReconciling = false;
    }
}

function scheduleReconcile(node) {
    queueMicrotask(() => reconcileQwenInputs(node));
}

app.registerExtension({
    name: "Herrgotts.H3Infinite.QwenReferenceAutogrow.v140",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!isTargetDefinition(nodeType, nodeData)) return;

        const originalOnConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function (...args) {
            const result = originalOnConnectionsChange?.apply(this, args);
            scheduleReconcile(this);
            return result;
        };

        const originalOnConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (...args) {
            const result = originalOnConfigure?.apply(this, args);
            scheduleReconcile(this);
            return result;
        };
    },

    async nodeCreated(node) {
        if (isTarget(node)) scheduleReconcile(node);
    },

    loadedGraphNode(node) {
        if (isTarget(node)) scheduleReconcile(node);
    },

    async afterConfigureGraph() {
        for (const node of app.graph?._nodes ?? []) {
            if (isTarget(node)) reconcileQwenInputs(node);
        }
    },
});
