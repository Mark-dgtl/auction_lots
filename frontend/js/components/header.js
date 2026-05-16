/**
 * Рендерит верхний header. Вызывается каждой страницей в начале bootstrap.
 * Подхватывает текущего пользователя и показывает нужную навигацию.
 */

import { getCurrentUser, logout } from "../auth.js";

export async function renderHeader(activePage) {
    const existing = document.querySelector(".site-header");
    if (existing) existing.remove();

    const user = await getCurrentUser();

    const header = document.createElement("header");
    header.className = "site-header";
    header.innerHTML = `
        <div class="container">
            <a href="/index.html" class="logo" aria-label="На главную">
                <span class="logo-dot" aria-hidden="true"></span>
                <span>Агрегатор торгов</span>
            </a>

            <button type="button" class="nav-toggle" aria-label="Меню"
                    aria-expanded="false" aria-controls="main-nav">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round">
                    <line x1="3" y1="6"  x2="21" y2="6"/>
                    <line x1="3" y1="12" x2="21" y2="12"/>
                    <line x1="3" y1="18" x2="21" y2="18"/>
                </svg>
            </button>

            <nav class="main-nav" id="main-nav" aria-label="Основная навигация">
                <a href="/index.html" data-page="index">Главная</a>
                <a href="/search.html" data-page="search">Поиск</a>
                ${
                    user
                        ? `
                    <a href="/cabinet.html#favorites" data-page="favorites">Избранное</a>
                    <a href="/notifications.html" data-page="notifications">Уведомления</a>
                    <a href="/cabinet.html#profile" data-page="cabinet" title="${escapeAttr(user.email)}">Кабинет</a>
                    <button type="button" class="btn btn-ghost btn-sm" data-act="logout">Выйти</button>
                `
                        : `
                    <a href="/login.html" data-page="login" class="btn btn-primary btn-sm">Войти</a>
                `
                }
            </nav>
        </div>
    `;

    document.body.prepend(header);

    if (activePage) {
        header.querySelectorAll("a[data-page]").forEach((a) => {
            a.classList.toggle("active", a.dataset.page === activePage);
        });
    }

    const toggle = header.querySelector(".nav-toggle");
    const nav = header.querySelector(".main-nav");
    toggle.addEventListener("click", () => {
        const open = nav.classList.toggle("open");
        toggle.setAttribute("aria-expanded", String(open));
    });

    const logoutBtn = header.querySelector('[data-act="logout"]');
    if (logoutBtn) {
        logoutBtn.addEventListener("click", async () => {
            logoutBtn.disabled = true;
            await logout();
            window.location.href = "/index.html";
        });
    }
}

function escapeAttr(s) {
    return String(s || "").replace(/"/g, "&quot;");
}
