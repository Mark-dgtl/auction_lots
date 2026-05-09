/**
 * Компонент панели фильтров. Инициализируется из меты (/api/meta/categories, /regions)
 * и вызывает onChange(filters) на submit / reset.
 *
 * filters = {
 *   query, category, region, price_from, price_to, date_from, date_to
 * }
 */

import { api } from "../api.js";
import { escapeHtml } from "../utils.js";

let metaPromise = null;
async function loadMeta() {
    if (!metaPromise) {
        metaPromise = Promise.all([
            api.get("/meta/categories"),
            api.get("/meta/regions"),
        ]).then(([cats, regs]) => ({
            categories: cats.items || [],
            regions: regs.items || [],
        }));
    }
    return metaPromise;
}

/**
 * Монтирует фильтры в переданный контейнер.
 * @param {HTMLElement} root
 * @param {object} initial — начальные значения
 * @param {(filters:object)=>void} onChange
 * @param {{showQuery?:boolean, showDate?:boolean, onSave?:()=>void}} [opts]
 */
export async function mountFilters(root, initial, onChange, opts = {}) {
    const { showQuery = true, showDate = true, onSave } = opts;
    root.innerHTML = `<div class="loader-row"><span class="spinner"></span></div>`;

    const meta = await loadMeta();

    root.innerHTML = `
        <h3>Фильтры</h3>
        <form class="filters-form" novalidate>
            <div class="filters-grid">
                ${
                    showQuery
                        ? `
                <div class="field">
                    <label for="f-query">Поиск</label>
                    <input id="f-query" name="query" class="input" type="search"
                           placeholder="Название, описание..." />
                </div>`
                        : ""
                }
                <div class="field">
                    <label for="f-category">Категория</label>
                    <select id="f-category" name="category" class="select">
                        <option value="">Все</option>
                        ${meta.categories
                            .map(
                                (c) =>
                                    `<option value="${escapeHtml(c.slug)}">${escapeHtml(c.name)}</option>`,
                            )
                            .join("")}
                    </select>
                </div>
                <div class="field">
                    <label for="f-region">Регион</label>
                    <select id="f-region" name="region" class="select">
                        <option value="">Все</option>
                        ${meta.regions
                            .map(
                                (r) =>
                                    `<option value="${escapeHtml(r.code)}">${escapeHtml(r.name)}</option>`,
                            )
                            .join("")}
                    </select>
                </div>
                <div class="field">
                    <label>Цена, ₽</label>
                    <div class="price-range">
                        <input name="price_from" class="input" type="number"
                               min="0" step="1000" placeholder="от" />
                        <input name="price_to" class="input" type="number"
                               min="0" step="1000" placeholder="до" />
                    </div>
                </div>
                ${
                    showDate
                        ? `
                <div class="field">
                    <label for="f-date-from">Торги с</label>
                    <input id="f-date-from" name="date_from" class="input" type="date" />
                </div>
                <div class="field">
                    <label for="f-date-to">Торги по</label>
                    <input id="f-date-to" name="date_to" class="input" type="date" />
                </div>`
                        : ""
                }
            </div>

            <div class="filters-actions">
                <button type="submit" class="btn btn-primary">Применить</button>
                <button type="button" class="btn btn-secondary" data-act="reset">
                    Сбросить
                </button>
                ${
                    onSave
                        ? `<button type="button" class="btn btn-ghost" data-act="save">
                              Сохранить фильтр
                           </button>`
                        : ""
                }
            </div>
        </form>
    `;

    const form = root.querySelector("form");
    applyValuesToForm(form, initial || {});

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        onChange(readValuesFromForm(form));
    });

    form.querySelector('[data-act="reset"]').addEventListener("click", () => {
        form.reset();
        onChange({});
    });

    const saveBtn = form.querySelector('[data-act="save"]');
    if (saveBtn && onSave) {
        saveBtn.addEventListener("click", () => {
            onSave(readValuesFromForm(form));
        });
    }

    return {
        getValues: () => readValuesFromForm(form),
        setValues: (vals) => applyValuesToForm(form, vals || {}),
    };
}

function readValuesFromForm(form) {
    const fd = new FormData(form);
    const out = {};
    for (const [k, v] of fd.entries()) {
        const s = String(v).trim();
        if (s) out[k] = s;
    }
    return out;
}

function applyValuesToForm(form, vals) {
    for (const name of [
        "query",
        "category",
        "region",
        "price_from",
        "price_to",
        "date_from",
        "date_to",
    ]) {
        const input = form.elements.namedItem(name);
        if (input) input.value = vals[name] != null ? String(vals[name]) : "";
    }
}
