/*
 * Página do convite: abertura da capa e contagem regressiva.
 *
 * Sem JavaScript o convite continua legível — a capa é revelada e o
 * conteúdo aparece na mesma.
 */
(function () {
    "use strict";

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    /* A Carta Selada apresenta-se primeiro como um envelope físico. A cena é
       curta, automática e removida do DOM quando termina. */
    const openingIntro = document.querySelector("[data-opening-intro]");
    if (openingIntro) {
        if (reducedMotion) {
            openingIntro.remove();
        } else {
            openingIntro.classList.add("is-opening");
            window.setTimeout(function () {
                openingIntro.classList.add("is-complete");
            }, 3200);
            window.setTimeout(function () {
                openingIntro.remove();
            }, 3950);
        }
    }

    document.querySelectorAll("[data-inv-flash]").forEach(function (flash) {
        const rawKind = (flash.dataset.kind || "info").split(" ")[0];
        const kind = rawKind === "danger" ? "error" : rawKind;
        if (window.Swal) window.Swal.fire({
            toast: true, position: "top-end", icon: kind,
            title: flash.dataset.message, showConfirmButton: false, timer: 4200
        });
    });

    document.querySelectorAll("[data-dialog-open]").forEach(function (button) {
        button.addEventListener("click", function () {
            const dialog = document.getElementById(button.dataset.dialogOpen);
            if (dialog && typeof dialog.showModal === "function") dialog.showModal();
        });
    });
    document.querySelectorAll("[data-dialog-close]").forEach(function (button) {
        button.addEventListener("click", function () { button.closest("dialog").close(); });
    });
    document.querySelectorAll(".inv-dialog").forEach(function (dialog) {
        dialog.addEventListener("click", function (event) {
            if (event.target === dialog) dialog.close();
        });
    });

    const musicPlayer = document.querySelector("[data-music-player]");
    let startMusic = function () {};
    if (musicPlayer) {
        const audio = musicPlayer.querySelector("[data-music-audio]");
        const toggle = musicPlayer.querySelector("[data-music-toggle]");
        startMusic = function () {
            if (!audio.paused) return;
            audio.play().then(function () {
                musicPlayer.classList.add("is-playing");
                toggle.querySelector("span").textContent = "Pausar";
            }).catch(function () {});
        };
        toggle.addEventListener("click", function () {
            if (audio.paused) {
                startMusic();
            } else {
                audio.pause();
                musicPlayer.classList.remove("is-playing");
                toggle.querySelector("span").textContent = "Ouvir";
            }
        });

        // Tenta iniciar assim que a página abre. Safari, Chrome e Firefox
        // podem bloquear áudio com som até existir a primeira interação;
        // nesse caso retomamos no primeiro toque/tecla, sem exigir o ícone.
        startMusic();
        ["pointerdown", "keydown", "touchstart"].forEach(function (eventName) {
            document.addEventListener(eventName, startMusic, { once: true, passive: true });
        });
    }

    /* --- Abertura da capa -------------------------------------------- */
    const cover = document.getElementById("inv-cover");
    const main = document.getElementById("inv-main");
    const opener = document.querySelector("[data-open-invitation]");

    if (main && main.hasAttribute("hidden") && !opener) {
        // Se o botão não existir por alguma razão, mostrar o convite.
        main.removeAttribute("hidden");
        document.body.classList.remove("inv--cover-pending");
    }

    if (cover && main && opener) {
        opener.addEventListener("click", function () {
            startMusic();
            main.removeAttribute("hidden");
            if (reducedMotion) {
                cover.remove();
                document.body.classList.remove("inv--cover-pending");
                window.scrollTo(0, 0);
                return;
            }
            cover.style.transition = "opacity .5s ease, transform .5s ease";
            cover.style.opacity = "0";
            cover.style.transform = "scale(1.03)";
            window.setTimeout(function () {
                cover.remove();
                document.body.classList.remove("inv--cover-pending");
                main.scrollIntoView({ behavior: "smooth", block: "start" });
            }, 480);
        });
    }

    /* --- Contagem regressiva ------------------------------------------ */
    const countdown = document.querySelector("[data-countdown]");
    if (!countdown) return;

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
