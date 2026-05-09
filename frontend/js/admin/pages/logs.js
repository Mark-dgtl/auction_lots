/**
 * Live-tail логов через SSE.
 *
 * - При монтировании сначала тянем снапшот /admin/logs (последние 200),
 *   потом подключаем EventSource на /admin/logs/stream.
 * - Фильтры (level + substring) применяются клиентски к новым записям
 *   и при перерисовке списка. Они также передаются в snapshot/stream
 *   как query-параметры (бэк может отфильтровать заранее — это ок).
 * - В DOM держим максимум MAX_DOM строк, лишнее усекаем сверху.
 * - Автоскролл к низу — только если пользователь и так у низа
 *   (порог ~40px). Если он скроллил вверх — не дёргаем.
 * - Pause закрывает EventSource, Resume — переоткрывает.
 * - При обрыве (onerror) — реконнект через 3 секунды.
 */

import { adminApi, openLogsStream } from "../api.js";
import { escapeHtml } from "../components/table.js";
import { debounce } from "../../utils.js";

const MAX_DOM = 500;
const RECONNECT_MS = 3000;

let es = null;
let reconnectTimer = null;
let unmounted = false;
let viewportEl = null;
let filters = { level: "", q: "" };
let paused = false;

export async function mount(root) {
    unmounted = false;
    paused = false;
    filters = { level: "", q: "" };

    root.innerHTML = `
        <div class="admin-page-header">
            <div>
                <h1>Logs</h1>
                <div class="subtitle">Live-tail логов backend и бота. Кольцевой буфер на сервере.</div>
            </div>
            <div class="admin-page-actions">
                <span class="logs-status" id="logs-status">
                    <span class="status-dot warn"></span>подключение…
                </span>
                <button type="button" class="btn btn-secondary" id="pause-btn">Pause</button>
                <button type="button" class="btn btn-secondary" id="clear-btn">Очистить</button>
            </div>
        </div>

        <div class="logs-toolbar">
            <select class="select" id="f-level" style="max-width: 180px">
                <option value="">Все уровни</option>
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
            </select>
            <input type="search" class="input grow" id="f-q"
                   placeholder="Поиск по сообщению (substring)…">
        </div>

        <div class="logs-viewport" id="logs-viewport"></div>
    `;

    viewportEl = root.querySelector("#logs-viewport");

    const levelSel = root.querySelector("#f-level");
    const qInput = root.querySelector("#f-q");
    levelSel.addEventListener("change", () => {
        filters.level = levelSel.value;
        reconnect();
    });
    qInput.addEventListener("input", debounce(() => {
        filters.q = qInput.value.trim();
        applyFilterToDom();
        reconnect();
    }, 300));

    const pauseBtn = root.querySelector("#pause-btn");
    pauseBtn.addEventListener("click", () => {
        if (paused) { resume(pauseBtn); } else { pause(pauseBtn); }
    });

    root.querySelector("#clear-btn").addEventListener("click", () => {
        viewportEl.innerHTML = "";
    });

    // Снапшот → стрим
    try {
        const snap = await adminApi.logsSnapshot({ limit: 200 });
        if (unmounted) return;
        for (const rec of (snap.items || [])) appendLine(rec, /*tail*/ false);
        scrollToBottom();
    } catch (e) {
        appendLine({
            ts: new Date().toISOString(),
            level: "WARNING",
            source: "ui",
            logger: "admin.logs",
            message: "Не удалось загрузить снапшот: " + (e.message || e),
        });
    }
    if (!unmounted) connectStream();
}

export function unmount() {
    unmounted = true;
    closeStream();
}

function pause(btn) {
    paused = true;
    closeStream();
    btn.textContent = "Resume";
    setStatus("warn", "приостановлено");
}

function resume(btn) {
    paused = false;
    btn.textContent = "Pause";
    connectStream();
}

function reconnect() {
    if (paused) return;
    closeStream();
    connectStream();
}

function closeStream() {
    if (es) {
        try { es.close(); } catch { /* noop */ }
        es = null;
    }
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }
}

function connectStream() {
    if (unmounted || paused) return;
    setStatus("warn", "подключение…");
    try {
        es = openLogsStream({ level: filters.level, q: filters.q });
    } catch (e) {
        setStatus("error", "не удалось открыть поток");
        scheduleReconnect();
        return;
    }
    es.onopen = () => setStatus("ok", "live");
    es.onmessage = (ev) => {
        try {
            const rec = JSON.parse(ev.data);
            appendLine(rec);
            trimDom();
            scrollToBottom();
        } catch (e) {
            console.warn("[logs] bad event", ev.data);
        }
    };
    es.onerror = () => {
        setStatus("error", "обрыв связи · реконнект…");
        closeStream();
        scheduleReconnect();
    };
}

function scheduleReconnect() {
    if (unmounted || paused) return;
    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectStream();
    }, RECONNECT_MS);
}

function setStatus(kind, text) {
    const el = document.getElementById("logs-status");
    if (!el) return;
    el.innerHTML = `<span class="status-dot ${kind}"></span>${escapeHtml(text)}`;
}

function appendLine(rec, _tail = true) {
    if (!viewportEl) return;
    const level = (rec.level || "").toUpperCase();
    if (filters.level && level !== filters.level) return;
    if (filters.q && !(rec.message || "").toLowerCase().includes(filters.q.toLowerCase())) return;

    const div = document.createElement("div");
    div.className = `log-line lvl-${level}`;
    div.dataset.level = level;
    div.dataset.message = rec.message || "";
    div.innerHTML = `
        <span class="ts">${escapeHtml(formatTs(rec.ts))}</span>
        <span class="lvl">${escapeHtml(level || "-")}</span>
        <span class="src">[${escapeHtml(rec.source || "-")}]</span>
        <span class="name">${escapeHtml(rec.logger || "")}</span>
        <span class="msg">${escapeHtml(rec.message || "")}</span>
    `;
    viewportEl.appendChild(div);
}

function applyFilterToDom() {
    if (!viewportEl) return;
    const lvl = filters.level;
    const q = (filters.q || "").toLowerCase();
    for (const node of viewportEl.children) {
        const okLevel = !lvl || node.dataset.level === lvl;
        const okQ = !q || (node.dataset.message || "").toLowerCase().includes(q);
        node.style.display = (okLevel && okQ) ? "" : "none";
    }
}

function trimDom() {
    if (!viewportEl) return;
    const overflow = viewportEl.children.length - MAX_DOM;
    if (overflow > 0) {
        for (let i = 0; i < overflow; i++) {
            viewportEl.removeChild(viewportEl.firstChild);
        }
    }
}

function scrollToBottom() {
    if (!viewportEl) return;
    const distance = viewportEl.scrollHeight - viewportEl.scrollTop - viewportEl.clientHeight;
    if (distance < 60) {
        viewportEl.scrollTop = viewportEl.scrollHeight;
    }
}

function formatTs(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3, "0")}`;
}
