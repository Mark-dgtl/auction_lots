/**
 * Outbox: шаблон регулярного дайджеста; вкладки по статусу (pending/sent/failed),
 * retry/delete на строках, расширяемая ячейка text по клику.
 */

import { adminApi } from "../api.js";
import { createTable, escapeHtml } from "../components/table.js";
import { confirm } from "../components/dialog.js";
import { toast } from "../../components/toast.js";
import { formatDateTime } from "../../utils.js";

let table = null;
let currentStatus = "pending";
let digestTemplateValue = "";
const DIGEST_PREVIEW_DATA = {
    filter_name: "Коммерческая недвижимость, Москва",
    lots_count: 2,
    lots: [
        "1. Помещение 124 м2, ЦАО",
        "   12 500 000.00 ₽",
        "   http://localhost:8080/lot.html?id=101",
        "",
        "2. Склад 980 м2, МО",
        "   34 900 000.00 ₽",
        "   http://localhost:8080/lot.html?id=102",
    ].join("\n"),
};

export async function mount(root) {
    root.innerHTML = `
        <div class="admin-page-header">
            <div>
                <h1>Outbox</h1>
                <div class="subtitle">Очередь сообщений в Telegram. Бот забирает pending и подтверждает доставку.</div>
            </div>
        </div>

        <section class="admin-card">
            <h3 class="card-title">Регулярный дайджест по лотам</h3>
            <div class="subtitle" style="margin-top:6px">
                Доступные плейсхолдеры: <span class="code-inline">{filter_name}</span>,
                <span class="code-inline">{lots_count}</span>, <span class="code-inline">{lots}</span>
            </div>
            <div style="height: var(--space-3)"></div>
            <label for="digest-template" style="display:block;margin-bottom:6px;color:var(--admin-text-muted)">
                Шаблон сообщения
            </label>
            <textarea
                id="digest-template"
                class="textarea"
                rows="10"
                placeholder="Загрузка шаблона..."
                spellcheck="false"
            ></textarea>
            <div style="height: var(--space-3)"></div>
            <label for="digest-template-preview" style="display:block;margin-bottom:6px;color:var(--admin-text-muted)">
                Предпросмотр (тестовые данные)
            </label>
            <div id="digest-template-preview" class="preview-pane" aria-live="polite"></div>
            <div style="height: var(--space-3)"></div>
            <div class="admin-page-actions">
                <button type="button" class="btn btn-primary" id="digest-template-save">Сохранить шаблон</button>
                <button type="button" class="btn btn-secondary" id="digest-run-now">Отправить досрочно сейчас</button>
            </div>
        </section>
        <div style="height: var(--space-5)"></div>

        <div class="tabs" id="status-tabs">
            <button type="button" class="tab active" data-status="pending">Pending</button>
            <button type="button" class="tab" data-status="sent">Sent</button>
            <button type="button" class="tab" data-status="failed">Failed</button>
        </div>

        <div id="outbox-table"></div>
    `;

    currentStatus = "pending";

    table = createTable({
        root: root.querySelector("#outbox-table"),
        pageSize: 50,
        emptyText: "Сообщений нет",
        rowKey: (o) => o.id,
        loader: ({ page, pageSize }) =>
            adminApi.outbox({
                status: currentStatus,
                limit: pageSize,
                offset: (page - 1) * pageSize,
            }),
        columns: [
            { key: "id", title: "ID", num: true },
            {
                key: "user_email",
                title: "Получатель",
                render: (v, o) => v || `user #${o.user_id}`,
            },
            { key: "chat_id", title: "Chat ID", num: true },
            {
                key: "text",
                title: "Текст",
                render: (v) => {
                    const div = document.createElement("div");
                    div.className = "expandable";
                    div.title = "Кликните, чтобы развернуть";
                    div.textContent = v || "";
                    div.addEventListener("click", () => div.classList.toggle("expanded"));
                    return div;
                },
            },
            {
                key: "status",
                title: "Статус",
                render: (v) => {
                    const s = document.createElement("span");
                    s.className = `status-pill ${v}`;
                    s.textContent = v || "—";
                    return s;
                },
            },
            { key: "attempt_count", title: "Попыток", num: true },
            {
                key: "created_at",
                title: "Создан",
                render: (v) => v ? formatDateTime(v) : "—",
            },
            {
                key: "_actions",
                title: "",
                className: "actions",
                render: (_, o) => {
                    const wrap = document.createElement("span");

                    if (o.status === "failed" || o.status === "pending") {
                        const retry = document.createElement("button");
                        retry.type = "button";
                        retry.className = "btn btn-secondary btn-sm";
                        retry.textContent = "Retry";
                        retry.addEventListener("click", () => onRetry(o.id));
                        wrap.appendChild(retry);
                    }

                    const del = document.createElement("button");
                    del.type = "button";
                    del.className = "btn btn-danger btn-sm";
                    del.style.marginLeft = "4px";
                    del.textContent = "Удалить";
                    del.addEventListener("click", () => onDelete(o.id));
                    wrap.appendChild(del);
                    return wrap;
                },
            },
        ],
    });
    table.reload();

    root.querySelector("#digest-template-save").addEventListener("click", onSaveTemplate);
    root.querySelector("#digest-run-now").addEventListener("click", onRunNow);
    root.querySelector("#digest-template").addEventListener("input", onTemplateInput);
    await loadDigestTemplate();

    root.querySelector("#status-tabs").addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-status]");
        if (!btn) return;
        currentStatus = btn.dataset.status;
        root.querySelectorAll("#status-tabs .tab")
            .forEach((t) => t.classList.toggle("active", t === btn));
        table.setPage(1);
    });
}

export function unmount() {
    table = null;
}

async function onRetry(id) {
    try {
        await adminApi.outboxRetry(id);
        toast.success(`Сообщение #${id} поставлено на повтор`);
        table.reload();
    } catch (err) {
        toast.fromApiError(err);
    }
}

async function onDelete(id) {
    const ok = await confirm("Удалить сообщение?", `Outbox #${id} будет удалён.`, {
        okText: "Удалить",
    });
    if (!ok) return;
    try {
        await adminApi.outboxDelete(id);
        toast.success("Удалено");
        table.reload();
    } catch (err) {
        toast.fromApiError(err);
    }
}

async function loadDigestTemplate() {
    const textarea = document.getElementById("digest-template");
    if (!textarea) return;
    try {
        const data = await adminApi.digestTemplate();
        digestTemplateValue = data.template || "";
        textarea.value = digestTemplateValue;
        renderDigestPreview(digestTemplateValue);
    } catch (err) {
        textarea.value = "";
        textarea.placeholder = "Не удалось загрузить шаблон";
        renderDigestPreview("");
        toast.fromApiError(err);
    }
}

async function onSaveTemplate() {
    const textarea = document.getElementById("digest-template");
    const button = document.getElementById("digest-template-save");
    if (!textarea || !button) return;

    const nextTemplate = textarea.value.trim();
    button.disabled = true;
    try {
        const data = await adminApi.digestTemplateUpdate({ template: nextTemplate });
        digestTemplateValue = data.template || nextTemplate;
        textarea.value = digestTemplateValue;
        renderDigestPreview(digestTemplateValue);
        toast.success("Шаблон дайджеста сохранён");
    } catch (err) {
        toast.fromApiError(err);
    } finally {
        button.disabled = false;
    }
}

function onTemplateInput(e) {
    const template = e?.target?.value ?? "";
    renderDigestPreview(template);
}

function renderDigestPreview(template) {
    const node = document.getElementById("digest-template-preview");
    if (!node) return;

    const normalized = (template || "").trim();
    const tpl = normalized || "Новые лоты по фильтру «{filter_name}» ({lots_count}):\n\n{lots}";
    try {
        const rendered = applyDigestTemplate(tpl, DIGEST_PREVIEW_DATA);
        node.textContent = rendered;
    } catch (err) {
        node.textContent = `Ошибка шаблона: ${err && err.message ? err.message : "неизвестная ошибка"}`;
    }
}

function applyDigestTemplate(template, values) {
    return template.replace(/\{([a-z_]+)\}/gi, (match, key) => {
        if (!(key in values)) {
            throw new Error(`неизвестный плейсхолдер ${match}`);
        }
        return String(values[key]);
    }).trimEnd();
}

async function onRunNow() {
    const button = document.getElementById("digest-run-now");
    if (!button) return;
    button.disabled = true;
    try {
        const data = await adminApi.digestRunNow();
        toast.success(`Дайджест запущен: создано сообщений ${data.created ?? 0}`);
        if (table) table.reload();
    } catch (err) {
        toast.fromApiError(err);
    } finally {
        button.disabled = false;
    }
}
