/**
 * Универсальная таблица для админки.
 *
 * Особенности:
 *  - Колонки задаются массивом `{ key, title, render?, sortable?, num?, className? }`.
 *  - Данные подгружаются переданным async-loader'ом, который получает
 *    `{ page, pageSize, sort, sortDir, ...extraParams }` и должен вернуть
 *    `{ items, total }`. Если total не передан — пагинация не показывается.
 *  - Состояния loading / empty / error отрисовываются автоматически.
 *  - Клик по строке (если задан `onRowClick`) — кликабельная строка.
 *  - Внешний код может подложить дополнительные параметры через `setParams()`
 *    (фильтры, поиск). Любой setParams сбрасывает страницу на 1 и перезагружает.
 *
 * Использование:
 *   const t = createTable({ root, columns, loader, pageSize: 20 });
 *   t.reload();
 *   t.setParams({ q: "foo" });
 */

import { renderPagination } from "../../components/pagination.js";

export function createTable({
    root,
    columns,
    loader,
    pageSize = 20,
    initialSort = null,
    initialSortDir = "desc",
    onRowClick = null,
    rowKey = (item, idx) => item.id ?? idx,
    emptyText = "Нет данных",
    toolbarHtml = "",
}) {
    let state = {
        page: 1,
        pageSize,
        sort: initialSort,
        sortDir: initialSortDir,
        params: {},
        loading: false,
        items: [],
        total: null,
        error: null,
    };

    root.classList.add("adm-table-wrap");
    root.innerHTML = `
        ${toolbarHtml ? `<div class="adm-table-toolbar">${toolbarHtml}</div>` : ""}
        <div class="adm-table-scroll">
            <table class="adm-table">
                <thead></thead>
                <tbody></tbody>
            </table>
        </div>
        <div class="adm-table-footer hidden">
            <span class="adm-table-total muted"></span>
            <div class="pagination"></div>
        </div>
    `;
    const theadEl = root.querySelector("thead");
    const tbodyEl = root.querySelector("tbody");
    const footerEl = root.querySelector(".adm-table-footer");
    const totalEl = root.querySelector(".adm-table-total");
    const pagEl = root.querySelector(".pagination");

    renderHeader();

    function renderHeader() {
        const tr = document.createElement("tr");
        for (const col of columns) {
            const th = document.createElement("th");
            if (col.num) th.classList.add("num");
            if (col.className) th.classList.add(col.className);
            if (col.sortable) {
                th.classList.add("sortable");
                th.addEventListener("click", () => toggleSort(col.key));
            }
            const arrow =
                state.sort === col.key
                    ? `<span class="sort-arrow">${state.sortDir === "asc" ? "▲" : "▼"}</span>`
                    : "";
            th.innerHTML = `${escapeHtml(col.title)}${arrow}`;
            tr.appendChild(th);
        }
        theadEl.innerHTML = "";
        theadEl.appendChild(tr);
    }

    function toggleSort(key) {
        if (state.sort === key) {
            state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
        } else {
            state.sort = key;
            state.sortDir = "asc";
        }
        renderHeader();
        reload();
    }

    function showLoading() {
        const colspan = columns.length;
        const rows = Array.from({ length: 5 }, () => `
            <tr class="skeleton-row">
                <td colspan="${colspan}"><div class="skeleton-bar"></div></td>
            </tr>
        `).join("");
        tbodyEl.innerHTML = rows;
        footerEl.classList.add("hidden");
    }

    function showEmpty() {
        tbodyEl.innerHTML = `
            <tr><td colspan="${columns.length}">
                <div class="adm-state">${escapeHtml(emptyText)}</div>
            </td></tr>
        `;
        footerEl.classList.add("hidden");
    }

    function showError(msg) {
        tbodyEl.innerHTML = `
            <tr><td colspan="${columns.length}">
                <div class="adm-state error">
                    ${escapeHtml(msg || "Ошибка загрузки")}
                    <div><button type="button" class="btn btn-secondary" data-act="retry">Повторить</button></div>
                </div>
            </td></tr>
        `;
        const btn = tbodyEl.querySelector('[data-act="retry"]');
        if (btn) btn.addEventListener("click", reload);
        footerEl.classList.add("hidden");
    }

    function showRows() {
        tbodyEl.innerHTML = "";
        for (let i = 0; i < state.items.length; i++) {
            const item = state.items[i];
            const tr = document.createElement("tr");
            tr.dataset.key = String(rowKey(item, i));
            if (onRowClick) {
                tr.classList.add("clickable");
                tr.addEventListener("click", (e) => {
                    // Не реагируем на клики внутри кнопок-действий ячеек.
                    if (e.target.closest("button, a, input, select, textarea")) return;
                    onRowClick(item, e);
                });
            }
            for (const col of columns) {
                const td = document.createElement("td");
                if (col.num) td.classList.add("num");
                if (col.className) td.classList.add(col.className);
                const value = col.render
                    ? col.render(item[col.key], item, td)
                    : item[col.key];
                if (value == null) {
                    td.innerHTML = '<span class="muted">—</span>';
                } else if (value instanceof HTMLElement) {
                    td.appendChild(value);
                } else if (typeof value === "string") {
                    // render может явно вернуть HTML — но мы по умолчанию
                    // считаем строку обычным текстом (XSS-безопасно).
                    td.textContent = value;
                } else {
                    td.textContent = String(value);
                }
                tr.appendChild(td);
            }
            tbodyEl.appendChild(tr);
        }
        if (state.total != null) {
            footerEl.classList.remove("hidden");
            totalEl.textContent = `Всего: ${state.total}`;
            renderPagination(
                pagEl,
                { total: state.total, page: state.page, pageSize: state.pageSize },
                (p) => { state.page = p; reload(); },
            );
        } else {
            footerEl.classList.add("hidden");
        }
    }

    async function reload() {
        if (state.loading) return;
        state.loading = true;
        showLoading();
        try {
            const result = await loader({
                page: state.page,
                pageSize: state.pageSize,
                sort: state.sort,
                sortDir: state.sortDir,
                ...state.params,
            });
            state.items = (result && result.items) || [];
            state.total = result && "total" in result ? result.total : null;
            state.error = null;
            if (state.items.length === 0) showEmpty();
            else showRows();
        } catch (err) {
            state.error = err;
            showError(err && err.message ? err.message : "Ошибка");
        } finally {
            state.loading = false;
        }
    }

    function setParams(p) {
        state.params = { ...state.params, ...p };
        state.page = 1;
        reload();
    }

    function setPage(p) {
        state.page = p;
        reload();
    }

    return {
        root,
        reload,
        setParams,
        setPage,
        getState: () => ({ ...state }),
        toolbar: root.querySelector(".adm-table-toolbar"),
    };
}

export function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
