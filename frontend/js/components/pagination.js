/**
 * Пагинация. Рендерит набор кнопок в root на основе total/page/pageSize.
 * onChange(newPage) — вызывается при клике.
 */

export function renderPagination(root, { total, page, pageSize }, onChange) {
    root.innerHTML = "";
    const pages = Math.max(1, Math.ceil(total / pageSize));
    if (pages <= 1) return;

    const make = (label, p, { active = false, disabled = false, ellipsis = false } = {}) => {
        if (ellipsis) {
            const span = document.createElement("span");
            span.className = "ellipsis";
            span.textContent = "…";
            root.appendChild(span);
            return;
        }
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = label;
        if (active) btn.classList.add("active");
        if (disabled) btn.disabled = true;
        btn.addEventListener("click", () => {
            if (!disabled && !active) onChange(p);
        });
        root.appendChild(btn);
    };

    make("‹", page - 1, { disabled: page <= 1 });

    // Собираем набор номеров: 1, (page-1), page, (page+1), last, с многоточиями.
    const nums = new Set([1, pages, page, page - 1, page + 1]);
    const ordered = [...nums].filter((n) => n >= 1 && n <= pages).sort((a, b) => a - b);

    let prev = 0;
    for (const n of ordered) {
        if (n - prev > 1) make(null, null, { ellipsis: true });
        make(String(n), n, { active: n === page });
        prev = n;
    }

    make("›", page + 1, { disabled: page >= pages });
}
