/**
 * Список пользователей. Поиск + пагинация + переход в карточку.
 */

import { adminApi } from "../api.js";
import { createTable } from "../components/table.js";
import { go } from "../router.js";
import { debounce, formatDateTime } from "../../utils.js";

let table = null;

export async function mount(root) {
    root.innerHTML = `
        <div class="admin-page-header">
            <div>
                <h1>Users</h1>
                <div class="subtitle">Управление аккаунтами, привязка Telegram, права.</div>
            </div>
        </div>
        <div id="users-table"></div>
    `;

    const toolbar = `
        <input type="search" class="input grow" id="u-q"
               placeholder="Поиск по email или имени…">
    `;

    table = createTable({
        root: root.querySelector("#users-table"),
        toolbarHtml: toolbar,
        pageSize: 20,
        emptyText: "Пользователи не найдены",
        rowKey: (u) => u.id,
        onRowClick: (u) => go(`/users/${u.id}`),
        loader: ({ page, pageSize, q }) =>
            adminApi.users({ page, page_size: pageSize, q }),
        columns: [
            { key: "id", title: "ID", num: true },
            {
                key: "email",
                title: "Email",
                render: (v, u) => {
                    const span = document.createElement("span");
                    span.textContent = v || "—";
                    if (u.is_admin) {
                        const b = document.createElement("span");
                        b.className = "badge";
                        b.style.marginLeft = "8px";
                        b.textContent = "admin";
                        span.appendChild(b);
                    }
                    if (u.is_blocked) {
                        const b = document.createElement("span");
                        b.className = "status-pill failed";
                        b.style.marginLeft = "8px";
                        b.textContent = "blocked";
                        span.appendChild(b);
                    }
                    return span;
                },
            },
            {
                key: "telegram_linked",
                title: "TG",
                render: (v) => {
                    const span = document.createElement("span");
                    if (v) {
                        span.className = "status-pill ok";
                        span.textContent = "привязан";
                    } else {
                        span.className = "muted";
                        span.textContent = "—";
                    }
                    return span;
                },
            },
            { key: "favorites_count", title: "Избр.", num: true },
            { key: "filters_count", title: "Фильтров", num: true },
            {
                key: "digest_time",
                title: "Дайджест",
                render: (v) => v || "—",
            },
            {
                key: "created_at",
                title: "Создан",
                render: (v) => v ? formatDateTime(v) : "—",
            },
            {
                key: "_actions",
                title: "",
                className: "actions",
                render: (_, u) => {
                    const wrap = document.createElement("span");
                    const btn = document.createElement("button");
                    btn.type = "button";
                    btn.className = "btn btn-secondary btn-sm";
                    btn.textContent = "Открыть";
                    btn.addEventListener("click", (e) => {
                        e.stopPropagation();
                        go(`/users/${u.id}`);
                    });
                    wrap.appendChild(btn);
                    return wrap;
                },
            },
        ],
    });

    table.reload();

    const qInput = root.querySelector("#u-q");
    qInput.addEventListener("input", debounce(() => {
        table.setParams({ q: qInput.value.trim() });
    }, 300));
}

export function unmount() {
    table = null;
}
