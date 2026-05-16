/**
 * Прокси URL изображений лотов через /api/media/image.
 * В БД хранятся ссылки на torgi.gov.ru / fedresurs — без прокси браузер
 * тянет их напрямую (медленно, без кэша на нашем сервере).
 */

export function lotImageUrl(url) {
    if (!url || typeof url !== "string") return url;
    const trimmed = url.trim();
    if (!trimmed) return trimmed;
    if (trimmed.startsWith("/api/media/")) return trimmed;
    if (trimmed.startsWith("data:")) return trimmed;
    return `/api/media/image?url=${encodeURIComponent(trimmed)}`;
}
