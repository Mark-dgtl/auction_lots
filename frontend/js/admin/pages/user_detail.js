/**
 * Карточка пользователя с формой редактирования + историей outbox.
 */

import { adminApi } from "../api.js";
import { toast } from "../../components/toast.js";
import { confirm } from "../components/dialog.js";
import { escapeHtml } from "../components/table.js";
import { go } from "../router.js";
import { formatDateTime } from "../../utils.js";

let currentUser = null;

export async function mount(root, params) {
    const id = Number(params.id);
    if (!id) {
        root.innerHTML = `<div class="adm-state error">Неверный id пользователя</div>`;
        return;
    }

    root.innerHTML = `
        <div class="admin-page-header">
            <div>
                <h1>Пользователь #${id}</h1>
                <div class="subtitle">
                    <a href="#/users">← к списку</a>
                </div>
            </div>
            <div class="admin-page-actions" id="page-actions"></div>
        </div>
        <div id="user-content"><div class="adm-state">Загрузка…</div></div>
    `;

    try {
        const u = await adminApi.user(id);
        currentUser = u;
        renderUser(u);
    } catch (err) {
        document.getElementById("user-content").innerHTML =
            `<div class="adm-state error">${escapeHtml(err.message || "Ошибка")}</div>`;
    }
}

export function unmount() {
    currentUser = null;
}

function renderUser(u) {
    const root = document.getElementById("user-content");
    root.innerHTML = `
        <div class="admin-grid-2">
            <section class="admin-card">
                <h3 class="card-title">Профиль</h3>
                <form id="edit-form">
                    <div class="field">
                        <label>Email</label>
                        <input class="input" value="${escapeHtml(u.email || "")}" disabled>
                    </div>
                    <div class="field">
                        <label for="f-full-name">Имя</label>
                        <input class="input" id="f-full-name" name="full_name"
                               value="${escapeHtml(u.full_name || "")}"
                               placeholder="Не указано">
                    </div>
                    <div class="field">
                        <label for="f-digest">Время дайджеста (HH:MM)</label>
                        <input class="input" id="f-digest" name="digest_time"
                               value="${escapeHtml(u.digest_time || "")}"
                               placeholder="09:00" pattern="^\\d{2}:\\d{2}$">
                    </div>
                    <div class="field">
                        <label class="checkbox">
                            <input type="checkbox" name="is_admin" ${u.is_admin ? "checked" : ""}>
                            Администратор
                        </label>
                    </div>
                    <div class="field">
                        <label class="checkbox">
                            <input type="checkbox" name="is_blocked" ${u.is_blocked ? "checked" : ""}>
                            Заблокирован
                        </label>
                    </div>
                    <div class="filters-actions">
                        <button type="submit" class="btn btn-primary">Сохранить</button>
                        <button type="button" class="btn btn-secondary" id="reset-btn">Сбросить</button>
                    </div>
                </form>
            </section>

            <section class="admin-card">
                <h3 class="card-title">Telegram & данные</h3>
                <dl class="kv-list">
                    <dt>ID</dt><dd>${u.id}</dd>
                    <dt>Создан</dt><dd>${escapeHtml(formatDateTime(u.created_at))}</dd>
                    <dt>Tz дайджеста</dt><dd>${escapeHtml(u.digest_tz || "—")}</dd>
                    <dt>Telegram</dt>
                    <dd>${
                        u.telegram_linked
                            ? `<span class="status-pill ok">привязан</span> <span class="muted">(user_id ${u.telegram_user_id ?? "—"})</span>`
                            : '<span class="muted">не привязан</span>'
                    }</dd>
                    <dt>Избранное</dt><dd>${u.favorites_count ?? 0}</dd>
                    <dt>Фильтров</dt><dd>${u.filters_count ?? 0}</dd>
                </dl>

                <div class="divider"></div>

                <div class="filters-actions">
                    <button type="button" class="btn btn-secondary" id="unlink-tg" ${u.telegram_linked ? "" : "disabled"}>
                        Отвязать TG
                    </button>
                    <button type="button" class="btn btn-danger" id="delete-user">
                        Удалить
                    </button>
                </div>
            </section>
        </div>

        <div style="height: var(--space-5)"></div>

        <section class="admin-card">
            <h3 class="card-title">Последние сообщения (outbox)</h3>
            ${renderOutbox(u.recent_outbox || [])}
        </section>
    `;

    const form = root.querySelector("#edit-form");
    form.addEventListener("submit", (e) => onSave(e, form, u.id));
    root.querySelector("#reset-btn").addEventListener("click", () => renderUser(u));
    root.querySelector("#unlink-tg").addEventListener("click", () => onUnlinkTg(u.id));
    root.querySelector("#delete-user").addEventListener("click", () => onDelete(u.id, u.email));
}

function renderOutbox(items) {
    if (!items.length) return '<div class="adm-state">Пока нет</div>';
    const rows = items.map((o) => `
        <tr>
            <td>${o.id}</td>
            <td><span class="status-pill ${o.status}">${escapeHtml(o.status)}</span></td>
            <td>${escapeHtml(formatDateTime(o.created_at))}</td>
            <td>${escapeHtml(o.sent_at ? formatDateTime(o.sent_at) : "—")}</td>
            <td><div class="expandable">${escapeHtml(o.text || "")}</div></td>
        </tr>
    `).join("");
    return `
        <div class="adm-table-scroll">
            <table class="adm-table">
                <thead>
                    <tr><th>ID</th><th>Статус</th><th>Создан</th><th>Отправлен</th><th>Текст</th></tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
}

async function onSave(e, form, id) {
    e.preventDefault();
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;

    const body = {
        full_name: form.full_name.value.trim() || null,
        digest_time: form.digest_time.value.trim() || null,
        is_admin: form.is_admin.checked,
        is_blocked: form.is_blocked.checked,
    };

    if (body.digest_time && !/^\d{2}:\d{2}$/.test(body.digest_time)) {
        toast.error("Время в формате HH:MM");
        submit.disabled = false;
        return;
    }

    try {
        const updated = await adminApi.userPatch(id, body);
        currentUser = updated;
        renderUser(updated);
        toast.success("Сохранено");
    } catch (err) {
        toast.fromApiError(err);
    } finally {
        submit.disabled = false;
    }
}

async function onUnlinkTg(id) {
    const ok = await confirm(
        "Отвязать Telegram?",
        "Пользователь больше не будет получать уведомления, пока не привяжет аккаунт заново.",
        { okText: "Отвязать", cancelText: "Оставить" },
    );
    if (!ok) return;
    try {
        await adminApi.userUnlinkTg(id);
        toast.success("Telegram отвязан");
        const u = await adminApi.user(id);
        renderUser(u);
    } catch (err) {
        toast.fromApiError(err);
    }
}

async function onDelete(id, email) {
    const ok = await confirm(
        "Удалить пользователя?",
        `${email} будет удалён вместе с избранным и фильтрами. Действие необратимо.`,
        { okText: "Удалить", cancelText: "Отмена" },
    );
    if (!ok) return;
    try {
        await adminApi.userDelete(id);
        toast.success("Пользователь удалён");
        go("/users");
    } catch (err) {
        toast.fromApiError(err);
    }
}

// Делает «развернуть/свернуть» для длинных ячеек outbox.
document.addEventListener("click", (e) => {
    const t = e.target.closest(".expandable");
    if (t) t.classList.toggle("expanded");
});
