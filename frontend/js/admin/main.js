/**
 * Точка входа админки.
 *
 * 1) Проверяем авторизацию через `/api/me`. Если токена нет, либо
 *    `is_admin` — false, отправляем на /login.html с redirect-параметром.
 * 2) Иначе — рисуем email админа в шапке, навешиваем «Выйти» и
 *    запускаем хеш-роутер.
 *
 * Никаких моков: админка работает только с реальным API
 * (см. требования milestone M4).
 */

import { getCurrentUser, logout } from "../auth.js";
import { startRouter } from "./router.js";

async function bootstrap() {
    // #region agent log
    fetch("http://127.0.0.1:7460/ingest/7bcbbbf8-5316-4074-8658-ad3265ad53e3", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-Debug-Session-Id": "3e7f94",
        },
        body: JSON.stringify({
            sessionId: "3e7f94",
            location: "admin/main.js:bootstrap",
            message: "admin bootstrap start",
            data: { href: location.href, pathname: location.pathname },
            timestamp: Date.now(),
            hypothesisId: "H5",
        }),
    }).catch(() => {});
    // #endregion

    wireSidebar();

    const user = await getCurrentUser();
    // #region agent log
    fetch("http://127.0.0.1:7460/ingest/7bcbbbf8-5316-4074-8658-ad3265ad53e3", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-Debug-Session-Id": "3e7f94",
        },
        body: JSON.stringify({
            sessionId: "3e7f94",
            location: "admin/main.js:after-getCurrentUser",
            message: "admin gate",
            data: {
                hasUser: !!user,
                is_admin: user ? !!user.is_admin : null,
            },
            timestamp: Date.now(),
            hypothesisId: "H1-H3",
        }),
    }).catch(() => {});
    // #endregion
    if (!user) {
        // #region agent log
        fetch("http://127.0.0.1:7460/ingest/7bcbbbf8-5316-4074-8658-ad3265ad53e3", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Debug-Session-Id": "3e7f94",
            },
            body: JSON.stringify({
                sessionId: "3e7f94",
                location: "admin/main.js:redirect",
                message: "toLogin no user",
                data: {},
                timestamp: Date.now(),
                hypothesisId: "H1-H2-H4",
            }),
        }).catch(() => {});
        // #endregion
        toLogin();
        return;
    }
    if (!user.is_admin) {
        // #region agent log
        fetch("http://127.0.0.1:7460/ingest/7bcbbbf8-5316-4074-8658-ad3265ad53e3", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Debug-Session-Id": "3e7f94",
            },
            body: JSON.stringify({
                sessionId: "3e7f94",
                location: "admin/main.js:redirect",
                message: "toIndex not admin",
                data: {},
                timestamp: Date.now(),
                hypothesisId: "H3",
            }),
        }).catch(() => {});
        // #endregion
        // Авторизован, но не админ — без права входа.
        // Лучше выкинуть на главную, чем зацикливать редиректы на /login.
        window.location.replace("/index.html");
        return;
    }

    const emailEl = document.getElementById("admin-email");
    if (emailEl) {
        emailEl.textContent = user.email || "";
        emailEl.title = user.email || "";
    }

    const logoutBtn = document.getElementById("admin-logout");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", async () => {
            logoutBtn.disabled = true;
            await logout();
            window.location.href = "/login.html";
        });
    }

    // #region agent log
    fetch("http://127.0.0.1:7460/ingest/7bcbbbf8-5316-4074-8658-ad3265ad53e3", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-Debug-Session-Id": "3e7f94",
        },
        body: JSON.stringify({
            sessionId: "3e7f94",
            location: "admin/main.js:ok",
            message: "admin router start",
            data: {},
            timestamp: Date.now(),
            hypothesisId: "OK",
        }),
    }).catch(() => {});
    // #endregion
    startRouter(document.getElementById("admin-view"));
}

function toLogin() {
    const r = encodeURIComponent("/admin.html");
    window.location.replace("/login.html?redirect=" + r);
}

function wireSidebar() {
    const sidebar = document.getElementById("admin-sidebar");
    const burger = document.getElementById("admin-burger");
    const backdrop = document.getElementById("admin-sidebar-backdrop");
    if (!sidebar || !burger) return;

    const close = () => {
        sidebar.classList.remove("open");
        if (backdrop) backdrop.classList.remove("open");
    };
    const open = () => {
        sidebar.classList.add("open");
        if (backdrop) backdrop.classList.add("open");
    };

    burger.addEventListener("click", () => {
        sidebar.classList.contains("open") ? close() : open();
    });
    if (backdrop) backdrop.addEventListener("click", close);

    sidebar.addEventListener("click", (e) => {
        if (e.target.closest("a")) close();
    });
}

bootstrap();
