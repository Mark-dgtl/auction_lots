/**
 * Dashboard. Раз в 5 секунд опрашивает /admin/health и /admin/stats.
 * Цвета индикаторов: зелёный/жёлтый/красный по простым правилам ниже.
 */

import { adminApi } from "../api.js";
import { formatDateTime } from "../../utils.js";
import { escapeHtml } from "../components/table.js";

const REFRESH_MS = 5000;
let timer = null;
let unmounted = false;

export async function mount(root) {
    unmounted = false;
    root.innerHTML = `
        <div class="admin-page-header">
            <div>
                <h1>Dashboard</h1>
                <div class="subtitle">Сводка состояния системы. Обновляется каждые ${REFRESH_MS / 1000} сек.</div>
            </div>
            <div class="admin-page-actions">
                <button type="button" class="btn btn-secondary" id="refresh-now">Обновить</button>
            </div>
        </div>
        <section class="admin-grid" id="health-cards"></section>
        <div style="height: var(--space-5)"></div>
        <section class="admin-grid" id="stats-cards"></section>
        <div style="height: var(--space-5)"></div>
        <section class="admin-card">
            <h3 class="card-title">Последние запуски парсера</h3>
            <div id="last-runs"></div>
        </section>
    `;
    root.querySelector("#refresh-now").addEventListener("click", refresh);
    await refresh();
    timer = setInterval(refresh, REFRESH_MS);
}

export function unmount() {
    unmounted = true;
    if (timer) clearInterval(timer);
    timer = null;
}

async function refresh() {
    if (unmounted) return;
    const [health, stats] = await Promise.allSettled([
        adminApi.health(),
        adminApi.stats(),
    ]);
    if (unmounted) return;

    if (health.status === "fulfilled") {
        renderHealth(health.value);
        renderRuns(health.value.parser && health.value.parser.last_runs);
    } else {
        renderError("health-cards", health.reason);
        renderError("last-runs", health.reason);
    }
    if (stats.status === "fulfilled") {
        renderStats(stats.value);
    } else {
        renderError("stats-cards", stats.reason);
    }
}

function renderError(id, err) {
    const node = document.getElementById(id);
    if (!node) return;
    node.innerHTML = `<div class="adm-state error">${escapeHtml(err && err.message || "Ошибка")}</div>`;
}

function renderHealth(h) {
    const cards = [
        healthCard("База данных", h.db && h.db.ok ? "ok" : "error",
            h.db ? `Латентность: ${h.db.latency_ms ?? "—"} мс` : "—"),
        healthCard("Шедулер",
            h.scheduler && h.scheduler.running ? "ok" : "error",
            h.scheduler
                ? `Задач: ${(h.scheduler.jobs || []).length}`
                : "—"),
        healthCard("Бот",
            h.bot && h.bot.online ? "ok" : "error",
            h.bot && h.bot.last_heartbeat_at
                ? `Heartbeat: ${formatDateTime(h.bot.last_heartbeat_at)}`
                : "Нет heartbeat"),
        healthCard("Outbox",
            outboxColor(h.outbox),
            h.outbox
                ? `pending: ${h.outbox.pending} · failed: ${h.outbox.failed}`
                : "—"),
        healthCard("Процесс",
            "ok",
            h.process
                ? `v${h.process.version} · uptime ${formatUptime(h.process.uptime_seconds)}<br>RSS ${h.process.rss_mb} MB · CPU ${h.process.cpu_percent}%`
                : "—",
            { html: true }),
    ];
    document.getElementById("health-cards").innerHTML = cards.join("");
}

function outboxColor(o) {
    if (!o) return "warn";
    if (o.failed > 0) return "error";
    if (o.pending > 50 || (o.oldest_pending_age_seconds || 0) > 600) return "warn";
    return "ok";
}

function healthCard(label, color, sub, { html = false } = {}) {
    return `
        <div class="admin-card">
            <div class="metric">
                <div class="metric-label">
                    <span class="status-dot ${color}"></span>${escapeHtml(label)}
                </div>
                <div class="metric-sub">${html ? sub : escapeHtml(sub)}</div>
            </div>
        </div>
    `;
}

function renderStats(s) {
    const cards = [
        statCard("Пользователи", s.users_total, `админов ${s.users_admin} · с TG ${s.users_with_telegram} · заблок. ${s.users_blocked}`),
        statCard("Лотов", s.lots_total, `за 24ч +${s.lots_added_24h}`),
        statCard("Избранное", s.favorites_total, `фильтров ${s.filters_total} · с уведомл. ${s.filters_with_notify}`),
        statCard("Outbox",
            (s.outbox && (s.outbox.pending + s.outbox.sent + s.outbox.failed)) || 0,
            s.outbox ? `pending ${s.outbox.pending} · sent ${s.outbox.sent} · failed ${s.outbox.failed}` : "—"),
        statCard("Ошибок за 24ч", s.errors_24h, ""),
    ];
    document.getElementById("stats-cards").innerHTML = cards.join("");
}

function statCard(label, value, sub) {
    return `
        <div class="admin-card">
            <div class="metric">
                <div class="metric-label">${escapeHtml(label)}</div>
                <div class="metric-value">${escapeHtml(String(value ?? "—"))}</div>
                <div class="metric-sub">${escapeHtml(sub)}</div>
            </div>
        </div>
    `;
}

function renderRuns(runs) {
    const node = document.getElementById("last-runs");
    if (!node) return;
    if (!runs || runs.length === 0) {
        node.innerHTML = '<div class="adm-state">Запусков ещё не было</div>';
        return;
    }
    const top = runs.slice(0, 5);
    node.innerHTML = `
        <table class="adm-table">
            <thead><tr>
                <th>Источник</th><th>Статус</th>
                <th class="num">Seen</th><th class="num">New</th><th class="num">Upd</th>
                <th>Старт</th><th>Финиш</th>
            </tr></thead>
            <tbody>
                ${top.map((r) => `
                    <tr>
                        <td><span class="code-inline">${escapeHtml(r.source)}</span></td>
                        <td><span class="status-pill ${runStatusClass(r.status)}">${escapeHtml(r.status)}</span></td>
                        <td class="num">${r.lots_seen ?? 0}</td>
                        <td class="num">${r.lots_new ?? 0}</td>
                        <td class="num">${r.lots_updated ?? 0}</td>
                        <td>${escapeHtml(formatDateTime(r.started_at))}</td>
                        <td>${escapeHtml(r.finished_at ? formatDateTime(r.finished_at) : "—")}</td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `;
}

function runStatusClass(s) {
    if (s === "ok" || s === "success") return "ok";
    if (s === "running") return "pending";
    if (s === "failed" || s === "error") return "failed";
    return "";
}

function formatUptime(sec) {
    sec = Number(sec) || 0;
    const d = Math.floor(sec / 86400);
    const h = Math.floor((sec % 86400) / 3600);
    const m = Math.floor((sec % 3600) / 60);
    if (d > 0) return `${d}д ${h}ч`;
    if (h > 0) return `${h}ч ${m}м`;
    return `${m}м`;
}
