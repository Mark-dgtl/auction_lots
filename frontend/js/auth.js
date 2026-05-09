/**
 * Хранение и загрузка текущего пользователя.
 * Сам access-токен лежит в sessionStorage (api.js), здесь — только user-объект в памяти.
 */

import { api, tokenStore, ApiError } from "./api.js";

let currentUser = null;
let loadPromise = null;

/**
 * Асинхронно получает текущего пользователя (кеширует).
 * Если токена нет или /me вернул 401 — возвращает null (не бросает).
 */
export async function getCurrentUser() {
    if (currentUser) return currentUser;
    if (!tokenStore.get()) {
        // #region agent log
        fetch("http://127.0.0.1:7460/ingest/7bcbbbf8-5316-4074-8658-ad3265ad53e3", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Debug-Session-Id": "3e7f94",
            },
            body: JSON.stringify({
                sessionId: "3e7f94",
                location: "auth.js:getCurrentUser",
                message: "no access token",
                data: {},
                timestamp: Date.now(),
                hypothesisId: "H1",
            }),
        }).catch(() => {});
        // #endregion
        return null;
    }

    if (!loadPromise) {
        loadPromise = (async () => {
            try {
                // `_noRedirect: true` — на публичных страницах (index/search/lot)
                // протухший токен не должен выкидывать анонима на /login.html.
                // Мы просто сбросим токен и продолжим как аноним.
                currentUser = await api.get("/me", { _noRedirect: true });
                return currentUser;
            } catch (e) {
                // #region agent log
                fetch("http://127.0.0.1:7460/ingest/7bcbbbf8-5316-4074-8658-ad3265ad53e3", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Debug-Session-Id": "3e7f94",
                    },
                    body: JSON.stringify({
                        sessionId: "3e7f94",
                        location: "auth.js:getCurrentUser:catch",
                        message: "/me failed",
                        data: {
                            isApiError: e instanceof ApiError,
                            status: e instanceof ApiError ? e.status : null,
                            code: e instanceof ApiError ? e.code : null,
                        },
                        timestamp: Date.now(),
                        hypothesisId: "H2-H4",
                    }),
                }).catch(() => {});
                // #endregion
                if (e instanceof ApiError && e.status === 401) {
                    return null;
                }
                return null;
            } finally {
                loadPromise = null;
            }
        })();
    }
    return loadPromise;
}

export async function login(email, password) {
    const resp = await api.post("/auth/login", { email, password });
    if (resp && resp.access_token) {
        tokenStore.set(resp.access_token);
        currentUser = null; // инвалидируем кеш
    }
    return resp;
}

/**
 * Возвращает целевой URL для редиректа после успешного входа.
 * Если у пользователя `is_admin === true` — отправляем в админку,
 * иначе — на переданный fallback (по умолчанию `/index.html`).
 *
 * Не падает: при любых ошибках получения /me возвращает fallback.
 */
export async function resolvePostLoginRedirect(fallback = "/index.html") {
    try {
        clearCache();
        const user = await getCurrentUser();
        if (user && user.is_admin === true) return "/admin.html";
        return fallback;
    } catch {
        return fallback;
    }
}

export async function register(email, password) {
    return api.post("/auth/register", { email, password });
}

export async function logout() {
    try {
        await api.post("/auth/logout");
    } catch {
        // даже если сервер вернул ошибку — локально выходим
    }
    tokenStore.clear();
    currentUser = null;
}

export function clearCache() {
    currentUser = null;
}
