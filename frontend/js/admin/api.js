/**
 * Admin-API клиент.
 *
 * Тонкий слой поверх базового `js/api.js`: добавляет именованные
 * методы для эндпоинтов из CONTRACTS §2.9. SSE-стрим логов
 * реализован отдельно (EventSource не несёт Authorization-заголовок,
 * поэтому при необходимости токен подмешивается в query — но в
 * текущем контракте бэк опирается на cookie sessionId через nginx;
 * см. CONTRACTS §2.9.2).
 */

import { api, tokenStore } from "../api.js";
import { config } from "../config.js";

export const adminApi = {
    // 2.9.1
    health() { return api.get("/admin/health"); },
    stats() { return api.get("/admin/stats"); },

    // 2.9.2
    logsSnapshot({ level, q, limit = 200 } = {}) {
        const qs = new URLSearchParams();
        if (level) qs.set("level", level);
        if (q) qs.set("q", q);
        if (limit) qs.set("limit", String(limit));
        const s = qs.toString();
        return api.get("/admin/logs" + (s ? "?" + s : ""));
    },

    // 2.9.3
    schedulerJobs()        { return api.get("/admin/scheduler/jobs"); },
    schedulerRun(id)       { return api.post(`/admin/scheduler/jobs/${encodeURIComponent(id)}/run`); },
    schedulerPause(id)     { return api.post(`/admin/scheduler/jobs/${encodeURIComponent(id)}/pause`); },
    schedulerResume(id)    { return api.post(`/admin/scheduler/jobs/${encodeURIComponent(id)}/resume`); },
    parserRun(source)      { return api.post("/admin/parser/run", { source }); },
    parserRuns(limit = 50) { return api.get(`/admin/parser/runs?limit=${limit}`); },

    // 2.9.4
    users({ q, page = 1, page_size = 20 } = {}) {
        const qs = new URLSearchParams();
        if (q) qs.set("q", q);
        qs.set("page", String(page));
        qs.set("page_size", String(page_size));
        return api.get("/admin/users?" + qs.toString());
    },
    user(id)         { return api.get(`/admin/users/${id}`); },
    userDelete(id)   { return api.delete(`/admin/users/${id}`); },
    userUnlinkTg(id) { return api.post(`/admin/users/${id}/unlink-telegram`); },
    // userPatch определён ниже отдельно — в базовом api.js нет метода PATCH.

    // 2.9.5
    lots({ source, status, q, page = 1, page_size = 20 } = {}) {
        const qs = new URLSearchParams();
        if (source) qs.set("source", source);
        if (status) qs.set("status", status);
        if (q) qs.set("q", q);
        qs.set("page", String(page));
        qs.set("page_size", String(page_size));
        return api.get("/admin/lots?" + qs.toString());
    },
    lotDelete(id)  { return api.delete(`/admin/lots/${id}`); },
    lotRefresh(id) { return api.post(`/admin/lots/${id}/refresh`); },

    // 2.9.6
    outbox({ status, limit = 50, offset = 0 } = {}) {
        const qs = new URLSearchParams();
        if (status) qs.set("status", status);
        qs.set("limit", String(limit));
        qs.set("offset", String(offset));
        return api.get("/admin/outbox?" + qs.toString());
    },
    outboxRetry(id)  { return api.post(`/admin/outbox/${id}/retry`); },
    outboxDelete(id) { return api.delete(`/admin/outbox/${id}`); },

    // 2.9.7
    botSend(body)      { return api.post("/admin/bot/send", body); },
    botBroadcast(body) { return api.post("/admin/bot/broadcast", body); },

    // 2.9.8
    dbTables()             { return api.get("/admin/db/tables"); },
    dbTableRows(name, { limit = 50, offset = 0 } = {}) {
        return api.get(
            `/admin/db/tables/${encodeURIComponent(name)}` +
            `?limit=${limit}&offset=${offset}`,
        );
    },
    dbReports()        { return api.get("/admin/db/reports"); },
    dbReportRun(id)    { return api.post(`/admin/db/reports/${encodeURIComponent(id)}/run`); },
    dbQuery(body)      { return api.post("/admin/db/query", body); },

    // 2.9.9
    digestTemplate()        { return api.get("/admin/digest/template"); },
    digestTemplateUpdate(body) { return api.put("/admin/digest/template", body); },
    digestRunNow()          { return api.post("/admin/digest/run-now"); },
};

/**
 * PATCH /admin/users/{id} в нашем базовом api.js не определён —
 * добавим вручную через fetch. Альтернатива: расширить api.js,
 * но контракт просит «минимально править».
 */
adminApi.userPatch = async function userPatch(id, body) {
    const url = config.API_BASE_URL + `/admin/users/${id}`;
    const headers = new Headers({ "Content-Type": "application/json" });
    const token = tokenStore.get();
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const resp = await fetch(url, {
        method: "PATCH",
        credentials: "include",
        headers,
        body: JSON.stringify(body),
    });
    if (resp.status === 204) return null;
    let payload = null;
    try { payload = await resp.json(); } catch { /* ignore */ }
    if (!resp.ok) {
        const err = (payload && payload.error) || {};
        const e = new Error(err.message || "Ошибка запроса");
        e.code = err.code || "INTERNAL_ERROR";
        e.status = resp.status;
        throw e;
    }
    return payload;
};

/**
 * Создаёт EventSource для live-tail логов.
 * EventSource в браузере не позволяет передавать кастомные заголовки,
 * поэтому полагаемся на cookie-сессию (refresh_token cookie стоит
 * как HttpOnly), плюс при необходимости можно прокинуть access_token
 * как query-параметр — backend должен его принять.
 *
 * @returns {EventSource}
 */
export function openLogsStream({ level, q } = {}) {
    const qs = new URLSearchParams();
    if (level) qs.set("level", level);
    if (q) qs.set("q", q);
    const token = tokenStore.get();
    if (token) qs.set("access_token", token);
    const s = qs.toString();
    const url = config.API_BASE_URL + "/admin/logs/stream" + (s ? "?" + s : "");
    return new EventSource(url, { withCredentials: true });
}
