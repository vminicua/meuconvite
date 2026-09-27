/*
 * Envelope Botânico — acabamento e movimento próprios deste template.
 *
 * Só decora: coloca a coroa de folhas com o monograma, faz cair algumas
 * folhas na capa, abre a capa afastando a folhagem e revela as secções ao
 * fazer scroll. Sem este ficheiro o convite continua completo e legível.
 */
(function () {
    "use strict";

    var body = document.body;
    if (!body || !body.classList.contains("inv--template-envelope-botanico")) return;

    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var decor = document.querySelector("[data-tpl-decor]");
    var cover = document.getElementById("inv-cover");
    var main = document.getElementById("inv-main");
    var hero = main && main.querySelector(".inv-hero");
    var viewport = document.querySelector("[data-invitation-viewport]");

    function piece(name) {
        return decor ? decor.querySelector('[data-tpl-piece="' + name + '"]') : null;
    }

    /* --- Peças decorativas ------------------------------------------- */
    var wreath = piece("wreath");
    var fall = piece("fall");
    if (hero && wreath) {
        hero.insertBefore(wreath.cloneNode(true), hero.firstChild);
        body.classList.add("tpl-eb-dressed");
    }
    if (cover) {
        var paper = cover.querySelector(".inv-cover__paper");
        var eyebrow = paper && paper.querySelector(".inv-cover__eyebrow");
        if (wreath && paper) paper.insertBefore(wreath, eyebrow || paper.firstChild);
        if (fall && !reduced) cover.appendChild(fall);
    }
    if (decor) decor.remove();

    document.querySelectorAll(".inv-timeline__item").forEach(function (item, index) {
        var icons = ["rings", "toast", "dinner", "music"];
        item.setAttribute("data-tpl-icon", icons[index] || "heart");
    });

    if (reduced) return;
    body.classList.add("tpl-motion");

    /* --- Abertura: a folhagem afasta-se e o papel sobe ------------------ */
    if (cover && main) {
        document.addEventListener("click", function (event) {
            var button = event.target.closest && event.target.closest("[data-open-invitation]");
            if (!button || button.getAttribute("data-tpl-go") === "1") return;
            event.preventDefault();
            event.stopPropagation();
            if (cover.classList.contains("tpl-opening")) return;
            cover.classList.add("tpl-opening");
            window.setTimeout(function () {
                button.setAttribute("data-tpl-go", "1");
                main.classList.add("tpl-enter");
                button.click();
            }, 900);
        }, true);
    } else if (main) {
        main.classList.add("tpl-enter");
    }

    /* --- Revelação ao scroll ----------------------------------------- */
    var targets = [];
    if (main) {
        main.querySelectorAll(":scope > .inv-section, .inv-timeline__item, .inv-qr__card, .inv-footer, .inv-story__quote, .inv-gallery-teaser__stack")
            .forEach(function (el) { el.classList.add("tpl-reveal"); targets.push(el); });
    }
    if ("IntersectionObserver" in window) {
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add("is-in");
                observer.unobserve(entry.target);
            });
        }, { threshold: 0.14, rootMargin: "0px 0px -8% 0px" });
        targets.forEach(function (el) { observer.observe(el); });
    } else {
        targets.forEach(function (el) { el.classList.add("is-in"); });
    }

    var seconds = document.querySelector("[data-countdown] [data-unit=seconds]");
    if (seconds && "MutationObserver" in window) {
        new MutationObserver(function () {
            seconds.classList.remove("tpl-tick");
            void seconds.offsetWidth;
            seconds.classList.add("tpl-tick");
        }).observe(seconds, { childList: true, characterData: true, subtree: true });
    }

    /* --- Parallax suave da folhagem ------------------------------------- */
    if (main) {
        var pending = false;
        var paint = function () {
            pending = false;
            var useViewport = viewport && viewport.scrollHeight > viewport.clientHeight + 1
                && window.getComputedStyle(viewport).overflowY !== "visible";
            var top = useViewport ? viewport.getBoundingClientRect().top : 0;
            var offset = Math.max(-600, Math.min(600, top - main.getBoundingClientRect().top));
            main.style.setProperty("--tpl-par", offset.toFixed(1));
        };
        var request = function () {
            if (pending) return;
            pending = true;
            window.requestAnimationFrame(paint);
        };
        window.addEventListener("scroll", request, { passive: true });
        if (viewport) viewport.addEventListener("scroll", request, { passive: true });
        request();
    }
})();
