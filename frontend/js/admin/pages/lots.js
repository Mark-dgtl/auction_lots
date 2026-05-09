/**
 * Лоты — таблица с фильтрами по источнику/статусу/q,
 * удаление и re-parse каждого лота.
 */

import { adminApi } from "../api.js";
import { createTable } from "../components/table.js";
import { confirm } from "../components/dialog.js";
import { toast } from "../../components/toast.js";
import { debounce, formatDateTime, formatPrice } from "../../utils.js";

let table = null;

export async function mount(root) {
    root.innerHTML = `
        <div class="admin-page-header">
            <div>
                <h1>Lots</h1>
                <div class="subtitle">Все лоты в БД, ручное удаление и обновление с источника.</div>
            </div>
        </div>
        <div id="lots-table"></div>
    `;

    const toolbar = `
        <select class="select" id="f-source" style="max-width: 180px">
            <option value="">Все источники</option>
            <option value="torgi_gov">torgi_gov</option>
            <option value="efrsb">efrsb</option>
        </select>
        <input class="input" id="f-status" placeholder="Статус" style="max-width: 160px">
        <input type="search" class="input grow" id="f-q" placeholder="Поиск по заголовку…">
    `;

    table = createTable({
        root: root.querySelector("#lots-table"),
        toolbarHtml: toolbar,
        pageSize: 20,
        emptyText: "Лоты не найдены",
        rowKey: (l) => l.id,
        loader: ({ page, pageSize, source, status, q }) =>
            adminApi.lots({ page, page_size: pageSize, source, status, q }),
        columns: [
            { key: "id", title: "ID", num: true },
            { key: "source", title: "Источник",
              render: (v) => {
                  const s = document.createElement("span");
                  s.className = "code-inline";
                  s.textContent = v || "—";
                  return s;
              },
            },
            {
                key: "title",
                title: "Заголовок",
                render: (v, l) => {
                    const a = document.createElement("a");
                    a.href = `/lot.html?id=${l.id}`;
                    a.target = "_blank";
                    a.rel = "noopener";
                    a.textContent = v || "—";
                    return a;
                },
            },
            { key: "category", title: "Категория", render: (v) => v || "—" },
            { key: "region_name", title: "Регион", render: (v) => v || "—" },
            {
                key: "price",
                title: "Цена",
                num: true,
                render: (v) => v == null ? "—" : formatPrice(v),
            },
            {
                key: "auction_date",
                title: "Аукцион",
                render: (v) => v ? formatDateTime(v) : "—",
            },
            {
                key: "_actions",
                title: "",
                className: "actions",
                render: (_, l) => {
                    const wrap = document.createElement("span");
                    const refresh = document.createElement("button");
                    refresh.type = "button";
                    refresh.className = "btn btn-secondary btn-sm";
                    refresh.textContent = "Re-parse";
                    refresh.addEventListener("click", () => onRefresh(l.id, refresh));

                    const del = document.createElement("button");
                    del.type = "button";
                    del.className = "btn btn-danger btn-sm";
                    del.textContent = "Удалить";
                    del.style.marginLeft = "4px";
                    del.addEventListener("click", () => onDelete(l));

                    wrap.appendChild(refresh);
                    wrap.appendChild(del);
                    return wrap;
                },
            },
        ],
    });
    table.reload();

    const sourceSel = root.querySelector("#f-source");
    const statusInput = root.querySelector("#f-status");
    const qInput = root.querySelector("#f-q");

    sourceSel.addEventListener("change", () =>
        table.setParams({ source: sourceSel.value }));
    statusInput.addEventListener("input", debounce(() =>
        table.setParams({ status: statusInput.value.trim() }), 300));
    qInput.addEventListener("input", debounce(() =>
        table.setParams({ q: qInput.value.trim() }), 300));
}

export function unmount() {
    table = null;
}

async function onRefresh(id, btn) {
    btn.disabled = true;
    const oldText = btn.textContent;
    btn.textContent = "…";
    try {
        await adminApi.lotRefresh(id);
        toast.success(`Лот #${id} обновлён`);
        table.reload();
    } catch (err) {
        toast.fromApiError(err);
    } finally {
        btn.disabled = false;
        btn.textContent = oldText;
    }
}

async function onDelete(l) {
    const ok = await confirm(
        "Удалить лот?",
        `«${l.title}» (#${l.id}) будет удалён из БД. Действие необратимо.`,
        { okText: "Удалить" },
    );
    if (!ok) return;
    try {
        await adminApi.lotDelete(l.id);
        toast.success("Лот удалён");
        table.reload();
    } catch (err) {
        toast.fromApiError(err);
    }
}
