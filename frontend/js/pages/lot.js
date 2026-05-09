/**
 * Страница карточки лота.
 * ?id=123 → GET /api/lots/123 → рендер галереи + инфы + действия.
 */

import { renderHeader } from "../components/header.js";
import { renderFooter } from "../components/footer.js";
import { api, ApiError } from "../api.js";
import { getCurrentUser } from "../auth.js";
import { toast } from "../components/toast.js";
import {
    qs,
    readQuery,
    formatPrice,
    formatDate,
    formatDateTime,
    escapeHtml,
} from "../utils.js";

async function boot() {
    await renderHeader(null);
    renderFooter();

    const { id } = readQuery();
    if (!id) {
        renderNotFound("Не указан идентификатор лота");
        return;
    }

    const user = await getCurrentUser();

    qs("#lot-root").innerHTML = skeleton();

    try {
        const lot = await api.get(`/lots/${encodeURIComponent(id)}`);
        renderLot(lot, user);
    } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
            renderNotFound("Лот не найден");
        } else {
            renderNotFound(safeMsg(e));
            if (e instanceof ApiError) toast.fromApiError(e);
        }
    }
}

function skeleton() {
    return `
        <div class="lot-layout">
            <div>
                <div class="skeleton" style="width:100%;aspect-ratio:16/10;border-radius:var(--radius-lg)"></div>
                <div class="skeleton" style="width:70%;height:28px;margin-top:var(--space-4)"></div>
                <div class="skeleton" style="width:40%;height:16px;margin-top:var(--space-3)"></div>
                <div class="skeleton" style="width:100%;height:80px;margin-top:var(--space-4)"></div>
            </div>
            <aside>
                <div class="skeleton" style="width:100%;height:200px;border-radius:var(--radius-lg)"></div>
            </aside>
        </div>`;
}

function renderNotFound(msg) {
    qs("#lot-root").innerHTML = `
        <div class="empty-state">
            <h2>Не удалось открыть лот</h2>
            <p>${escapeHtml(msg)}</p>
            <p style="margin-top:var(--space-4)">
                <a class="btn btn-primary" href="/search.html">К поиску</a>
            </p>
        </div>`;
}

function renderLot(lot, user) {
    const images = Array.isArray(lot.images) ? lot.images : [];
    qs("#lot-root").innerHTML = `
        <div class="lot-layout">
            <div>
                <div class="lot-gallery">
                    <div class="lot-gallery-main" id="gallery-main">
                        ${
                            images[0]
                                ? `<img src="${escapeHtml(images[0])}" alt="${escapeHtml(lot.title)}">`
                                : `<span>Нет фото</span>`
                        }
                    </div>
                    ${
                        images.length > 1
                            ? `<div class="lot-gallery-thumbs" role="tablist">
                                ${images
                                    .map(
                                        (src, i) => `
                                    <button type="button" class="${i === 0 ? "active" : ""}"
                                            data-idx="${i}"
                                            aria-label="Фото ${i + 1}"
                                            role="tab">
                                        <img src="${escapeHtml(src)}" alt="">
                                    </button>`,
                                    )
                                    .join("")}
                              </div>`
                            : ""
                    }
                </div>

                <article style="margin-top: var(--space-5)">
                    <div class="lot-header">
                        <div>
                            <h1 class="lot-title">${escapeHtml(lot.title)}</h1>
                            <div class="lot-meta">
                                ${
                                    lot.region_name
                                        ? `<span class="badge badge-muted">${escapeHtml(lot.region_name)}</span>`
                                        : ""
                                }
                                ${
                                    lot.category
                                        ? `<span class="badge">${escapeHtml(lot.category)}</span>`
                                        : ""
                                }
                                ${
                                    lot.status
                                        ? `<span class="muted">Статус: ${escapeHtml(lot.status)}</span>`
                                        : ""
                                }
                            </div>
                        </div>
                    </div>
                    <h3 style="margin-bottom:var(--space-2)">Описание</h3>
                    <div class="lot-description">${escapeHtml(lot.description || "Описание отсутствует.")}</div>
                </article>
            </div>

            <aside class="lot-sidebar">
                <div class="card">
                    <div class="price-block">${escapeHtml(formatPrice(lot.price))}</div>
                    ${
                        lot.price_step
                            ? `<div class="muted text-sm" style="margin-top:var(--space-1)">
                                  Шаг: ${escapeHtml(formatPrice(lot.price_step))}
                               </div>`
                            : ""
                    }

                    <div class="info-rows" style="margin-top:var(--space-4)">
                        ${row("Дата торгов", formatDateTime(lot.auction_date))}
                        ${row("Опубликовано", formatDate(lot.published_at))}
                        ${row("Источник", escapeHtml(lot.source || "—"))}
                    </div>

                    <div style="display:flex;flex-direction:column;gap:var(--space-2);margin-top:var(--space-4)">
                        ${
                            user
                                ? `<button type="button" class="btn btn-primary btn-block" id="fav-btn"
                                          aria-pressed="${lot.is_favorite ? "true" : "false"}">
                                      ${lot.is_favorite ? "В избранном" : "В избранное"}
                                   </button>`
                                : `<a class="btn btn-primary btn-block" href="/login.html?redirect=${encodeURIComponent(location.pathname + location.search)}">
                                      Войти, чтобы добавить в избранное
                                   </a>`
                        }
                        ${
                            lot.source_url
                                ? `<a class="btn btn-secondary btn-block" href="${escapeHtml(lot.source_url)}"
                                      target="_blank" rel="noopener noreferrer">
                                      Открыть источник ↗
                                   </a>`
                                : ""
                        }
                    </div>
                </div>
            </aside>
        </div>`;

    // Галерея: клик по миниатюре меняет главное фото
    const thumbs = qs("#lot-root").querySelectorAll(".lot-gallery-thumbs button");
    const main = qs("#gallery-main");
    thumbs.forEach((btn) => {
        btn.addEventListener("click", () => {
            thumbs.forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            const idx = Number(btn.dataset.idx);
            const src = images[idx];
            if (src) main.innerHTML = `<img src="${escapeHtml(src)}" alt="${escapeHtml(lot.title)}">`;
        });
    });

    // Избранное
    const favBtn = qs("#fav-btn");
    if (favBtn) {
        favBtn.addEventListener("click", async () => {
            const next = !lot.is_favorite;
            favBtn.disabled = true;
            try {
                if (next) await api.post(`/favorites/${lot.id}`);
                else await api.delete(`/favorites/${lot.id}`);
                lot.is_favorite = next;
                favBtn.textContent = next ? "В избранном" : "В избранное";
                favBtn.setAttribute("aria-pressed", String(next));
                (next ? toast.success : toast.info)(
                    next ? "Добавлено в избранное" : "Удалено из избранного",
                );
            } catch (e) {
                toast.fromApiError(e);
            } finally {
                favBtn.disabled = false;
            }
        });
    }
}

function row(label, value) {
    return `
        <div class="row">
            <span class="label">${escapeHtml(label)}</span>
            <span class="value">${escapeHtml(value)}</span>
        </div>`;
}

function safeMsg(e) {
    return (e && e.message ? e.message : "Неизвестная ошибка").replace(
        /[<>&"']/g,
        "",
    );
}

boot();
