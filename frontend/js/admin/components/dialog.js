/**
 * Расширенные модальные диалоги для админки.
 *
 * confirm/prompt берём из общего `js/components/modal.js`, плюс
 * добавляем `custom(...)` — окно с произвольным HTML и собственными
 * кнопками. Это нужно для подтверждения рассылки (с превью, числом
 * получателей и т.п.) и других нестандартных сценариев.
 */

export { confirm, prompt } from "../../components/modal.js";

/**
 * Универсальное модальное окно с произвольным телом.
 *
 * @param {object}   opts
 * @param {string}   opts.title       — заголовок
 * @param {string}   opts.bodyHtml    — innerHTML тела (HTML-строка)
 * @param {string}   [opts.okText]    — текст «OK»-кнопки
 * @param {string}   [opts.cancelText]— текст «Отмена»-кнопки
 * @param {boolean}  [opts.danger]    — окрасить OK как опасный
 * @param {(root: HTMLElement) => void} [opts.onMount] — вызывается после
 *        вставки модалки в DOM, удобно навешать обработчики на инпуты тела
 * @param {(root: HTMLElement) => any}  [opts.collect] — вызывается на ОК,
 *        возвращает значение, которое будет результатом promise. Если
 *        возвращает `null` или `undefined` — закрытие отменяется.
 *
 * @returns {Promise<any|null>} — `null` если пользователь отменил
 */
export function custom({
    title,
    bodyHtml,
    okText = "OK",
    cancelText = "Отмена",
    danger = false,
    onMount,
    collect,
} = {}) {
    return new Promise((resolve) => {
        const overlay = document.createElement("div");
        overlay.className = "modal-overlay";
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-modal", "true");
        overlay.innerHTML = `
            <div class="modal" style="max-width: 560px">
                <h3 class="modal-title"></h3>
                <div class="modal-body"></div>
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary" data-act="cancel"></button>
                    <button type="button" class="btn ${danger ? "btn-danger" : "btn-primary"}" data-act="ok"></button>
                </div>
            </div>
        `;
        const titleEl = overlay.querySelector(".modal-title");
        const bodyEl = overlay.querySelector(".modal-body");
        const okBtn = overlay.querySelector('[data-act="ok"]');
        const cancelBtn = overlay.querySelector('[data-act="cancel"]');

        titleEl.textContent = title || "";
        bodyEl.innerHTML = bodyHtml || "";
        okBtn.textContent = okText;
        cancelBtn.textContent = cancelText;

        const close = (val) => {
            document.body.style.overflow = "";
            document.removeEventListener("keydown", onEsc);
            overlay.remove();
            resolve(val);
        };
        const onEsc = (e) => { if (e.key === "Escape") close(null); };

        overlay.addEventListener("click", (e) => {
            if (e.target === overlay) close(null);
        });
        cancelBtn.addEventListener("click", () => close(null));
        okBtn.addEventListener("click", () => {
            if (typeof collect === "function") {
                const v = collect(bodyEl);
                if (v == null || v === false) return;
                close(v);
            } else {
                close(true);
            }
        });

        document.addEventListener("keydown", onEsc);
        document.body.style.overflow = "hidden";
        document.body.appendChild(overlay);
        if (typeof onMount === "function") onMount(bodyEl);
        okBtn.focus();
    });
}
