/**
 * Парсер: карточки шедулерных задач (next_run, paused, кнопки),
 * форма «Запустить парсер сейчас», таблица последних 50 запусков.
 */

import { adminApi } from "../api.js";
import { toast } from "../../components/toast.js";
import { escapeHtml } from "../components/table.js";
import { formatDateTime } from "../../utils.js";

let unmounted = false;

export async function mount(root) {
    unmounted = false;
    root.innerHTML = `
        <div class="admin-page-header">
            <div>
                <h1>Parser</h1>
                <div class="subtitle">APScheduler-задачи и история запусков парсера.</div>
            </div>
            <div class="admin-page-actions">
                <button type="button" class="btn btn-secondary" id="reload-all">Обновить</button>
            </div>
        </div>

        <section class="admin-card" style="margin-bottom: var(--space-5)">
            <h3 class="card-title">Запустить парсер сейчас</h3>
            <form id="run-form" style="display:flex;gap:var(--space-2);align-items:flex-end;flex-wrap:wrap">
                <div class="field" style="margin: 0; min-width: 200px">
                    <label for="run-source">Источник</label>
                    <select id="run-source" class="select">
                        <option value="torgi_gov">torgi_gov</option>
                        <option value="all">all</option>
                    </select>
                </div>
                <button type="submit" class="btn btn-primary">Запустить</button>
            </form>
        </section>

        <section style="margin-bottom: var(--space-5)">
            <h3 style="margin-bottom: var(--space-3); font-size: var(--font-size-md)">Шедулер</h3>
            <div class="admin-grid" id="jobs-grid"></div>
        </section>

        <section class="admin-card">
            <h3 class="card-title">Последние запуски</h3>
            <div id="runs-table"></div>
        </section>
    `;

    root.querySelector("#reload-all").addEventListener("click", reloadAll);
    root.querySelector("#run-form").addEventListener("submit", onRunNow);

    await reloadAll();
}

export function unmount() {
    unmounted = true;
}

async function reloadAll() {
    await Promise.all([reloadJobs(), reloadRuns()]);
}

async function reloadJobs() {
    const grid = document.getElementById("jobs-grid");
    if (!grid) return;
    grid.innerHTML = '<div class="adm-state">Загрузка…</div>';
    try {
        const { items } = await adminApi.schedulerJobs();
        if (unmounted) return;
        if (!items || !items.length) {
            grid.innerHTML = '<div class="adm-state">Задач нет</div>';
            return;
        }
        grid.innerHTML = "";
        for (const job of items) {
            grid.appendChild(jobCard(job));
        }
    } catch (err) {
        grid.innerHTML = `<div class="adm-state error">${escapeHtml(err.message)}</div>`;
    }
}

function jobCard(job) {
    const card = document.createElement("div");
    card.className = "admin-card";
    card.innerHTML = `
        <div class="metric">
            <div class="metric-label">
                <span class="status-dot ${job.paused ? "warn" : "ok"}"></span>
                ${escapeHtml(job.name || job.id)}
            </div>
            <div class="metric-sub">
                <code class="code-inline">${escapeHtml(job.id)}</code>
            </div>
        </div>
        <dl class="kv-list" style="margin: var(--space-3) 0">
            <dt>Trigger</dt><dd>${escapeHtml(job.trigger || "—")}</dd>
            <dt>Next run</dt><dd>${escapeHtml(job.next_run_time ? formatDateTime(job.next_run_time) : "—")}</dd>
            <dt>Состояние</dt><dd>${job.paused ? '<span class="status-pill failed">paused</span>' : '<span class="status-pill ok">active</span>'}</dd>
        </dl>
        <div class="filters-actions">
            <button type="button" class="btn btn-secondary btn-sm" data-act="run">Run now</button>
            ${job.paused
                ? '<button type="button" class="btn btn-primary btn-sm" data-act="resume">Resume</button>'
                : '<button type="button" class="btn btn-secondary btn-sm" data-act="pause">Pause</button>'}
        </div>
    `;
    card.querySelector('[data-act="run"]').addEventListener("click", () => action(job.id, "run"));
    const pause = card.querySelector('[data-act="pause"]');
    const resume = card.querySelector('[data-act="resume"]');
    if (pause)  pause .addEventListener("click", () => action(job.id, "pause"));
    if (resume) resume.addEventListener("click", () => action(job.id, "resume"));
    return card;
}

async function action(id, kind) {
    try {
        if (kind === "run")    await adminApi.schedulerRun(id);
        if (kind === "pause")  await adminApi.schedulerPause(id);
        if (kind === "resume") await adminApi.schedulerResume(id);
        toast.success(`Задача ${id}: ${kind}`);
        reloadJobs();
        if (kind === "run") setTimeout(reloadRuns, 1500);
    } catch (err) {
        toast.fromApiError(err);
    }
}

async function reloadRuns() {
    const node = document.getElementById("runs-table");
    if (!node) return;
    node.innerHTML = '<div class="adm-state">Загрузка…</div>';
    try {
        const { items } = await adminApi.parserRuns(50);
        if (unmounted) return;
        if (!items || !items.length) {
            node.innerHTML = '<div class="adm-state">Запусков ещё не было</div>';
            return;
        }
        node.innerHTML = `
            <div class="adm-table-scroll">
                <table class="adm-table">
                    <thead><tr>
                        <th>Источник</th><th>Статус</th>
                        <th class="num">Seen</th><th class="num">New</th><th class="num">Upd</th>
                        <th class="num">Pages</th><th class="num">Yielded</th><th class="num">Invalid</th>
                        <th class="num">Expected</th><th>Full scan</th>
                        <th>Триггер</th>
                        <th>Старт</th><th>Финиш</th><th>Ошибка</th>
                    </tr></thead>
                    <tbody>
                        ${items.map((r) => `
                            <tr>
                                <td><span class="code-inline">${escapeHtml(r.source)}</span></td>
                                <td><span class="status-pill ${runStatusClass(r.status)}">${escapeHtml(r.status)}</span></td>
                                <td class="num">${r.lots_seen ?? 0}</td>
                                <td class="num">${r.lots_new ?? 0}</td>
                                <td class="num">${r.lots_updated ?? 0}</td>
                                <td class="num">${r.pages_fetched ?? 0}</td>
                                <td class="num">${r.yielded_total ?? 0}</td>
                                <td class="num">${r.skipped_invalid ?? 0}</td>
                                <td class="num">${r.expected_total_elements ?? "—"}</td>
                                <td>${r.full_scan_completed ? '<span class="status-pill ok">yes</span>' : '<span class="status-pill pending">no</span>'}</td>
                                <td>${escapeHtml(r.triggered_by || "—")}</td>
                                <td>${escapeHtml(formatDateTime(r.started_at))}</td>
                                <td>${escapeHtml(r.finished_at ? formatDateTime(r.finished_at) : "—")}</td>
                                <td class="muted" style="max-width:240px">${escapeHtml(r.error || "")}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `;
    } catch (err) {
        node.innerHTML = `<div class="adm-state error">${escapeHtml(err.message)}</div>`;
    }
}

function runStatusClass(s) {
    if (s === "ok" || s === "success") return "ok";
    if (s === "running") return "pending";
    if (s === "failed" || s === "error") return "failed";
    return "";
}

async function onRunNow(e) {
    e.preventDefault();
    const form = e.currentTarget;
    const submit = form.querySelector('button[type="submit"]');
    const source = form.querySelector("#run-source").value;
    submit.disabled = true;
    try {
        const r = await adminApi.parserRun(source);
        toast.success(`Запуск ${source}: ${r.status}, новых ${r.lots_new ?? 0}`);
        reloadRuns();
    } catch (err) {
        toast.fromApiError(err);
    } finally {
        submit.disabled = false;
    }
}
