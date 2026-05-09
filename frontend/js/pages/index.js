/**
 * Главная: поисковая строка + 10 последних лотов + быстрые категории.
 */

import { renderHeader } from "../components/header.js";
import { renderFooter } from "../components/footer.js";
import { api, ApiError } from "../api.js";
import { getCurrentUser } from "../auth.js";
import { renderLotCard, renderLotSkeletons } from "../components/lot-card.js";
import { toast } from "../components/toast.js";
import { qs, buildQuery } from "../utils.js";

async function boot() {
    await renderHeader("index");
    renderFooter();

    const form = qs("#hero-search");
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        const q = qs("#hero-input").value.trim();
        window.location.href = "/search.html" + buildQuery(q ? { query: q } : {});
    });

    qs("#quick-filters").addEventListener("click", (e) => {
        const btn = e.target.closest("[data-cat]");
        if (!btn) return;
        window.location.href =
            "/search.html" + buildQuery({ category: btn.dataset.cat });
    });

    const grid = qs("#recent-lots");
    grid.replaceChildren(renderLotSkeletons(6));

    try {
        const user = await getCurrentUser();
        const resp = await api.get(
            "/lots" + buildQuery({ sort: "date_desc", page_size: 10 }),
        );
        if (!resp.items || resp.items.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <h3>Лотов пока нет</h3>
                    <p>Загляните позже — мы обновляем каталог регулярно.</p>
                </div>`;
            return;
        }
        grid.innerHTML = "";
        for (const lot of resp.items) {
            grid.appendChild(
                renderLotCard(lot, {
                    onFavorite: user ? handleFavorite : null,
                }),
            );
        }
    } catch (e) {
        grid.innerHTML = `
            <div class="error-banner">Не удалось загрузить лоты: ${escapeError(e)}</div>`;
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

function escapeError(e) {
    return (e && e.message ? e.message : "Ошибка").replace(/[<>&"']/g, "");
}

boot();
