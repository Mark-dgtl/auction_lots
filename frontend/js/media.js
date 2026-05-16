/**
 * URL изображений лотов: статический WebP-кэш или API (fallback).
 */

export function lotFeedThumbUrl(lot) {
    if (lot?.thumbnail) return lot.thumbnail;
    if (lot?.thumbnail_source) return lotImageUrl(lot.thumbnail_source, "thumb");
    return null;
}

export function lotImageUrl(url, variant = "thumb") {
    if (!url || typeof url !== "string") return url;
    const trimmed = url.trim();
    if (!trimmed) return trimmed;
    if (trimmed.startsWith("/")) return trimmed;
    if (trimmed.startsWith("data:")) return trimmed;
    return `/api/media/image?url=${encodeURIComponent(trimmed)}&variant=${variant}`;
}

/** Fallback, если статический /media/cache/... ещё не прогрет. */
export function lotImageApiFallback(remoteUrl, variant = "thumb") {
    if (!remoteUrl) return null;
    return lotImageUrl(remoteUrl, variant);
}
