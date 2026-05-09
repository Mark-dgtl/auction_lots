/**
 * Вспомогательные утилиты: форматирование цен/дат, экранирование, DOM.
 */

import { config } from "./config.js";

const priceFmt = new Intl.NumberFormat(config.LOCALE, {
    style: "currency",
    currency: config.CURRENCY,
    maximumFractionDigits: 0,
});

// Даты от backend приходят в UTC (суффикс "Z" или "+00:00"). Intl корректно
// распарсит и отформатирует их в указанной timeZone.
const dateFmt = new Intl.DateTimeFormat(config.LOCALE, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: config.TZ,
});

const dateTimeFmt = new Intl.DateTimeFormat(config.LOCALE, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: config.TZ,
});

export function formatPrice(value) {
    if (value == null || value === "") return "—";
    const n = typeof value === "string" ? Number(value) : value;
    if (!isFinite(n)) return "—";
    return priceFmt.format(n);
}

export function formatDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d)) return "—";
    return dateFmt.format(d);
}

export function formatDateTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d)) return "—";
    return dateTimeFmt.format(d);
}

export function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

export function debounce(fn, ms = 250) {
    let t;
    return function (...args) {
        clearTimeout(t);
        t = setTimeout(() => fn.apply(this, args), ms);
    };
}

export function qs(sel, root = document) {
    return root.querySelector(sel);
}

export function qsa(sel, root = document) {
    return Array.from(root.querySelectorAll(sel));
}

export function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
        if (k === "class") node.className = v;
        else if (k === "text") node.textContent = v;
        else if (k === "html") node.innerHTML = v;
        else if (k.startsWith("on") && typeof v === "function") {
            node.addEventListener(k.slice(2).toLowerCase(), v);
        } else if (v === true) node.setAttribute(k, "");
        else if (v !== false && v != null) node.setAttribute(k, String(v));
    }
    const list = Array.isArray(children) ? children : [children];
    for (const c of list) {
        if (c == null || c === false) continue;
        node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return node;
}

/**
 * Собирает URL с query-параметрами, пропуская пустые значения.
 */
export function buildQuery(params) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
        if (v == null || v === "") continue;
        qs.set(k, v);
    }
    const s = qs.toString();
    return s ? "?" + s : "";
}

/**
 * Парсит URLSearchParams текущего документа в простой объект.
 */
export function readQuery() {
    const out = {};
    const p = new URLSearchParams(window.location.search);
    for (const [k, v] of p.entries()) out[k] = v;
    return out;
}

/**
 * Обновляет URL без перезагрузки страницы.
 */
export function writeQuery(params) {
    const url = new URL(window.location.href);
    url.search = buildQuery(params);
    window.history.replaceState(null, "", url.toString());
}
