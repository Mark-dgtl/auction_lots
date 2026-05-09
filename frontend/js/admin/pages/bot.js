/**
 * Бот: личные сообщения и рассылка.
 *
 * Личное сообщение:
 *  - autocomplete по email через /api/admin/users?q=
 *  - textarea, parse_mode (none|html|markdown), кнопка отправить
 *  - превью (для html/markdown — отображаем «как есть» в монospace,
 *    чтобы админ увидел итоговый текст без сюрпризов)
 *
 * Рассылка:
 *  - textarea, parse_mode
 *  - audience: чекбоксы has_telegram (всегда), has_filter (с уведомл.),
 *    + список user_ids через запятую
 *  - перед отправкой — модалка с подтверждением
 */

import { adminApi } from "../api.js";
import { custom } from "../components/dialog.js";
import { toast } from "../../components/toast.js";
import { escapeHtml } from "../components/table.js";
import { debounce } from "../../utils.js";

let activeTab = "dm";

export async function mount(root) {
    activeTab = "dm";
    root.innerHTML = `
        <div class="admin-page-header">
            <div>
                <h1>Bot</h1>
                <div class="subtitle">Ручная отправка сообщений в Telegram через outbox.</div>
            </div>
        </div>

        <div class="tabs" id="bot-tabs">
            <button type="button" class="tab active" data-tab="dm">Личное сообщение</button>
            <button type="button" class="tab" data-tab="broadcast">Рассылка</button>
        </div>

        <div id="bot-pane"></div>
    `;
    root.querySelector("#bot-tabs").addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-tab]");
        if (!btn) return;
        activeTab = btn.dataset.tab;
        root.querySelectorAll("#bot-tabs .tab")
            .forEach((t) => t.classList.toggle("active", t === btn));
        renderPane();
    });
    renderPane();

    function renderPane() {
        const pane = document.getElementById("bot-pane");
        if (activeTab === "dm") renderDm(pane);
        else renderBroadcast(pane);
    }
}

export function unmount() { /* no-op */ }

/* ---------------- Personal message ---------------- */

function renderDm(pane) {
    pane.innerHTML = `
        <div class="composer-grid">
            <section class="admin-card">
                <h3 class="card-title">Получатель и текст</h3>
                <form id="dm-form">
                    <div class="field autocomplete">
                        <label for="dm-email">Email пользователя</label>
                        <input id="dm-email" class="input" autocomplete="off"
                               placeholder="user@example.com">
                        <input type="hidden" id="dm-user-id" name="user_id">
                        <div class="autocomplete-list hidden" id="dm-suggest"></div>
                        <span class="hint" id="dm-pick-hint">Найдите пользователя через поиск</span>
                    </div>
                    <div class="field">
                        <label for="dm-mode">Parse mode</label>
                        <select id="dm-mode" class="select" style="max-width: 180px">
                            <option value="">none</option>
                            <option value="html">html</option>
                            <option value="markdown">markdown</option>
                        </select>
                    </div>
                    <div class="field">
                        <label for="dm-text">Текст сообщения</label>
                        <textarea id="dm-text" class="textarea" rows="8"
                                  placeholder="Привет!"></textarea>
                    </div>
                    <button type="submit" class="btn btn-primary">Отправить</button>
                </form>
            </section>

            <section class="admin-card">
                <h3 class="card-title">Превью</h3>
                <div class="preview-pane" id="dm-preview"><span class="muted">Текст пуст</span></div>
            </section>
        </div>
    `;

    const emailInput   = pane.querySelector("#dm-email");
    const userIdInput  = pane.querySelector("#dm-user-id");
    const suggestEl    = pane.querySelector("#dm-suggest");
    const pickHint     = pane.querySelector("#dm-pick-hint");
    const textArea     = pane.querySelector("#dm-text");
    const previewEl    = pane.querySelector("#dm-preview");

    wireAutocomplete(emailInput, suggestEl, (u) => {
        userIdInput.value = u.id;
        emailInput.value = u.email;
        pickHint.textContent = `Выбран: ${u.email} (id ${u.id})${u.telegram_linked ? "" : " — TG не привязан"}`;
        suggestEl.classList.add("hidden");
    });

    emailInput.addEventListener("input", () => {
        userIdInput.value = "";
        pickHint.textContent = "Найдите пользователя через поиск";
    });

    textArea.addEventListener("input", () => {
        const t = textArea.value;
        previewEl.textContent = t || "";
        if (!t) previewEl.innerHTML = '<span class="muted">Текст пуст</span>';
    });

    pane.querySelector("#dm-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const userId = Number(userIdInput.value);
        const text = textArea.value.trim();
        const parse_mode = pane.querySelector("#dm-mode").value || null;

        if (!userId) { toast.error("Выберите получателя из списка"); return; }
        if (!text)   { toast.error("Текст сообщения пуст"); return; }

        const submit = e.currentTarget.querySelector('button[type="submit"]');
        submit.disabled = true;
        try {
            const r = await adminApi.botSend({ user_id: userId, text, parse_mode });
            const warn = r && r.warning === "BOT_OFFLINE"
                ? " · бот offline, сообщение в очереди"
                : "";
            toast.success(`Поставлено в outbox #${r.outbox_id}${warn}`);
            textArea.value = "";
            previewEl.innerHTML = '<span class="muted">Текст пуст</span>';
        } catch (err) {
            toast.fromApiError(err);
        } finally {
            submit.disabled = false;
        }
    });
}

/* ---------------- Broadcast ---------------- */

function renderBroadcast(pane) {
    pane.innerHTML = `
        <div class="composer-grid">
            <section class="admin-card">
                <h3 class="card-title">Текст рассылки</h3>
                <form id="bc-form">
                    <div class="field">
                        <label for="bc-mode">Parse mode</label>
                        <select id="bc-mode" class="select" style="max-width: 180px">
                            <option value="">none</option>
                            <option value="html">html</option>
                            <option value="markdown">markdown</option>
                        </select>
                    </div>
                    <div class="field">
                        <label for="bc-text">Сообщение</label>
                        <textarea id="bc-text" class="textarea" rows="10"
                                  placeholder="Внимание! ..."></textarea>
                    </div>
                    <button type="submit" class="btn btn-primary">Отправить</button>
                </form>
            </section>

            <section class="admin-card">
                <h3 class="card-title">Аудитория</h3>
                <div class="field">
                    <label class="checkbox">
                        <input type="checkbox" id="bc-has-tg" checked disabled>
                        Только пользователи с привязанным Telegram
                    </label>
                    <span class="hint">Сообщение бесполезно для тех, у кого нет TG.</span>
                </div>
                <div class="field">
                    <label class="checkbox">
                        <input type="checkbox" id="bc-has-filter">
                        Только с включёнными уведомлениями (есть фильтр с notify=true)
                    </label>
                </div>
                <div class="field">
                    <label for="bc-ids">user_ids через запятую (необязательно)</label>
                    <input id="bc-ids" class="input" placeholder="1, 2, 7">
                    <span class="hint">Если указать — отправим только этим пользователям. Остальные критерии будут проигнорированы бэкендом.</span>
                </div>
            </section>
        </div>

        <div style="height: var(--space-4)"></div>

        <section class="admin-card">
            <h3 class="card-title">Превью</h3>
            <div class="preview-pane" id="bc-preview"><span class="muted">Текст пуст</span></div>
        </section>
    `;

    const textArea = pane.querySelector("#bc-text");
    const previewEl = pane.querySelector("#bc-preview");
    textArea.addEventListener("input", () => {
        previewEl.textContent = textArea.value || "";
        if (!textArea.value) previewEl.innerHTML = '<span class="muted">Текст пуст</span>';
    });

    pane.querySelector("#bc-form").addEventListener("submit", (e) => onBroadcast(e, pane));
}

async function onBroadcast(e, pane) {
    e.preventDefault();
    const form = e.currentTarget;
    const submit = form.querySelector('button[type="submit"]');

    const text = pane.querySelector("#bc-text").value.trim();
    const parse_mode = pane.querySelector("#bc-mode").value || null;
    const idsRaw = pane.querySelector("#bc-ids").value.trim();
    const has_filter = pane.querySelector("#bc-has-filter").checked;

    if (!text) { toast.error("Текст пуст"); return; }

    const audience = { has_telegram: true };
    if (has_filter) audience.has_filter = true;
    if (idsRaw) {
        const ids = idsRaw
            .split(/[,\s]+/)
            .map((s) => Number(s.trim()))
            .filter((n) => Number.isInteger(n) && n > 0);
        if (!ids.length) {
            toast.error("Не удалось разобрать user_ids");
            return;
        }
        audience.user_ids = ids;
    }

    const audSummary = describeAudience(audience);

    const ok = await custom({
        title: "Подтверждение рассылки",
        bodyHtml: `
            <p style="margin-bottom: var(--space-3)">Вы собираетесь отправить рассылку.</p>
            <dl class="kv-list">
                <dt>Аудитория</dt><dd>${escapeHtml(audSummary)}</dd>
                <dt>parse_mode</dt><dd>${escapeHtml(parse_mode || "none")}</dd>
                <dt>Длина</dt><dd>${text.length} симв.</dd>
            </dl>
            <div class="divider"></div>
            <div class="preview-pane" style="max-height: 200px"></div>
        `,
        okText: "Отправить",
        cancelText: "Отмена",
        danger: true,
        onMount: (body) => {
            body.querySelector(".preview-pane").textContent = text;
        },
    });
    if (!ok) return;

    submit.disabled = true;
    try {
        const r = await adminApi.botBroadcast({ text, parse_mode, audience });
        toast.success(`Поставлено в очередь: ${r.queued ?? "?"}`);
    } catch (err) {
        toast.fromApiError(err);
    } finally {
        submit.disabled = false;
    }
}

function describeAudience(a) {
    if (a.user_ids) return `по списку (${a.user_ids.length} id)`;
    const parts = ["с TG"];
    if (a.has_filter) parts.push("+ с уведомлениями");
    return parts.join(" ");
}

/* ---------------- Autocomplete ---------------- */

function wireAutocomplete(input, listEl, onPick) {
    let activeIdx = -1;
    let lastResults = [];

    const close = () => {
        listEl.classList.add("hidden");
        listEl.innerHTML = "";
        activeIdx = -1;
    };

    const render = (items) => {
        if (!items.length) { close(); return; }
        listEl.innerHTML = "";
        items.forEach((u, idx) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.dataset.idx = String(idx);
            btn.innerHTML = `
                <strong>${escapeHtml(u.email)}</strong>
                <span class="muted" style="margin-left: 6px">id ${u.id}</span>
                ${u.telegram_linked
                    ? '<span class="status-pill ok" style="margin-left:6px">TG</span>'
                    : '<span class="status-pill failed" style="margin-left:6px">no TG</span>'}
            `;
            btn.addEventListener("mousedown", (e) => {
                // mousedown а не click, чтобы успеть до blur'а инпута
                e.preventDefault();
                onPick(u);
            });
            listEl.appendChild(btn);
        });
        listEl.classList.remove("hidden");
    };

    const search = debounce(async (q) => {
        if (!q || q.length < 2) { close(); return; }
        try {
            const r = await adminApi.users({ q, page: 1, page_size: 10 });
            lastResults = r.items || [];
            render(lastResults);
        } catch {
            close();
        }
    }, 200);

    input.addEventListener("input", () => search(input.value.trim()));
    input.addEventListener("keydown", (e) => {
        if (listEl.classList.contains("hidden")) return;
        const items = Array.from(listEl.children);
        if (e.key === "ArrowDown") {
            e.preventDefault();
            activeIdx = Math.min(items.length - 1, activeIdx + 1);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            activeIdx = Math.max(0, activeIdx - 1);
        } else if (e.key === "Enter" && activeIdx >= 0) {
            e.preventDefault();
            onPick(lastResults[activeIdx]);
            return;
        } else if (e.key === "Escape") {
            close();
            return;
        } else {
            return;
        }
        items.forEach((it, i) => it.classList.toggle("active", i === activeIdx));
    });
    input.addEventListener("blur", () => setTimeout(close, 120));
}
