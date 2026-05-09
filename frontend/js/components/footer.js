/**
 * Подвал в стиле многосекционного лендинга (как flowcub.com).
 */

export function renderFooter() {
    const existing = document.querySelector(".site-footer");
    if (existing) existing.remove();

    const footer = document.createElement("footer");
    footer.className = "site-footer";
    const year = new Date().getFullYear();
    footer.innerHTML = `
        <div class="container">
            <div class="site-footer__grid">
                <div>
                    <div class="site-footer__brand">Агрегатор торгов</div>
                    <p class="site-footer__lead">Курсовая работа. Студент Крапивин Марк, группа ЭВТ-24-1б</p>
                </div>
                <div class="site-footer__col">
                    <h4>Навигация</h4>
                    <ul>
                        <li><a href="/index.html">Главная</a></li>
                        <li><a href="/search.html">Поиск</a></li>
                        <li><a href="/login.html">Вход</a></li>
                    </ul>
                </div>
                <div class="site-footer__col">
                    <h4>Кабинет</h4>
                    <ul>
                        <li><a href="/cabinet.html">Избранное</a></li>
                        <li><a href="/notifications.html">Уведомления</a></li>
                    </ul>
                </div>
            </div>
            <div class="site-footer__bottom">
                <span>© ${year} Агрегатор торгов · Курсовая работа</span>
                <span>Стек: FastAPI · PostgreSQL · aiogram · HTML&CSS3&JS</span>
            </div>
        </div>
    `;
    document.body.appendChild(footer);
}
