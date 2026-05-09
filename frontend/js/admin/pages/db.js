/**
 * БД-консоль:
 *  - Tab «Таблицы»: список + grid с пагинацией.
 *  - Tab «Готовые отчёты»: каталог + run.
 *  - Tab «SQL-консоль»: textarea с подсветкой через CSS,
 *    переключатель readonly/danger, чекбокс confirm для danger.
 */

import { adminApi } from "../api.js";
import { confirm } from "../components/dialog.js";
import { toast } from "../../components/toast.js";
import { escapeHtml } from "../components/table.js";
import { renderPagination } from "../../components/pagination.js";

let activeTab = "tables";

const SQL_EXAMPLES = [
    "SELECT id, email, is_admin, created_at FROM users ORDER BY id DESC LIMIT 50;",
    "SELECT source, COUNT(*) FROM lots GROUP BY 1;",
    "SELECT status, COUNT(*) FROM outbox GROUP BY 1;",
    "UPDATE users SET is_blocked = TRUE WHERE id = 42;  -- danger режим",
];

export async function mount(root) {
    activeTab = "tables";
    root.innerHTML = `
        <div class="admin-page-header">
            <div>
                <h1>DB-консоль</h1>
                <div class="subtitle">Просмотр таблиц, готовые отчёты и произвольный SQL.</div>
            </div>
        </div>
        <div class="tabs" id="db-tabs">
            <button type="button" class="tab active" data-tab="tables">Таблицы</button>
            <button type="button" class="tab" data-tab="reports">Готовые отчёты</button>
            <button type="button" class="tab" data-tab="sql">SQL-консоль</button>
        </div>
        <div id="db-pane"></div>
    `;
    root.querySelector("#db-tabs").addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-tab]");
        if (!btn) return;
        activeTab = btn.dataset.tab;
        root.querySelectorAll("#db-tabs .tab")
            .forEach((t) => t.classList.toggle("active", t === btn));
        renderPane(root.querySelector("#db-pane"));
    });
    renderPane(root.querySelector("#db-pane"));
}

export function unmount() { /* no-op */ }

function renderPane(pane) {
    if (activeTab === "tables")  renderTables(pane);
    if (activeTab === "reports") renderReports(pane);
    if (activeTab === "sql")     renderSql(pane);
}

/* ---------------- Tables ---------------- */

async function renderTables(pane) {
    pane.innerHTML = `
        <div class="admin-grid-2">
            <section class="admin-card">
                <h3 class="card-title">Таблицы</h3>
                <div id="tables-list"><div class="adm-state">Загрузка…</div></div>
            </section>
            <section class="admin-card" id="table-view-card">
                <h3 class="card-title" id="table-view-title">Содержимое</h3>
                <div id="table-view"><div class="adm-state">Выберите таблицу слева</div></div>
            </section>
        </div>
    `;
    try {
        const r = await adminApi.dbTables();
        const list = pane.querySelector("#tables-list");
        const items = r.items || [];
        if (!items.length) {
            list.innerHTML = '<div class="adm-state">Таблиц нет</div>';
            return;
        }
        list.innerHTML = `
            <ul style="display:flex;flex-direction:column;gap:2px">
                ${items.map((t) => `
                    <li>
                        <button type="button" class="btn btn-ghost btn-sm"
                                style="width:100%;justify-content:space-between"
                                data-name="${escapeHtml(t.name)}">
                            <span>${escapeHtml(t.name)}</span>
                            <span class="muted">~${escapeHtml(String(t.rows_estimate ?? "?"))}</span>
                        </button>
                    </li>
                `).join("")}
            </ul>
        `;
        list.addEventListener("click", (e) => {
            const btn = e.target.closest("button[data-name]");
            if (!btn) return;
            list.querySelectorAll("button[data-name]")
                .forEach((b) => b.classList.toggle("active", b === btn));
            openTable(btn.dataset.name, pane);
        });
    } catch (err) {
        pane.querySelector("#tables-list").innerHTML =
            `<div class="adm-state error">${escapeHtml(err.message)}</div>`;
    }
}

async function openTable(name, pane, page = 1) {
    const titleEl = pane.querySelector("#table-view-title");
    const view = pane.querySelector("#table-view");
    titleEl.textContent = name;
    view.innerHTML = '<div class="adm-state">Загрузка…</div>';
    const limit = 50;
    const offset = (page - 1) * limit;
    try {
        const r = await adminApi.dbTableRows(name, { limit, offset });
        view.innerHTML = renderResultTable(r);
        if (r.total != null) {
            const pagDiv = document.createElement("div");
            pagDiv.className = "pagination";
            pagDiv.style.marginTop = "var(--space-3)";
            view.appendChild(pagDiv);
            renderPagination(
                pagDiv,
                { total: r.total, page, pageSize: limit },
                (p) => openTable(name, pane, p),
            );
        }
    } catch (err) {
        view.innerHTML = `<div class="adm-state error">${escapeHtml(err.message)}</div>`;
    }
}

/* ---------------- Reports ---------------- */

async function renderReports(pane) {
    pane.innerHTML = `
        <div class="admin-grid-2">
            <section class="admin-card">
                <h3 class="card-title">Каталог отчётов</h3>
                <div id="reports-list"><div class="adm-state">Загрузка…</div></div>
            </section>
            <section class="admin-card">
                <h3 class="card-title" id="report-title">Результат</h3>
                <div id="report-view"><div class="adm-state">Выберите отчёт слева</div></div>
            </section>
        </div>
    `;
    try {
        const r = await adminApi.dbReports();
        const items = r.items || [];
        const list = pane.querySelector("#reports-list");
        if (!items.length) {
            list.innerHTML = '<div class="adm-state">Отчётов нет</div>';
            return;
        }
        list.innerHTML = `
            <ul style="display:flex;flex-direction:column;gap:var(--space-2)">
                ${items.map((rep) => `
                    <li class="admin-card" style="padding: var(--space-3)">
                        <div style="display:flex;justify-content:space-between;align-items:center;gap:var(--space-2)">
                            <div>
                                <div style="font-weight:600">${escapeHtml(rep.title)}</div>
                                <div class="muted text-xs"><code class="code-inline">${escapeHtml(rep.id)}</code></div>
                            </div>
                            <button type="button" class="btn btn-secondary btn-sm" data-id="${escapeHtml(rep.id)}">Запустить</button>
                        </div>
                        ${rep.sql ? `<pre style="white-space:pre-wrap;color:var(--admin-text-muted);font-family:ui-monospace,Consolas,monospace;font-size:11px;margin-top:var(--space-2)">${escapeHtml(rep.sql)}</pre>` : ""}
                    </li>
                `).join("")}
            </ul>
        `;
        list.addEventListener("click", async (e) => {
            const btn = e.target.closest("button[data-id]");
            if (!btn) return;
            await runReport(btn.dataset.id, pane, btn);
        });
    } catch (err) {
        pane.querySelector("#reports-list").innerHTML =
            `<div class="adm-state error">${escapeHtml(err.message)}</div>`;
    }
}

async function runReport(id, pane, btn) {
    const view = pane.querySelector("#report-view");
    const title = pane.querySelector("#report-title");
    title.textContent = `Результат: ${id}`;
    view.innerHTML = '<div class="adm-state">Выполняется…</div>';
    btn.disabled = true;
    try {
        const r = await adminApi.dbReportRun(id);
        view.innerHTML = `
            <div class="sql-result-meta">
                <span>${r.row_count ?? (r.rows && r.rows.length) ?? 0} строк</span>
                <span>·</span>
                <span>${r.elapsed_ms ?? 0} мс</span>
                ${r.truncated ? '<span>· <span class="status-pill pending">truncated</span></span>' : ""}
            </div>
            ${renderResultTable(r)}
        `;
    } catch (err) {
        view.innerHTML = `<div class="adm-state error">${escapeHtml(err.message)}</div>`;
    } finally {
        btn.disabled = false;
    }
}

/* ---------------- SQL console ---------------- */

function renderSql(pane) {
    pane.innerHTML = `
        <div class="sql-hint">
            <strong>Режимы:</strong> <code>readonly</code> — только SELECT/WITH (макс 500 строк, statement_timeout 5s).
            <code>danger</code> — INSERT/UPDATE/DELETE с обязательным подтверждением. DDL запрещены навсегда.
            <details style="margin-top: var(--space-2)">
                <summary style="cursor:pointer">Примеры</summary>
                <ul style="margin-top: var(--space-2); padding-left: var(--space-4); display:flex;flex-direction:column;gap:4px">
                    ${SQL_EXAMPLES.map((q) => `<li><code class="code-inline" data-example>${escapeHtml(q)}</code></li>`).join("")}
                </ul>
            </details>
        </div>

        <textarea id="sql-input" class="sql-editor" spellcheck="false"
                  placeholder="-- введите SQL"></textarea>

        <div class="sql-toolbar">
            <div class="sql-mode" id="sql-mode" role="tablist">
                <button type="button" class="active" data-mode="readonly">readonly</button>
                <button type="button" class="danger" data-mode="danger">danger</button>
            </div>
            <label class="checkbox hidden" id="confirm-wrap">
                <input type="checkbox" id="sql-confirm">
                Я понимаю риски (изменение/удаление данных)
            </label>
            <span class="grow"></span>
            <button type="button" class="btn btn-primary" id="sql-run">Выполнить</button>
        </div>

        <div id="sql-result" style="margin-top: var(--space-4)"></div>
    `;

    const input = pane.querySelector("#sql-input");
    const modeWrap = pane.querySelector("#sql-mode");
    const confirmWrap = pane.querySelector("#confirm-wrap");
    const confirmCb = pane.querySelector("#sql-confirm");
    const runBtn = pane.querySelector("#sql-run");
    const resultEl = pane.querySelector("#sql-result");

    let mode = "readonly";

    modeWrap.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-mode]");
        if (!btn) return;
        mode = btn.dataset.mode;
        modeWrap.querySelectorAll("button")
            .forEach((b) => b.classList.toggle("active", b === btn));
        confirmWrap.classList.toggle("hidden", mode !== "danger");
        input.classList.toggle("danger", mode === "danger");
    });

    pane.querySelectorAll("[data-example]").forEach((el) => {
        el.addEventListener("click", () => { input.value = el.textContent; input.focus(); });
    });

    runBtn.addEventListener("click", async () => {
        const sql = input.value.trim();
        if (!sql) { toast.error("SQL пуст"); return; }
        if (mode === "danger" && !confirmCb.checked) {
            toast.error("Подтвердите чекбокс «Я понимаю риски»");
            return;
        }
        if (mode === "danger") {
            const ok = await confirm(
                "Выполнить опасный запрос?",
                "Запрос может изменить или удалить данные. Действие будет залогировано в admin_audit_log.",
                { okText: "Выполнить" },
            );
            if (!ok) return;
        }

        runBtn.disabled = true;
        resultEl.innerHTML = '<div class="adm-state">Выполняется…</div>';
        try {
            const body = { sql, mode };
            if (mode === "danger") body.confirm = true;
            const r = await adminApi.dbQuery(body);
            resultEl.innerHTML = `
                <div class="sql-result-meta">
                    <span>${r.row_count ?? (r.rows && r.rows.length) ?? 0} строк</span>
                    <span>·</span>
                    <span>${r.elapsed_ms ?? 0} мс</span>
                    ${r.truncated ? '<span>· <span class="status-pill pending">truncated до 500</span></span>' : ""}
                </div>
                ${renderResultTable(r)}
            `;
        } catch (err) {
            resultEl.innerHTML = `<div class="adm-state error">${escapeHtml(err.message)}</div>`;
        } finally {
            runBtn.disabled = false;
        }
    });
}

/* ---------------- Result renderer ---------------- */

function renderResultTable(r) {
    const cols = r.columns || [];
    const rows = r.rows || [];
    if (!cols.length) {
        return '<div class="adm-state">Нет колонок в ответе</div>';
    }
    if (!rows.length) {
        return '<div class="adm-state">Запрос не вернул строк</div>';
    }
    return `
        <div class="adm-table-scroll" style="max-height: 60vh; overflow-y: auto">
            <table class="adm-table">
                <thead>
                    <tr>${cols.map((c) => `<th>${escapeHtml(c)}</th>`).join("")}</tr>
                </thead>
                <tbody>
                    ${rows.map((row) => `
                        <tr>
                            ${row.map((cell) => `<td>${formatCell(cell)}</td>`).join("")}
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;
}

function formatCell(v) {
    if (v == null) return '<span class="muted">NULL</span>';
    if (typeof v === "object") {
        return `<code class="code-inline">${escapeHtml(JSON.stringify(v))}</code>`;
    }
    return escapeHtml(String(v));
}
