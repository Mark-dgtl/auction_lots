/**
 * Централизованный HTTP-клиент.
 *
 * Особенности:
 *  - credentials: "include" — чтобы cookie `refresh_token` летел в `/auth/refresh`.
 *  - Access-токен хранится в sessionStorage (пересоздаётся при каждом входе).
 *  - При 401 один раз пытается выполнить refresh и повторить исходный запрос.
 *  - Если refresh тоже упал — чистит состояние и редиректит на /login.html.
 *  - В обоих режимах (мок/реальный) возвращает ApiError при проблемах,
 *    так что страницы пишут одинаковый код.
 */

import { config } from "./config.js";
import { mockRouter } from "./api.mock.js";

const TOKEN_KEY = "ag_access_token";

export class ApiError extends Error {
    constructor(code, message, status) {
        super(message || code || "Неизвестная ошибка");
        this.name = "ApiError";
        this.code = code || "INTERNAL_ERROR";
        this.status = status ?? 0;
    }
}

export const tokenStore = {
    get() {
        return sessionStorage.getItem(TOKEN_KEY);
    },
    set(token) {
        if (token) sessionStorage.setItem(TOKEN_KEY, token);
    },
    clear() {
        sessionStorage.removeItem(TOKEN_KEY);
    },
};

// Флаг, чтобы не зацикливать refresh → request → refresh.
let refreshInflight = null;

function redirectToLogin() {
    const current = window.location.pathname + window.location.search;
    if (window.location.pathname.endsWith("/login.html")) return;
    const redirect = encodeURIComponent(current);
    window.location.href = `/login.html?redirect=${redirect}`;
}

async function tryRefresh() {
    // Делим один in-flight refresh между всеми параллельными запросами.
    if (refreshInflight) return refreshInflight;

    refreshInflight = (async () => {
        try {
            const data = await rawRequest("POST", "/auth/refresh", {
                _skipAuth: true,
                _skipRefresh: true,
            });
            if (data && data.access_token) {
                tokenStore.set(data.access_token);
                return true;
            }
            return false;
        } catch {
            return false;
        } finally {
            refreshInflight = null;
        }
    })();

    return refreshInflight;
}

/**
 * Низкоуровневый запрос. Не занимается 401-повторами;
 * это делает `request()` сверху.
 */
async function rawRequest(method, path, options = {}) {
    const url = path.startsWith("http") ? path : config.API_BASE_URL + path;

    const headers = new Headers(options.headers || {});
    if (!headers.has("Content-Type") && options.body !== undefined) {
        headers.set("Content-Type", "application/json");
    }
    if (!options._skipAuth) {
        const token = tokenStore.get();
        if (token) headers.set("Authorization", `Bearer ${token}`);
    }

    const init = {
        method,
        headers,
        credentials: "include",
    };
    if (options.body !== undefined) {
        init.body =
            typeof options.body === "string"
                ? options.body
                : JSON.stringify(options.body);
    }

    let response;
    if (config.USE_MOCK) {
        // В мок-режиме роутер возвращает объект { status, body } —
        // симулируем fetch-Response ровно настолько, насколько нам нужно.
        const mock = await mockRouter(method, path, options);
        response = {
            ok: mock.status >= 200 && mock.status < 300,
            status: mock.status,
            async json() {
                return mock.body;
            },
            async text() {
                return mock.body == null ? "" : JSON.stringify(mock.body);
            },
        };
    } else {
        response = await fetch(url, init);
    }

    if (response.status === 204) return null;

    let payload = null;
    try {
        payload = await response.json();
    } catch {
        payload = null;
    }

    if (!response.ok) {
        const err = payload && payload.error ? payload.error : {};
        const code = err.code || codeFromStatus(response.status);
        const message =
            err.message || messageForCode(code) || defaultMessage(response.status);
        throw new ApiError(code, message, response.status);
    }

    return payload;
}

/**
 * Дружелюбные сообщения для специальных кодов ошибок
 * (см. docs/CONTRACTS.md §2.1). Используется как fallback,
 * если backend не прислал поле `message`.
 */
function messageForCode(code) {
    switch (code) {
        case "NOT_ADMIN":
            return "Доступ только для администраторов";
        case "USER_BLOCKED":
            return "Пользователь заблокирован";
        case "INVALID_SQL":
            return "Недопустимый SQL-запрос";
        case "SQL_TIMEOUT":
            return "Запрос выполнялся слишком долго и был прерван";
        case "DML_NOT_CONFIRMED":
            return "Подтвердите выполнение опасной операции";
        case "BOT_OFFLINE":
            return "Бот сейчас offline — сообщение поставлено в очередь";
        case "JOB_NOT_FOUND":
            return "Задача шедулера не найдена";
        case "PARSER_BUSY":
            return "Парсер уже выполняется, дождитесь окончания";
        case "TELEGRAM_NOT_LINKED":
            return "Telegram не привязан к аккаунту";
        case "ALREADY_ADMIN":
            return "Действие невозможно: затрагивает последнего админа";
        default:
            return null;
    }
}

function codeFromStatus(status) {
    if (status === 400 || status === 422) return "VALIDATION_ERROR";
    if (status === 401) return "UNAUTHORIZED";
    if (status === 403) return "FORBIDDEN";
    if (status === 404) return "NOT_FOUND";
    if (status === 409) return "CONFLICT";
    if (status === 429) return "RATE_LIMITED";
    return "INTERNAL_ERROR";
}

function defaultMessage(status) {
    if (status === 0) return "Нет связи с сервером";
    if (status === 401) return "Требуется авторизация";
    if (status === 403) return "Недостаточно прав";
    if (status === 404) return "Не найдено";
    if (status >= 500) return "Ошибка сервера. Попробуйте ещё раз.";
    return "Ошибка запроса";
}

/**
 * Высокоуровневый запрос с логикой refresh-повтора.
 * @param {string} method
 * @param {string} path — относительно API_BASE_URL, начинается с "/"
 * @param {object} [options]
 * @returns {Promise<any>}
 */
async function request(method, path, options = {}) {
    try {
        return await rawRequest(method, path, options);
    } catch (e) {
        if (!(e instanceof ApiError)) {
            throw new ApiError("NETWORK_ERROR", "Нет связи с сервером", 0);
        }
        // 401 — пробуем обновить токен и повторить запрос один раз.
        const canRetry =
            e.status === 401 &&
            !options._skipRefresh &&
            !path.startsWith("/auth/");
        if (canRetry) {
            const ok = await tryRefresh();
            if (ok) {
                return await rawRequest(method, path, {
                    ...options,
                    _skipRefresh: true,
                });
            }
            // Refresh не прошёл — чистим access-токен. Если вызывающий
            // не попросил `_noRedirect`, шлём пользователя на логин с возвратом.
            tokenStore.clear();
            if (!options._noRedirect) {
                redirectToLogin();
            }
        }
        throw e;
    }
}

export const api = {
    get(path, options) {
        return request("GET", path, options);
    },
    post(path, body, options) {
        return request("POST", path, { ...options, body });
    },
    put(path, body, options) {
        return request("PUT", path, { ...options, body });
    },
    delete(path, options) {
        return request("DELETE", path, options);
    },
};
