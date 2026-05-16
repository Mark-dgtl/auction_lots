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

const SHUFFLE_SEED_KEY = "search_shuffle_seed";

let state = {
    filters: {},
    page: 1,
    sort: "random",
    shuffleSeed: null,
    user: null,
};

async function boot() {
    await renderHeader("search");
    renderFooter();

    state.user = await getCurrentUser();

    const q = readQuery();
    state.filters = pickFilters(q);
    state.page = Math.max(1, parseInt(q.page || "1", 10));
    const filtersEmpty = !hasActiveFilters(state.filters);
    if (q.sort) {
        state.sort = q.sort;
    } else {
        state.sort = filtersEmpty ? "random" : "date_desc";
    }
    if (state.sort === "random") {
        state.shuffleSeed = q.shuffle_seed || ensureShuffleSeed();
    }

    const sortSel = qs("#sort-select");
    sortSel.value = state.sort;
    sortSel.addEventListener("change", () => {
        state.sort = sortSel.value;
        if (state.sort === "random") {
            state.shuffleSeed = ensureShuffleSeed(true);
        } else {
            state.shuffleSeed = null;
        }
        state.page = 1;
        syncUrl();
        loadLots();
    });

    await mountFilters(
        qs("#filters-root"),
        state.filters,
        (values) => {
            const wasEmpty = !hasActiveFilters(state.filters);
            const nowEmpty = !hasActiveFilters(values);
            state.filters = values;
            state.page = 1;
            if (nowEmpty && !wasEmpty && state.sort === "date_desc") {
                state.sort = "random";
                state.shuffleSeed = ensureShuffleSeed(true);
            }
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

function hasActiveFilters(filters) {
    return Object.keys(filters).length > 0;
}

function ensureShuffleSeed(forceNew = false) {
    if (!forceNew) {
        try {
            const saved = sessionStorage.getItem(SHUFFLE_SEED_KEY);
            if (saved) return saved;
        } catch {
            /* ignore */
        }
    }
    const seed =
        typeof crypto !== "undefined" && crypto.randomUUID
            ? crypto.randomUUID().slice(0, 12)
            : String(Date.now());
    try {
        sessionStorage.setItem(SHUFFLE_SEED_KEY, seed);
    } catch {
        /* ignore */
    }
    return seed;
}

function syncUrl() {
    const params = {
        ...state.filters,
        page: state.page > 1 ? String(state.page) : "",
    };
    if (state.sort === "random") {
        params.sort = "random";
        if (state.shuffleSeed) params.shuffle_seed = state.shuffleSeed;
    } else if (state.sort !== "date_desc") {
        params.sort = state.sort;
    }
    writeQuery(params);
}

async function loadLots() {
    const grid = qs("#results");
    const pag = qs("#pagination");
    const counter = qs("#results-count");

    pag.innerHTML = "";
    counter.textContent = "";
    grid.replaceChildren(renderLotSkeletons(8));

    try {
        const query = {
            ...state.filters,
            sort: state.sort,
            page: String(state.page),
            page_size: String(PAGE_SIZE),
        };
        if (state.sort === "random" && state.shuffleSeed) {
            query.shuffle_seed = state.shuffleSeed;
        }
        const resp = await api.get("/lots" + buildQuery(query));
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
        resp.items.forEach((lot, i) => {
            grid.appendChild(
                renderLotCard(lot, {
                    onFavorite: state.user ? handleFavorite : null,
                    imagePriority: i < 6 ? "high" : undefined,
                }),
            );
        });
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
