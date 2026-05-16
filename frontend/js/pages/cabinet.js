/**
 * Личный кабинет. Вкладки: профиль, избранное, сохранённые фильтры, Telegram.
 */

import { renderHeader } from "../components/header.js";
import { renderFooter } from "../components/footer.js";
import { api, ApiError } from "../api.js";
import { getCurrentUser } from "../auth.js";
import { renderLotCard, renderLotSkeletons } from "../components/lot-card.js";
import { toast } from "../components/toast.js";
import { confirm } from "../components/modal.js";
import {
    qs,
    qsa,
    escapeHtml,
    formatDateTime,
    buildQuery,
} from "../utils.js";

function headerActiveForCabinet() {
    const tab = (location.hash || "#profile").replace("#", "");
    return tab === "favorites" ? "favorites" : "cabinet";
}

async function boot() {
    await renderHeader(headerActiveForCabinet());
    renderFooter();

    const user = await getCurrentUser();
    if (!user) {
        window.location.href =
            "/login.html?redirect=" +
            encodeURIComponent(location.pathname + location.search);
        return;
    }

    qs("#user-email").textContent = user.email;
    qs("#user-digest").textContent = user.digest_time || "09:00";

    const tabs = qsa(".cabinet-nav button");
    const sections = {
        profile: qs("#sec-profile"),
        favorites: qs("#sec-favorites"),
        filters: qs("#sec-filters"),
        telegram: qs("#sec-telegram"),
    };

    function activate(name) {
        tabs.forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
        for (const [k, el] of Object.entries(sections)) {
            el.classList.toggle("hidden", k !== name);
        }
        const mainNav = document.querySelector(".main-nav");
        if (mainNav) {
            const headerPage = name === "favorites" ? "favorites" : "cabinet";
            mainNav
                .querySelectorAll('a[data-page="favorites"], a[data-page="cabinet"]')
                .forEach((a) => {
                    a.classList.toggle("active", a.dataset.page === headerPage);
                });
        }
        if (name === "favorites") loadFavorites();
        if (name === "filters") loadFilters();
        if (name === "telegram") loadTelegram(user);
    }

    tabs.forEach((b) => b.addEventListener("click", () => activate(b.dataset.tab)));

    // Вкладка по умолчанию — из hash или profile
    const initial = (location.hash || "#profile").replace("#", "");
    activate(sections[initial] ? initial : "profile");
}

// ---------- Favorites ----------
async function loadFavorites() {
    const grid = qs("#favorites-grid");
    grid.replaceChildren(renderLotSkeletons(4));
    try {
        const resp = await api.get("/favorites");
        if (!resp.items || resp.items.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <h3>Избранное пустое</h3>
                    <p>Найдите интересные лоты и добавьте их сюда.</p>
                    <p style="margin-top:var(--space-4)">
                        <a class="btn btn-primary" href="/search.html">Перейти к поиску</a>
                    </p>
                </div>`;
            return;
        }
        grid.innerHTML = "";
        for (const lot of resp.items) {
            grid.appendChild(
                renderLotCard(lot, {
                    onFavorite: async (l, next) => {
                        if (next) await api.post(`/favorites/${l.id}`);
                        else await api.delete(`/favorites/${l.id}`);
                        loadFavorites();
                    },
                }),
            );
        }
    } catch (e) {
        grid.innerHTML = `<div class="error-banner">Ошибка: ${safeMsg(e)}</div>`;
        if (e instanceof ApiError) toast.fromApiError(e);
    }
}

// ---------- Filters ----------
async function loadFilters() {
    const list = qs("#filters-list");
    list.innerHTML = `<div class="loader-row"><span class="spinner"></span></div>`;
    try {
        const resp = await api.get("/filters");
        if (!resp.items || resp.items.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <h3>Нет сохранённых фильтров</h3>
                    <p>Настройте поиск и сохраните фильтр на странице поиска.</p>
                </div>`;
            return;
        }

        list.innerHTML = "";
        for (const f of resp.items) {
            list.appendChild(renderFilterItem(f));
        }
    } catch (e) {
        list.innerHTML = `<div class="error-banner">Ошибка: ${safeMsg(e)}</div>`;
        if (e instanceof ApiError) toast.fromApiError(e);
    }
}

function renderFilterItem(f) {
    const item = document.createElement("div");
    item.className = "filter-item";
    item.innerHTML = `
        <div class="filter-item-body">
            <div class="filter-item-name"></div>
            <div class="filter-item-desc"></div>
        </div>
        <label class="checkbox">
            <input type="checkbox" data-act="toggle-notify" ${f.notify_enabled ? "checked" : ""}>
            <span>Уведомлять</span>
        </label>
        <div class="filter-item-actions">
            <button type="button" class="btn btn-secondary btn-sm" data-act="apply">Применить</button>
            <button type="button" class="btn btn-danger btn-sm" data-act="delete">Удалить</button>
        </div>
    `;
    item.querySelector(".filter-item-name").textContent = f.name;
    item.querySelector(".filter-item-desc").textContent =
        describeFilter(f.filter) + " · создан " + formatDateTime(f.created_at);

    item.querySelector('[data-act="apply"]').addEventListener("click", () => {
        window.location.href = "/search.html" + buildQuery(f.filter || {});
    });

    item.querySelector('[data-act="delete"]').addEventListener("click", async () => {
        const ok = await confirm(
            "Удалить фильтр?",
            `«${f.name}» будет удалён без возможности восстановления.`,
            { okText: "Удалить", cancelText: "Отмена" },
        );
        if (!ok) return;
        try {
            await api.delete(`/filters/${f.id}`);
            toast.info("Фильтр удалён");
            loadFilters();
        } catch (e) {
            toast.fromApiError(e);
        }
    });

    item.querySelector('[data-act="toggle-notify"]').addEventListener(
        "change",
        async (e) => {
            try {
                await api.put(`/filters/${f.id}`, {
                    notify_enabled: e.target.checked,
                });
                toast.success(
                    e.target.checked
                        ? "Уведомления включены"
                        : "Уведомления выключены",
                );
            } catch (err) {
                e.target.checked = !e.target.checked;
                toast.fromApiError(err);
            }
        },
    );

    return item;
}

function describeFilter(f) {
    if (!f) return "Пустой фильтр";
    const parts = [];
    if (f.query) parts.push(`«${f.query}»`);
    if (f.category) parts.push(`категория: ${f.category}`);
    if (f.region) parts.push(`регион: ${f.region}`);
    if (f.price_from) parts.push(`от ${f.price_from} ₽`);
    if (f.price_to) parts.push(`до ${f.price_to} ₽`);
    return parts.length ? parts.join(", ") : "Без параметров";
}

// ---------- Telegram ----------
async function loadTelegram(user) {
    const root = qs("#telegram-block");
    root.innerHTML = `<div class="loader-row"><span class="spinner"></span></div>`;
    try {
        const linked = !!user.telegram_linked;
        root.innerHTML = `
            <div class="telegram-status">
                <div>
                    <div><span class="status-dot ${linked ? "ok" : "warn"}"></span>
                    ${linked ? "Telegram привязан" : "Telegram не привязан"}</div>
                    <div class="subtle text-sm" style="margin-top:var(--space-1)">
                        Получайте ежедневный дайджест новых лотов в мессенджер.
                    </div>
                </div>
                ${
                    linked
                        ? `<button class="btn btn-danger" data-act="unlink">Отвязать</button>`
                        : `<button class="btn btn-primary" data-act="link">Привязать Telegram</button>`
                }
            </div>
        `;
        const linkBtn = root.querySelector('[data-act="link"]');
        if (linkBtn) {
            linkBtn.addEventListener("click", async () => {
                linkBtn.disabled = true;
                try {
                    const resp = await api.post("/telegram/link");
                    // Открываем deep-link в новой вкладке; код ждёт, пока бот сам обновит статус
                    window.open(resp.deep_link, "_blank", "noopener");
                    toast.info("Откройте бота и нажмите «Start». Ссылка активна 10 минут.");
                } catch (e) {
                    toast.fromApiError(e);
                } finally {
                    linkBtn.disabled = false;
                }
            });
        }
        const unlinkBtn = root.querySelector('[data-act="unlink"]');
        if (unlinkBtn) {
            unlinkBtn.addEventListener("click", async () => {
                const ok = await confirm(
                    "Отвязать Telegram?",
                    "Вы перестанете получать уведомления в мессенджер.",
                    { okText: "Отвязать" },
                );
                if (!ok) return;
                try {
                    await api.post("/telegram/unlink");
                    toast.info("Telegram отвязан");
                    user.telegram_linked = false;
                    loadTelegram(user);
                } catch (e) {
                    toast.fromApiError(e);
                }
            });
        }
    } catch (e) {
        root.innerHTML = `<div class="error-banner">Ошибка: ${safeMsg(e)}</div>`;
    }
}

function safeMsg(e) {
    return (e && e.message ? e.message : "Ошибка").replace(/[<>&"']/g, "");
}

boot();
