/**
 * Карточка лота (LotShort). Возвращает готовый DOM-узел.
 *
 * onFavorite(lot, nextState) — колбэк клика по сердечку.
 * Если не передан — кнопка прячется.
 */

import { formatPrice, formatDate, escapeHtml } from "../utils.js";
import { lotImageUrl } from "../media.js";

const HEART_SVG = `
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
     stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
</svg>`;

export function renderLotCard(lot, { onFavorite, imagePriority } = {}) {
    const card = document.createElement("article");
    card.className = "lot-card";
    card.dataset.lotId = String(lot.id);

    const thumbSrc = lot.thumbnail ? lotImageUrl(lot.thumbnail) : null;
    const priorityAttr =
        imagePriority === "high" ? ' fetchpriority="high"' : "";
    const thumb = thumbSrc
        ? `<img class="lot-card-thumb" src="${escapeHtml(thumbSrc)}"
                 alt="${escapeHtml(lot.title)}" loading="lazy" decoding="async"${priorityAttr}>`
        : `<div class="lot-card-thumb placeholder">Нет фото</div>`;

    const favBtnHtml = onFavorite
        ? `<button type="button" class="favorite-btn ${lot.is_favorite ? "active" : ""}"
                    aria-label="${lot.is_favorite ? "Убрать из избранного" : "В избранное"}"
                    aria-pressed="${lot.is_favorite ? "true" : "false"}">
                ${HEART_SVG}
           </button>`
        : "";

    card.innerHTML = `
        ${favBtnHtml}
        ${thumb}
        <a class="lot-card-link" href="/lot.html?id=${lot.id}"
           aria-label="${escapeHtml(lot.title)}"></a>
        <div class="lot-card-body">
            <div class="lot-card-title">${escapeHtml(lot.title)}</div>
            <div class="lot-card-price">${escapeHtml(formatPrice(lot.price))}</div>
            <div class="lot-card-meta">
                ${
                    lot.region_name
                        ? `<span>${escapeHtml(lot.region_name)}</span>`
                        : ""
                }
                ${
                    lot.auction_date
                        ? `<span>Торги: ${escapeHtml(formatDate(lot.auction_date))}</span>`
                        : ""
                }
            </div>
        </div>
    `;

    const img = card.querySelector(".lot-card-thumb[src]");
    if (img) {
        const markLoaded = () => img.classList.add("is-loaded");
        if (img.complete) markLoaded();
        else {
            img.addEventListener("load", markLoaded, { once: true });
            img.addEventListener("error", () => img.classList.add("is-error"), {
                once: true,
            });
        }
    }

    if (onFavorite) {
        const btn = card.querySelector(".favorite-btn");
        btn.addEventListener("click", async (e) => {
            e.preventDefault();
            e.stopPropagation();
            btn.disabled = true;
            const next = !lot.is_favorite;
            try {
                await onFavorite(lot, next);
                lot.is_favorite = next;
                btn.classList.toggle("active", next);
                btn.setAttribute("aria-pressed", String(next));
                btn.setAttribute(
                    "aria-label",
                    next ? "Убрать из избранного" : "В избранное",
                );
            } finally {
                btn.disabled = false;
            }
        });
    }

    return card;
}

/** Рендерит несколько плейсхолдеров-скелетонов. */
export function renderLotSkeletons(count = 6) {
    const frag = document.createDocumentFragment();
    for (let i = 0; i < count; i++) {
        const card = document.createElement("div");
        card.className = "lot-card";
        card.setAttribute("aria-hidden", "true");
        card.innerHTML = `
            <div class="skeleton" style="width:100%;aspect-ratio:16/10"></div>
            <div class="lot-card-body">
                <div class="skeleton" style="height:14px;width:85%;margin-bottom:8px"></div>
                <div class="skeleton" style="height:14px;width:55%;margin-bottom:12px"></div>
                <div class="skeleton" style="height:18px;width:40%"></div>
            </div>
        `;
        frag.appendChild(card);
    }
    return frag;
}
