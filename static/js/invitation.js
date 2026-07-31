/*
 * Página do convite: abertura da capa e contagem regressiva.
 *
 * Sem JavaScript o convite continua legível — a capa é revelada e o
 * conteúdo aparece na mesma.
 */
(function () {
    "use strict";

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    /* --- Abertura da capa -------------------------------------------- */
    const cover = document.getElementById("inv-cover");
    const main = document.getElementById("inv-main");
    const opener = document.querySelector("[data-open-invitation]");

    if (main && main.hasAttribute("hidden") && !opener) {
        // Se o botão não existir por alguma razão, mostrar o convite.
        main.removeAttribute("hidden");
    }

    if (cover && main && opener) {
        opener.addEventListener("click", function () {
            main.removeAttribute("hidden");
            if (reducedMotion) {
                cover.remove();
                window.scrollTo(0, 0);
                return;
            }
            cover.style.transition = "opacity .5s ease, transform .5s ease";
            cover.style.opacity = "0";
            cover.style.transform = "scale(1.03)";
            window.setTimeout(function () {
                cover.remove();
                main.scrollIntoView({ behavior: "smooth", block: "start" });
            }, 480);
        });
    }

    /* --- Contagem regressiva ------------------------------------------ */
    const countdown = document.querySelector("[data-countdown]");
    if (!countdown) {
        return;
    }

    const target = new Date(countdown.dataset.countdown).getTime();
    if (Number.isNaN(target)) {
        return;
    }

    const cells = {
        days: countdown.querySelector("[data-unit=days]"),
        hours: countdown.querySelector("[data-unit=hours]"),
        minutes: countdown.querySelector("[data-unit=minutes]"),
        seconds: countdown.querySelector("[data-unit=seconds]")
    };

    function pad(value) {
        return String(value).padStart(2, "0");
    }

    function tick() {
        const remaining = target - Date.now();
        if (remaining <= 0) {
            countdown.classList.add("is-done");
            Object.values(cells).forEach(function (cell) {
                if (cell) {
                    cell.textContent = "0";
                }
            });
            window.clearInterval(timer);
            return;
        }

        const seconds = Math.floor(remaining / 1000);
        if (cells.days) cells.days.textContent = Math.floor(seconds / 86400);
        if (cells.hours) cells.hours.textContent = pad(Math.floor(seconds / 3600) % 24);
        if (cells.minutes) cells.minutes.textContent = pad(Math.floor(seconds / 60) % 60);
        if (cells.seconds) cells.seconds.textContent = pad(seconds % 60);
    }

    tick();
    const timer = window.setInterval(tick, 1000);
})();
