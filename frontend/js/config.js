/**
 * Конфигурация фронтенда.
 *
 * Режим работы:
 *   - Дефолт — реальный API через nginx-прокси на `/api` (M2).
 *   - Для отладки/демо без бэка в консоли браузера:
 *       localStorage.use_mock = "true";  location.reload();
 *     Вернуться обратно:
 *       localStorage.removeItem("use_mock"); location.reload();
 *
 * Значение читается один раз при загрузке модуля: меняя localStorage
 * в devtools, страницу нужно перезагрузить — это сделано специально,
 * чтобы режим не плавал между запросами в рамках одной сессии.
 */

function readMockFlag() {
    try {
        const v = localStorage.getItem("use_mock");
        if (v == null) return false;
        return v === "true" || v === "1";
    } catch {
        return false;
    }
}

export const config = {
    API_BASE_URL: "/api",
    USE_MOCK: readMockFlag(),

    // Настройки мока (актуальны только при USE_MOCK=true)
    MOCK: {
        DELAY_MIN: 200,
        DELAY_MAX: 500,
        // 1 из N ответов — 500-ошибка для проверки error-state UI
        ERROR_EVERY_N: 20,
        // Жёсткий режим: не ошибаемся — удобно на демо
        STRICT_NO_ERRORS: false,
    },

    // Локаль / формат
    LOCALE: "ru-RU",
    CURRENCY: "RUB",
    TZ: "Europe/Moscow",
};
