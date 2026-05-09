/**
 * Страница входа / регистрации с табами.
 * Поддерживает ?redirect=/path — после успешного входа переходит туда.
 */

import { renderHeader } from "../components/header.js";
import { renderFooter } from "../components/footer.js";
import {
    login,
    register,
    getCurrentUser,
    resolvePostLoginRedirect,
} from "../auth.js";
import { toast } from "../components/toast.js";
import { qs, readQuery } from "../utils.js";

async function boot() {
    await renderHeader("login");
    renderFooter();

    // Если уже залогинены — сразу уходим.
    const user = await getCurrentUser();
    if (user) {
        window.location.href = await pickDestination();
        return;
    }

    const tabs = document.querySelectorAll(".tab");
    const panels = {
        login: qs("#form-login"),
        register: qs("#form-register"),
    };

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            const t = tab.dataset.tab;
            tabs.forEach((b) => b.classList.toggle("active", b === tab));
            for (const [k, el] of Object.entries(panels)) {
                el.classList.toggle("hidden", k !== t);
            }
        });
    });

    panels.login.addEventListener("submit", async (e) => {
        e.preventDefault();
        clearErrors(panels.login);

        const email = panels.login.email.value.trim().toLowerCase();
        const password = panels.login.password.value;

        const errs = validate({ email, password });
        if (Object.keys(errs).length) {
            showErrors(panels.login, errs);
            return;
        }

        const btn = panels.login.querySelector('button[type="submit"]');
        btn.disabled = true;
        try {
            await login(email, password);
            toast.success("Добро пожаловать!");
            window.location.href = await pickDestination();
        } catch (err) {
            toast.fromApiError(err);
        } finally {
            btn.disabled = false;
        }
    });

    panels.register.addEventListener("submit", async (e) => {
        e.preventDefault();
        clearErrors(panels.register);

        const email = panels.register.email.value.trim().toLowerCase();
        const password = panels.register.password.value;
        const password2 = panels.register.password2.value;

        const errs = validate({ email, password });
        if (password !== password2) errs.password2 = "Пароли не совпадают";
        if (Object.keys(errs).length) {
            showErrors(panels.register, errs);
            return;
        }

        const btn = panels.register.querySelector('button[type="submit"]');
        btn.disabled = true;
        try {
            await register(email, password);
            await login(email, password);
            toast.success("Аккаунт создан");
            window.location.href = await pickDestination();
        } catch (err) {
            toast.fromApiError(err);
        } finally {
            btn.disabled = false;
        }
    });
}

function validate({ email, password }) {
    const e = {};
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        e.email = "Введите корректный email";
    }
    if (!password || password.length < 8) {
        e.password = "Минимум 8 символов";
    }
    return e;
}

function clearErrors(form) {
    form.querySelectorAll(".error-msg").forEach((el) => (el.textContent = ""));
    form.querySelectorAll(".input").forEach((el) => el.classList.remove("invalid"));
}

function showErrors(form, errs) {
    for (const [name, msg] of Object.entries(errs)) {
        const input = form.elements.namedItem(name);
        if (input) input.classList.add("invalid");
        const slot = form.querySelector(`[data-error-for="${name}"]`);
        if (slot) slot.textContent = msg;
    }
}

function getRedirect() {
    const r = readQuery().redirect;
    if (r && r.startsWith("/")) return r;
    return "/index.html";
}

/**
 * Если в URL пришёл явный ?redirect=… — уважаем его (возможно админ
 * ткнул внутреннюю ссылку и его выкинуло на логин). Иначе админ
 * уезжает в админку, обычный юзер — на главную.
 */
async function pickDestination() {
    const explicit = readQuery().redirect;
    if (explicit && explicit.startsWith("/")) return explicit;
    return await resolvePostLoginRedirect("/index.html");
}

boot();
