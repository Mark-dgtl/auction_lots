/**
 * In-memory мок backend. Реализует все эндпоинты из CONTRACTS.md §2.
 *
 * Состояние:
 *   - user-данные (users, favorites, filters, settings) живут в localStorage —
 *     чтобы F5 не стирал всё подряд и демо было живее.
 *   - Лоты (неизменяемый каталог) — в памяти.
 *
 * Каждому "эндпоинту" соответствует запись в таблице маршрутов (см. ниже).
 * mockRouter(method, path) сопоставляет метод+путь → обработчик и возвращает
 * { status, body } — в точности как REST-ответ, чтобы api.js мог обработать
 * ошибки единообразно.
 */

import { config } from "./config.js";

const LS_KEY = "ag_mock_state_v1";

const DEFAULT_STATE = {
    users: [],
    favorites: {}, // { userId: [lotId, ...] }
    filters: {},   // { userId: [SavedFilter, ...] }
    settings: {},  // { userId: {digest_time, telegram_linked, tg_deep_link_token} }
    session: {
        accessToken: null,
        userId: null,
        refreshToken: null,
    },
    seqUser: 1,
    seqFilter: 1,
};

function loadState() {
    try {
        const raw = localStorage.getItem(LS_KEY);
        if (!raw) return structuredClone(DEFAULT_STATE);
        const parsed = JSON.parse(raw);
        return { ...structuredClone(DEFAULT_STATE), ...parsed };
    } catch {
        return structuredClone(DEFAULT_STATE);
    }
}

function saveState() {
    localStorage.setItem(LS_KEY, JSON.stringify(state));
}

const state = loadState();

// --------- Справочники ---------

const CATEGORIES = [
    { slug: "real_estate", name: "Недвижимость" },
    { slug: "vehicle", name: "Транспорт" },
    { slug: "equipment", name: "Оборудование" },
    { slug: "land", name: "Земельные участки" },
    { slug: "rights", name: "Права требования" },
    { slug: "securities", name: "Ценные бумаги" },
    { slug: "inventory", name: "ТМЦ и материалы" },
    { slug: "other", name: "Прочее" },
];

const REGIONS = [
    { code: "45", name: "Москва" },
    { code: "40", name: "Санкт-Петербург" },
    { code: "46", name: "Московская область" },
    { code: "41", name: "Ленинградская область" },
    { code: "66", name: "Свердловская область" },
    { code: "52", name: "Нижегородская область" },
    { code: "65", name: "Ростовская область" },
    { code: "36", name: "Краснодарский край" },
    { code: "71", name: "Челябинская область" },
    { code: "92", name: "Татарстан" },
    { code: "50", name: "Новосибирская область" },
    { code: "63", name: "Самарская область" },
];

// --------- Генерация лотов ---------

const LOT_TEMPLATES = {
    real_estate: [
        "Квартира {n} м² в центре",
        "Двухкомнатная квартира {n} м²",
        "Дом с участком {n} соток",
        "Апартаменты {n} м²",
        "Коммерческая недвижимость {n} м²",
    ],
    vehicle: [
        "Автомобиль Lada Granta {year}",
        "Kia Rio {year}",
        "Hyundai Solaris {year}",
        "Toyota Camry {year}",
        "Грузовой МАЗ {year}",
    ],
    equipment: [
        "Станок токарный 1К62",
        "Фрезерный станок 6Р82",
        "Компрессор винтовой {kw} кВт",
        "Линия упаковочная",
        "Сварочный аппарат",
    ],
    land: [
        "Земельный участок {n} соток ИЖС",
        "Участок сельхозназначения {n} га",
        "Участок промышленного назначения {n} соток",
    ],
    rights: [
        "Право требования по договору подряда",
        "Дебиторская задолженность {n} млн",
        "Права требования по кредиту",
    ],
    securities: [
        "Акции ПАО «Пример»",
        "Облигации корпоративные",
        "Доля в уставном капитале ООО",
    ],
    inventory: [
        "Партия металлопроката",
        "Офисная мебель (лот из {n} ед.)",
        "Строительные материалы",
    ],
    other: ["Имущественный комплекс", "Прочее имущество должника"],
};

const DESCRIPTIONS = [
    "Имущество должника, реализуется в рамках конкурсного производства. Осмотр по предварительной записи. Задаток — 10%.",
    "Предмет торгов находится в удовлетворительном состоянии. Документы в порядке, обременения отсутствуют.",
    "Объект выставлен повторно в связи с признанием первичных торгов несостоявшимися. Снижение стартовой цены.",
    "Продавец — арбитражный управляющий. Регистрация заявок на электронной площадке.",
    "Лот реализуется по открытой форме торгов. Шаг аукциона указан в извещении.",
];

function choose(arr, i) {
    return arr[i % arr.length];
}

function genLots() {
    const lots = [];
    let id = 1;
    const now = Date.now();
    const categories = Object.keys(LOT_TEMPLATES);

    for (let i = 0; i < 48; i++) {
        const category = choose(categories, i);
        const titleTpl = choose(LOT_TEMPLATES[category], i);
        const title = titleTpl
            .replace("{n}", String(35 + (i * 7) % 140))
            .replace("{year}", String(2012 + (i % 12)))
            .replace("{kw}", String(15 + (i % 10) * 5));

        const region = REGIONS[i % REGIONS.length];
        const basePrice = {
            real_estate: 2_500_000,
            vehicle: 350_000,
            equipment: 180_000,
            land: 800_000,
            rights: 1_200_000,
            securities: 500_000,
            inventory: 90_000,
            other: 250_000,
        }[category];
        const price = basePrice + (i * 137_000) % basePrice * 3;

        const daysAhead = 3 + (i * 4) % 60;
        const auctionDate = new Date(now + daysAhead * 24 * 3600 * 1000);
        const publishedAt = new Date(now - ((i * 37) % 30) * 24 * 3600 * 1000);

        // Картинки: placeholder-сервис с градиентом по id (не ходим наружу).
        const hue = (i * 37) % 360;
        const imgs = [
            makePlaceholder(hue, `Лот №${id}`),
            makePlaceholder((hue + 30) % 360, `Фото 2 · №${id}`),
            makePlaceholder((hue + 60) % 360, `Фото 3 · №${id}`),
        ];

        lots.push({
            id,
            source: i % 2 === 0 ? "efrsb" : "torgi_gov",
            source_lot_id: `M-${10000 + id}`,
            title,
            description: `${choose(DESCRIPTIONS, i)}\n\nКатегория: ${
                CATEGORIES.find((c) => c.slug === category)?.name
            }.\nРегион: ${region.name}.`,
            category,
            region_code: region.code,
            region_name: region.name,
            price: price.toFixed(2),
            price_step: (price * 0.05).toFixed(2),
            source_url: "https://example.com/lot/" + id,
            auction_date: auctionDate.toISOString(),
            published_at: publishedAt.toISOString(),
            updated_at: publishedAt.toISOString(),
            status: i % 9 === 0 ? "cancelled" : "active",
            images: imgs,
            thumbnail: imgs[0],
        });
        id++;
    }
    return lots;
}

function makePlaceholder(hue, label) {
    // Инлайновый SVG data-URI — не ходим во внешние сети.
    const bg1 = `hsl(${hue}, 35%, 82%)`;
    const bg2 = `hsl(${(hue + 40) % 360}, 40%, 70%)`;
    const svg = `
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 250'>
  <defs>
    <linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
      <stop offset='0' stop-color='${bg1}'/>
      <stop offset='1' stop-color='${bg2}'/>
    </linearGradient>
  </defs>
  <rect width='400' height='250' fill='url(#g)'/>
  <text x='50%' y='50%' text-anchor='middle' dominant-baseline='middle'
        fill='rgba(27,35,48,0.45)' font-family='sans-serif'
        font-size='18' font-weight='600'>${label}</text>
</svg>`.trim();
    return "data:image/svg+xml;utf8," + encodeURIComponent(svg);
}

const LOTS = genLots();

// --------- Вспомогательные ---------

function delay() {
    const { DELAY_MIN, DELAY_MAX } = config.MOCK;
    const ms = DELAY_MIN + Math.random() * (DELAY_MAX - DELAY_MIN);
    return new Promise((r) => setTimeout(r, ms));
}

function maybeFail(path) {
    if (config.MOCK.STRICT_NO_ERRORS) return false;
    // не сбоим авторизацию — иначе демо-вход утомит
    if (path.startsWith("/auth/") || path.startsWith("/meta/")) return false;
    return Math.floor(Math.random() * config.MOCK.ERROR_EVERY_N) === 0;
}

function ok(body) {
    return { status: body ? 200 : 204, body: body ?? null };
}
function err(status, code, message) {
    return { status, body: { error: { code, message } } };
}

function parseQuery(path) {
    const qIdx = path.indexOf("?");
    if (qIdx < 0) return { path, query: {} };
    const bare = path.slice(0, qIdx);
    const query = {};
    const qs = new URLSearchParams(path.slice(qIdx + 1));
    for (const [k, v] of qs.entries()) query[k] = v;
    return { path: bare, query };
}

function currentUser() {
    if (!state.session.userId) return null;
    return state.users.find((u) => u.id === state.session.userId) || null;
}

function requireAuth() {
    const u = currentUser();
    if (!u) return null;
    // Проверка "access_token" — просто что он есть в headers; api.js нам
    // все эти options прокидывает. В моке можно проще: флаг сессии.
    if (!state.session.accessToken) return null;
    return u;
}

function pickLotShort(lot, userId) {
    const favs = state.favorites[userId] || [];
    return {
        id: lot.id,
        source: lot.source,
        title: lot.title,
        category: lot.category,
        region_code: lot.region_code,
        region_name: lot.region_name,
        price: lot.price,
        auction_date: lot.auction_date,
        thumbnail: lot.thumbnail,
        is_favorite: userId ? favs.includes(lot.id) : false,
    };
}

function pickLotDetail(lot, userId) {
    return {
        ...pickLotShort(lot, userId),
        description: lot.description,
        price_step: lot.price_step,
        source_url: lot.source_url,
        images: lot.images,
        status: lot.status,
        published_at: lot.published_at,
        updated_at: lot.updated_at,
    };
}

// --------- Handlers ---------

async function hRegister(_m, _p, opts) {
    const body = opts.body || {};
    const email = String(body.email || "").trim().toLowerCase();
    const password = String(body.password || "");
    if (!email.includes("@")) {
        return err(422, "VALIDATION_ERROR", "Укажите корректный email");
    }
    if (password.length < 8) {
        return err(
            422,
            "VALIDATION_ERROR",
            "Пароль должен содержать минимум 8 символов",
        );
    }
    if (state.users.some((u) => u.email === email)) {
        return err(409, "CONFLICT", "Пользователь с таким email уже существует");
    }
    const user = {
        id: state.seqUser++,
        email,
        password,
        telegram_linked: false,
        digest_time: "09:00",
    };
    state.users.push(user);
    saveState();
    return ok({ id: user.id, email: user.email });
}

async function hLogin(_m, _p, opts) {
    const body = opts.body || {};
    const email = String(body.email || "").toLowerCase();
    const password = String(body.password || "");
    const user = state.users.find(
        (u) => u.email === email && u.password === password,
    );
    if (!user) {
        return err(401, "INVALID_CREDENTIALS", "Неверный email или пароль");
    }
    state.session.userId = user.id;
    state.session.accessToken = "mock_access_" + user.id + "_" + Date.now();
    state.session.refreshToken = "mock_refresh_" + user.id;
    saveState();
    return ok({
        access_token: state.session.accessToken,
        token_type: "bearer",
        expires_in: 900,
    });
}

async function hRefresh() {
    // Симулируем наличие cookie по факту того, что в state лежит refreshToken.
    if (!state.session.refreshToken || !state.session.userId) {
        return err(401, "UNAUTHORIZED", "Сессия истекла");
    }
    state.session.accessToken =
        "mock_access_" + state.session.userId + "_" + Date.now();
    saveState();
    return ok({
        access_token: state.session.accessToken,
        token_type: "bearer",
        expires_in: 900,
    });
}

async function hLogout() {
    state.session.userId = null;
    state.session.accessToken = null;
    state.session.refreshToken = null;
    saveState();
    return ok();
}

async function hMe() {
    const u = requireAuth();
    if (!u) return err(401, "UNAUTHORIZED", "Требуется авторизация");
    const s = state.settings[u.id] || {};
    return ok({
        id: u.id,
        email: u.email,
        telegram_linked: !!s.telegram_linked,
        digest_time: s.digest_time || u.digest_time || "09:00",
    });
}

async function hLotsList(_m, _p, opts) {
    const q = opts._query || {};
    const user = currentUser();
    const page = Math.max(1, parseInt(q.page || "1", 10));
    const pageSize = Math.min(100, Math.max(1, parseInt(q.page_size || "20", 10)));
    const query = (q.query || "").toLowerCase().trim();
    const category = q.category || "";
    const region = q.region || "";
    const priceFrom = q.price_from ? Number(q.price_from) : null;
    const priceTo = q.price_to ? Number(q.price_to) : null;
    const dateFrom = q.date_from ? new Date(q.date_from).getTime() : null;
    const dateTo = q.date_to ? new Date(q.date_to).getTime() : null;
    const sort = q.sort || "date_desc";

    let items = LOTS.slice();
    if (query) {
        items = items.filter(
            (l) =>
                l.title.toLowerCase().includes(query) ||
                (l.description || "").toLowerCase().includes(query),
        );
    }
    if (category) items = items.filter((l) => l.category === category);
    if (region) items = items.filter((l) => l.region_code === region);
    if (priceFrom != null) items = items.filter((l) => Number(l.price) >= priceFrom);
    if (priceTo != null) items = items.filter((l) => Number(l.price) <= priceTo);
    if (dateFrom != null) {
        items = items.filter(
            (l) => new Date(l.auction_date).getTime() >= dateFrom,
        );
    }
    if (dateTo != null) {
        items = items.filter(
            (l) => new Date(l.auction_date).getTime() <= dateTo + 24 * 3600 * 1000,
        );
    }

    if (sort === "price_asc") {
        items.sort((a, b) => Number(a.price) - Number(b.price));
    } else if (sort === "price_desc") {
        items.sort((a, b) => Number(b.price) - Number(a.price));
    } else {
        items.sort(
            (a, b) =>
                new Date(b.published_at).getTime() -
                new Date(a.published_at).getTime(),
        );
    }

    const total = items.length;
    const start = (page - 1) * pageSize;
    const pageItems = items
        .slice(start, start + pageSize)
        .map((l) => pickLotShort(l, user?.id));

    return ok({ items: pageItems, total, page, page_size: pageSize });
}

async function hLotDetail(_m, path) {
    const m = path.match(/^\/lots\/(\d+)$/);
    if (!m) return err(404, "NOT_FOUND", "Лот не найден");
    const id = Number(m[1]);
    const lot = LOTS.find((l) => l.id === id);
    if (!lot) return err(404, "NOT_FOUND", "Лот не найден");
    return ok(pickLotDetail(lot, currentUser()?.id));
}

function ensureFavorites(userId) {
    if (!state.favorites[userId]) state.favorites[userId] = [];
    return state.favorites[userId];
}

async function hFavoritesList() {
    const u = requireAuth();
    if (!u) return err(401, "UNAUTHORIZED", "Требуется авторизация");
    const favIds = ensureFavorites(u.id);
    const items = favIds
        .map((id) => LOTS.find((l) => l.id === id))
        .filter(Boolean)
        .map((l) => pickLotShort(l, u.id));
    return ok({ items, total: items.length });
}

async function hFavoriteAdd(_m, path) {
    const u = requireAuth();
    if (!u) return err(401, "UNAUTHORIZED", "Требуется авторизация");
    const id = Number(path.split("/").pop());
    if (!LOTS.some((l) => l.id === id)) return err(404, "NOT_FOUND", "Лот не найден");
    const favs = ensureFavorites(u.id);
    if (!favs.includes(id)) favs.push(id);
    saveState();
    return ok();
}

async function hFavoriteRemove(_m, path) {
    const u = requireAuth();
    if (!u) return err(401, "UNAUTHORIZED", "Требуется авторизация");
    const id = Number(path.split("/").pop());
    state.favorites[u.id] = ensureFavorites(u.id).filter((x) => x !== id);
    saveState();
    return ok();
}

function ensureFilters(userId) {
    if (!state.filters[userId]) state.filters[userId] = [];
    return state.filters[userId];
}

async function hFiltersList() {
    const u = requireAuth();
    if (!u) return err(401, "UNAUTHORIZED", "Требуется авторизация");
    return ok({ items: ensureFilters(u.id) });
}

async function hFilterCreate(_m, _p, opts) {
    const u = requireAuth();
    if (!u) return err(401, "UNAUTHORIZED", "Требуется авторизация");
    const body = opts.body || {};
    if (!body.name || typeof body.name !== "string") {
        return err(422, "VALIDATION_ERROR", "Укажите имя фильтра");
    }
    const item = {
        id: state.seqFilter++,
        name: body.name,
        filter: body.filter || {},
        notify_enabled: !!body.notify_enabled,
        created_at: new Date().toISOString(),
    };
    ensureFilters(u.id).push(item);
    saveState();
    return ok(item);
}

async function hFilterUpdate(_m, path, opts) {
    const u = requireAuth();
    if (!u) return err(401, "UNAUTHORIZED", "Требуется авторизация");
    const id = Number(path.split("/").pop());
    const list = ensureFilters(u.id);
    const found = list.find((f) => f.id === id);
    if (!found) return err(404, "NOT_FOUND", "Фильтр не найден");
    Object.assign(found, opts.body || {});
    saveState();
    return ok(found);
}

async function hFilterDelete(_m, path) {
    const u = requireAuth();
    if (!u) return err(401, "UNAUTHORIZED", "Требуется авторизация");
    const id = Number(path.split("/").pop());
    state.filters[u.id] = ensureFilters(u.id).filter((f) => f.id !== id);
    saveState();
    return ok();
}

async function hTelegramLink() {
    const u = requireAuth();
    if (!u) return err(401, "UNAUTHORIZED", "Требуется авторизация");
    const token = "tg_" + Math.random().toString(36).slice(2, 10);
    const settings = state.settings[u.id] || {};
    settings.tg_deep_link_token = token;
    state.settings[u.id] = settings;
    saveState();
    return ok({
        deep_link: `https://t.me/auction_aggregator_bot?start=${token}`,
        token,
        expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
    });
}

async function hTelegramUnlink() {
    const u = requireAuth();
    if (!u) return err(401, "UNAUTHORIZED", "Требуется авторизация");
    const settings = state.settings[u.id] || {};
    settings.telegram_linked = false;
    settings.tg_deep_link_token = null;
    state.settings[u.id] = settings;
    saveState();
    return ok();
}

async function hNotificationsGet() {
    const u = requireAuth();
    if (!u) return err(401, "UNAUTHORIZED", "Требуется авторизация");
    const s = state.settings[u.id] || {};
    return ok({
        digest_time: s.digest_time || "09:00",
        telegram_linked: !!s.telegram_linked,
    });
}

async function hNotificationsUpdate(_m, _p, opts) {
    const u = requireAuth();
    if (!u) return err(401, "UNAUTHORIZED", "Требуется авторизация");
    const body = opts.body || {};
    if (body.digest_time && !/^\d{2}:\d{2}$/.test(body.digest_time)) {
        return err(422, "VALIDATION_ERROR", "Неверный формат времени");
    }
    const s = state.settings[u.id] || {};
    if (body.digest_time) s.digest_time = body.digest_time;
    state.settings[u.id] = s;
    saveState();
    return ok({ digest_time: s.digest_time });
}

async function hNotificationsTest() {
    const u = requireAuth();
    if (!u) return err(401, "UNAUTHORIZED", "Требуется авторизация");
    const s = state.settings[u.id] || {};
    if (!s.telegram_linked) {
        return err(
            409,
            "TELEGRAM_NOT_LINKED",
            "Сначала привяжите Telegram в личном кабинете",
        );
    }
    return ok();
}

async function hMetaCategories() {
    return ok({ items: CATEGORIES });
}

async function hMetaRegions() {
    return ok({ items: REGIONS });
}

// --------- Роутер ---------

const ROUTES = [
    { m: "POST",   p: /^\/auth\/register$/, h: hRegister },
    { m: "POST",   p: /^\/auth\/login$/,    h: hLogin },
    { m: "POST",   p: /^\/auth\/refresh$/,  h: hRefresh },
    { m: "POST",   p: /^\/auth\/logout$/,   h: hLogout },
    { m: "GET",    p: /^\/me$/,             h: hMe },

    { m: "GET",    p: /^\/lots(\?.*)?$/,    h: hLotsList },
    { m: "GET",    p: /^\/lots\/\d+$/,      h: hLotDetail },

    { m: "GET",    p: /^\/favorites$/,       h: hFavoritesList },
    { m: "POST",   p: /^\/favorites\/\d+$/,  h: hFavoriteAdd },
    { m: "DELETE", p: /^\/favorites\/\d+$/,  h: hFavoriteRemove },

    { m: "GET",    p: /^\/filters$/,         h: hFiltersList },
    { m: "POST",   p: /^\/filters$/,         h: hFilterCreate },
    { m: "PUT",    p: /^\/filters\/\d+$/,    h: hFilterUpdate },
    { m: "DELETE", p: /^\/filters\/\d+$/,    h: hFilterDelete },

    { m: "POST",   p: /^\/telegram\/link$/,   h: hTelegramLink },
    { m: "POST",   p: /^\/telegram\/unlink$/, h: hTelegramUnlink },

    { m: "GET",    p: /^\/notifications\/settings$/, h: hNotificationsGet },
    { m: "PUT",    p: /^\/notifications\/settings$/, h: hNotificationsUpdate },
    { m: "POST",   p: /^\/notifications\/test$/,     h: hNotificationsTest },

    { m: "GET",    p: /^\/meta\/categories$/, h: hMetaCategories },
    { m: "GET",    p: /^\/meta\/regions$/,    h: hMetaRegions },
];

/**
 * Главный диспетчер мока. api.js передаёт сюда method+path (без base URL),
 * path может содержать query-string.
 *
 * @returns {Promise<{status:number, body:any}>}
 */
export async function mockRouter(method, rawPath, options = {}) {
    await delay();

    const { path, query } = parseQuery(rawPath);

    if (maybeFail(path)) {
        return err(500, "INTERNAL_ERROR", "Мок: случайный сбой сети");
    }

    for (const route of ROUTES) {
        if (route.m !== method) continue;
        const toTest = route.p.source.includes("?") ? rawPath : path;
        if (!route.p.test(toTest)) continue;
        try {
            return await route.h(method, path, { ...options, _query: query });
        } catch (e) {
            // Защита от багов в хэндлере — отдаём 500, как настоящий сервер.
            console.error("[mock] handler error", e);
            return err(500, "INTERNAL_ERROR", "Мок: ошибка обработки");
        }
    }
    return err(404, "NOT_FOUND", `Маршрут ${method} ${path} не найден (мок)`);
}

// Утилита для других модулей фронта: узнать, залогинены ли мы (удобно в header).
export function mockSession() {
    return {
        accessToken: state.session.accessToken,
        userId: state.session.userId,
    };
}
