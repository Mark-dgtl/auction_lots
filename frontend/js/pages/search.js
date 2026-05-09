/**
 * Поисковая страница.
 * Query-string ↔ форма фильтров ↔ запрос к API.
 */

import { renderHeader } from "../components/header.js";
import { renderFooter } from "../components/footer.js";
import { api, ApiError } from "../api.js";
import { getCurrentUser } from "../auth.js";
import { mountFilters } from "../components/filters.js";
import { renderLotCard, renderLotSkeletons } from "../components/lot-card.js";
import { renderPagination } from "../components/pagination.js";
import { toast } from "../components/toast.js";
import { prompt } from "../components/modal.js";
import { qs, buildQuery, readQuery, writeQuery } from "../utils.js";

const PAGE_SIZE = 20;

let state = {
    filters: {},
    page: 1,
    sort: "date_desc",
    user: null,
};

async function boot() {
    await renderHeader("search");
    renderFooter();

    state.user = await getCurrentUser();

    const q = readQuery();
    state.filters = pickFilters(q);
    state.page = Math.max(1, parseInt(q.page || "1", 10));
    state.sort = q.sort || "date_desc";

    const sortSel = qs("#sort-select");
    sortSel.value = state.sort;
    sortSel.addEventListener("change", () => {
        state.sort = sortSel.value;
        state.page = 1;
        syncUrl();
        loadLots();
    });

    await mountFilters(
        qs("#filters-root"),
        state.filters,
        (values) => {
            state.filters = values;
            state.page = 1;
            syncUrl();
            loadLots();
        },
        { onSave: state.user ? handleSaveFilter : null },
    );

    syncUrl();
    loadLots();
}

function pickFilters(obj) {
    const out = {};
    for (const k of [
        "query",
        "category",
        "region",
        "price_from",
        "price_to",
        "date_from",
        "date_to",
    ]) {
        if (obj[k]) out[k] = obj[k];
    }
    return out;
}

function syncUrl() {
    writeQuery({
        ...state.filters,
        sort: state.sort !== "date_desc" ? state.sort : "",
        page: state.page > 1 ? String(state.page) : "",
    });
}

async function loadLots() {
    const grid = qs("#results");
    const pag = qs("#pagination");
    const counter = qs("#results-count");

    pag.innerHTML = "";
    counter.textContent = "";
    grid.replaceChildren(renderLotSkeletons(8));

    try {
        const resp = await api.get(
            "/lots" +
                buildQuery({
                    ...state.filters,
                    sort: state.sort,
                    page: String(state.page),
                    page_size: String(PAGE_SIZE),
                }),
        );
        counter.textContent =
            resp.total > 0 ? `Найдено: ${resp.total}` : "";

        if (!resp.items || resp.items.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <h3>Ничего не нашлось</h3>
                    <p>Попробуйте изменить параметры поиска или сбросить фильтры.</p>
                </div>`;
            return;
        }

        grid.innerHTML = "";
        for (const lot of resp.items) {
            grid.appendChild(
                renderLotCard(lot, {
                    onFavorite: state.user ? handleFavorite : null,
                }),
            );
        }
        renderPagination(
            pag,
            { total: resp.total, page: resp.page, pageSize: resp.page_size },
            (p) => {
                state.page = p;
                syncUrl();
                loadLots();
                window.scrollTo({ top: 0, behavior: "smooth" });
            },
        );
    } catch (e) {
        grid.innerHTML = `
            <div class="error-banner">Не удалось загрузить лоты: ${safeMsg(e)}</div>`;
        if (e instanceof ApiError) toast.fromApiError(e);
    }
}

async function handleFavorite(lot, next) {
    try {
        if (next) {
            await api.post(`/favorites/${lot.id}`);
            toast.success("Добавлено в избранное");
        } else {
            await api.delete(`/favorites/${lot.id}`);
            toast.info("Удалено из избранного");
        }
    } catch (e) {
        toast.fromApiError(e);
        throw e;
    }
}

async function handleSaveFilter(values) {
    const name = await prompt(
        "Сохранить фильтр",
        "Дайте фильтру имя — вы сможете применить его одним кликом из личного кабинета.",
        { placeholder: "Например: квартиры в Москве до 5 млн" },
    );
    if (!name) return;
    try {
        await api.post("/filters", {
            name,
            filter: values,
            notify_enabled: false,
        });
        toast.success("Фильтр сохранён", "Готово");
    } catch (e) {
        toast.fromApiError(e);
    }
}

function safeMsg(e) {
    return (e && e.message ? e.message : "Ошибка").replace(/[<>&"']/g, "");
}

boot();
