/**
 * Простой хеш-роутер для админки.
 *
 * URL: `#/route` или `#/route/:param`. Поддерживает один уровень
 * параметров (нам этого хватает: `#/users/:id`). Каждая страница
 * экспортирует `mount(root, params)` (async), а на смену маршрута
 * — `unmount()` (опционально), чтобы прибраться (закрыть EventSource,
 * остановить интервал и т.п.).
 */

const ROUTES = {
    dashboard:   () => import("./pages/dashboard.js"),
    logs:        () => import("./pages/logs.js"),
    users:       () => import("./pages/users.js"),
    user_detail: () => import("./pages/user_detail.js"),
    lots:        () => import("./pages/lots.js"),
    outbox:      () => import("./pages/outbox.js"),
    parser:      () => import("./pages/parser.js"),
    bot:         () => import("./pages/bot.js"),
    db:          () => import("./pages/db.js"),
};

let currentPage = null;
let rootEl = null;

/**
 * Парсит хеш в `{name, params}`. Дефолт — dashboard.
 */
function parse(hash) {
    const raw = (hash || "").replace(/^#\/?/, "").replace(/^\//, "");
    if (!raw) return { name: "dashboard", params: {} };
    const parts = raw.split("/").filter(Boolean);
    const head = parts[0];
    if (head === "users" && parts[1]) {
        return { name: "user_detail", params: { id: parts[1] } };
    }
    if (ROUTES[head]) {
        return { name: head, params: {} };
    }
    return { name: "dashboard", params: {} };
}

function highlightSidebar(name) {
    const map = {
        dashboard: "dashboard",
        logs: "logs",
        users: "users",
        user_detail: "users",
        lots: "lots",
        outbox: "outbox",
        parser: "parser",
        bot: "bot",
        db: "db",
    };
    const active = map[name];
    document.querySelectorAll(".admin-sidebar a[data-route]").forEach((a) => {
        a.classList.toggle("active", a.dataset.route === active);
    });
}

async function navigate() {
    const { name, params } = parse(window.location.hash);
    highlightSidebar(name);

    if (currentPage && typeof currentPage.unmount === "function") {
        try { currentPage.unmount(); } catch (e) { console.error(e); }
    }
    currentPage = null;

    rootEl.innerHTML = '<div class="adm-state">Загрузка…</div>';

    try {
        const mod = await ROUTES[name]();
        currentPage = mod;
        await mod.mount(rootEl, params);
        rootEl.scrollTop = 0;
        window.scrollTo(0, 0);
    } catch (err) {
        console.error("[admin/router] mount failed", err);
        rootEl.innerHTML = `
            <div class="adm-state error">
                Не удалось загрузить страницу: ${escapeHtml(err.message || String(err))}
                <div><button type="button" class="btn btn-secondary" id="reload-route">Повторить</button></div>
            </div>
        `;
        const btn = rootEl.querySelector("#reload-route");
        if (btn) btn.addEventListener("click", navigate);
    }
}

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

/**
 * Запустить роутер. Вызывается один раз из main.js.
 */
export function startRouter(root) {
    rootEl = root;
    if (!window.location.hash) {
        window.location.hash = "#/dashboard";
    }
    window.addEventListener("hashchange", navigate);
    navigate();
}

/**
 * Программный переход. Не вызывает navigate напрямую —
 * полагается на штатное событие `hashchange`.
 */
export function go(path) {
    if (!path.startsWith("#")) path = "#" + (path.startsWith("/") ? path : "/" + path);
    if (window.location.hash === path) {
        navigate();
    } else {
        window.location.hash = path;
    }
}
