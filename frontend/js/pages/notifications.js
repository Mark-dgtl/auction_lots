/**
 * Настройки уведомлений: время дайджеста, включение/выключение уведомлений
 * по сохранённым фильтрам, тестовая отправка в Telegram.
 *
 * Тестовая отправка:
 *   - POST /api/notifications/test → 204 (успех)
 *   - 409 { code: "TELEGRAM_NOT_LINKED" } — показываем тост с предложением привязать
 *   - Кнопка заранее disabled, если Telegram не привязан (знаем из settings)
 */

import { renderHeader } from "../components/header.js";
import { renderFooter } from "../components/footer.js";
import { api, ApiError } from "../api.js";
import { getCurrentUser } from "../auth.js";
import { toast } from "../components/toast.js";
import { qs, formatDateTime } from "../utils.js";

const state = {
    telegramLinked: false,
};

async function boot() {
    await renderHeader("notifications");
    renderFooter();

    const user = await getCurrentUser();
    if (!user) {
        window.location.href =
            "/login.html?redirect=" + encodeURIComponent(location.pathname);
        return;
    }

    await loadSettings();
    await loadFilters();

    qs("#test-btn").addEventListener("click", sendTestNotification);
}

async function loadSettings() {
    const form = qs("#settings-form");
    try {
        const s = await api.get("/notifications/settings");
        form.digest_time.value = s.digest_time || "09:00";
        state.telegramLinked = !!s.telegram_linked;
        renderTgStatus();
    } catch (e) {
        toast.fromApiError(e);
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const time = form.digest_time.value;
        const btn = form.querySelector('button[type="submit"]');
        btn.disabled = true;
        try {
            await api.put("/notifications/settings", { digest_time: time });
            toast.success("Настройки сохранены");
        } catch (err) {
            toast.fromApiError(err);
        } finally {
            btn.disabled = false;
        }
    });
}

function renderTgStatus() {
    const tg = qs("#tg-status");
    const testBtn = qs("#test-btn");

    if (state.telegramLinked) {
        tg.innerHTML = `<span class="status-dot ok"></span>Telegram подключён`;
        testBtn.disabled = false;
        testBtn.title = "";
    } else {
        tg.innerHTML = `<span class="status-dot warn"></span>Telegram не подключён — <a href="/cabinet.html#telegram">подключить</a>`;
        testBtn.disabled = true;
        testBtn.title = "Сначала привяжите Telegram в личном кабинете";
    }
}

async function sendTestNotification() {
    const btn = qs("#test-btn");
    if (btn.disabled) return;
    btn.disabled = true;

    try {
        await api.post("/notifications/test");
        toast.success("Тестовое сообщение отправлено в Telegram", "Готово");
    } catch (e) {
        // Спецкейс: backend вернул 409 TELEGRAM_NOT_LINKED — покажем читаемый тост
        // и вернём состояние кнопки (но оставим disabled, т.к. предпосылка не выполнена).
        if (e instanceof ApiError && e.code === "TELEGRAM_NOT_LINKED") {
            toast.error(
                "Сначала привяжите Telegram в личном кабинете, затем повторите.",
                "Telegram не привязан",
            );
            state.telegramLinked = false;
            renderTgStatus();
            return;
        }
        if (e instanceof ApiError) {
            toast.fromApiError(e);
        } else {
            toast.error("Не удалось отправить тестовое сообщение");
        }
    } finally {
        // Включаем кнопку обратно только если tg всё ещё привязан
        if (state.telegramLinked) qs("#test-btn").disabled = false;
    }
}

async function loadFilters() {
    const list = qs("#notify-filters-list");
    list.innerHTML = `<div class="loader-row"><span class="spinner"></span></div>`;
    try {
        const resp = await api.get("/filters");
        if (!resp.items || resp.items.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <h3>Нет сохранённых фильтров</h3>
                    <p>Сохраните фильтр на <a href="/search.html">странице поиска</a>,
                    чтобы получать по нему уведомления.</p>
                </div>`;
            return;
        }
        list.innerHTML = "";
        for (const f of resp.items) list.appendChild(renderRow(f));
    } catch (e) {
        list.innerHTML = `<div class="error-banner">Ошибка: ${safeMsg(e)}</div>`;
        if (e instanceof ApiError) toast.fromApiError(e);
    }
}

function renderRow(f) {
    const el = document.createElement("div");
    el.className = "filter-item";
    el.innerHTML = `
        <div class="filter-item-body">
            <div class="filter-item-name"></div>
            <div class="filter-item-desc"></div>
        </div>
        <label class="checkbox">
            <input type="checkbox" data-act="toggle" ${f.notify_enabled ? "checked" : ""}>
            <span>Уведомлять</span>
        </label>
    `;
    el.querySelector(".filter-item-name").textContent = f.name;
    el.querySelector(".filter-item-desc").textContent =
        "Создан " + formatDateTime(f.created_at);

    el.querySelector('[data-act="toggle"]').addEventListener("change", async (e) => {
        try {
            await api.put(`/filters/${f.id}`, { notify_enabled: e.target.checked });
            toast.success(e.target.checked ? "Уведомления включены" : "Выключены");
        } catch (err) {
            e.target.checked = !e.target.checked;
            toast.fromApiError(err);
        }
    });
    return el;
}

function safeMsg(e) {
    return (e && e.message ? e.message : "Ошибка").replace(/[<>&"']/g, "");
}

boot();
