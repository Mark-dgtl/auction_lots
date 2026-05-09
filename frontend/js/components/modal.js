/**
 * Простые модальные окна. Возвращают Promise<boolean|any>.
 * confirm(title, message, {okText, cancelText})
 * prompt(title, message, {initial, placeholder, okText, cancelText}) -> string|null
 */

function buildOverlay() {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    return overlay;
}

function close(overlay, resolve, value) {
    document.body.style.overflow = "";
    overlay.remove();
    document.removeEventListener("keydown", overlay._esc);
    resolve(value);
}

export function confirm(title, message, opts = {}) {
    return new Promise((resolve) => {
        const overlay = buildOverlay();
        overlay.innerHTML = `
            <div class="modal">
                <h3 class="modal-title"></h3>
                <div class="modal-body"></div>
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary" data-act="cancel"></button>
                    <button type="button" class="btn btn-primary" data-act="ok"></button>
                </div>
            </div>
        `;
        overlay.querySelector(".modal-title").textContent = title;
        overlay.querySelector(".modal-body").textContent = message;
        overlay.querySelector('[data-act="ok"]').textContent = opts.okText || "OK";
        overlay.querySelector('[data-act="cancel"]').textContent =
            opts.cancelText || "Отмена";

        overlay.addEventListener("click", (e) => {
            if (e.target === overlay) close(overlay, resolve, false);
        });
        overlay.querySelector('[data-act="cancel"]').addEventListener("click", () =>
            close(overlay, resolve, false),
        );
        overlay.querySelector('[data-act="ok"]').addEventListener("click", () =>
            close(overlay, resolve, true),
        );

        overlay._esc = (e) => {
            if (e.key === "Escape") close(overlay, resolve, false);
        };
        document.addEventListener("keydown", overlay._esc);

        document.body.style.overflow = "hidden";
        document.body.appendChild(overlay);
        overlay.querySelector('[data-act="ok"]').focus();
    });
}

export function prompt(title, message, opts = {}) {
    return new Promise((resolve) => {
        const overlay = buildOverlay();
        overlay.innerHTML = `
            <div class="modal">
                <h3 class="modal-title"></h3>
                <div class="modal-body">
                    <p class="muted" style="margin-bottom: var(--space-3)"></p>
                    <input type="text" class="input" />
                </div>
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary" data-act="cancel"></button>
                    <button type="button" class="btn btn-primary" data-act="ok"></button>
                </div>
            </div>
        `;
        overlay.querySelector(".modal-title").textContent = title;
        overlay.querySelector(".modal-body p").textContent = message;
        const input = overlay.querySelector("input");
        input.value = opts.initial || "";
        if (opts.placeholder) input.placeholder = opts.placeholder;
        overlay.querySelector('[data-act="ok"]').textContent =
            opts.okText || "Сохранить";
        overlay.querySelector('[data-act="cancel"]').textContent =
            opts.cancelText || "Отмена";

        overlay.addEventListener("click", (e) => {
            if (e.target === overlay) close(overlay, resolve, null);
        });
        overlay.querySelector('[data-act="cancel"]').addEventListener("click", () =>
            close(overlay, resolve, null),
        );
        overlay.querySelector('[data-act="ok"]').addEventListener("click", () => {
            const v = input.value.trim();
            if (!v) {
                input.focus();
                return;
            }
            close(overlay, resolve, v);
        });
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                overlay.querySelector('[data-act="ok"]').click();
            }
        });

        overlay._esc = (e) => {
            if (e.key === "Escape") close(overlay, resolve, null);
        };
        document.addEventListener("keydown", overlay._esc);

        document.body.style.overflow = "hidden";
        document.body.appendChild(overlay);
        input.focus();
        input.select();
    });
}
