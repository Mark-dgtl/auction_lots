/**
 * Минималистичные тосты для loading/success/error.
 * Подключается один контейнер #toasts (создаётся лениво).
 */

function ensureRoot() {
    let root = document.getElementById("toasts");
    if (!root) {
        root = document.createElement("div");
        root.id = "toasts";
        document.body.appendChild(root);
    }
    return root;
}

function push({ title, message, kind = "info", timeout = 4000 }) {
    const root = ensureRoot();
    const el = document.createElement("div");
    el.className = `toast toast-${kind}`;
    el.setAttribute("role", kind === "error" ? "alert" : "status");
    el.innerHTML = `
        <div class="toast-body">
            ${title ? `<div class="toast-title"></div>` : ""}
            <div class="toast-message"></div>
        </div>
        <button type="button" class="toast-close" aria-label="Закрыть">×</button>
    `;
    if (title) el.querySelector(".toast-title").textContent = title;
    el.querySelector(".toast-message").textContent = message;
    el.querySelector(".toast-close").addEventListener("click", () => dismiss(el));
    root.appendChild(el);

    if (timeout > 0) setTimeout(() => dismiss(el), timeout);
    return el;
}

function dismiss(el) {
    if (!el || !el.parentNode) return;
    el.style.opacity = "0";
    el.style.transform = "translateY(6px)";
    el.style.transition = "opacity 160ms ease, transform 160ms ease";
    setTimeout(() => el.remove(), 180);
}

export const toast = {
    info(message, title) { return push({ kind: "info", title, message }); },
    success(message, title) { return push({ kind: "success", title, message }); },
    error(message, title) { return push({ kind: "error", title, message, timeout: 6000 }); },
    fromApiError(e) {
        const msg = e && e.message ? e.message : "Неизвестная ошибка";
        return push({ kind: "error", message: msg, timeout: 6000 });
    },
    dismiss,
};
