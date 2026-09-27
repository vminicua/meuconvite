/*
 * Capulana Moçambicana — acabamento e movimento próprios deste template.
 *
 * Só decora: coloca o brasão com o monograma e os brilhos, abre a capa como
 * um cartão que se levanta e revela as secções ao fazer scroll.
 * Sem este ficheiro o convite continua completo e legível.
 */
(function () {
    "use strict";

    var CODE = "capulana";
    var OPEN_DELAY = 900;

    var body = document.body;
    if (!body || !body.classList.contains("inv--template-" + CODE)) return;

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
    var crest = piece("crest");
    var sparkle = piece("sparkle");
    var corners = piece("corners");
    if (hero && crest) {
        hero.insertBefore(crest.cloneNode(true), hero.firstChild);
        body.classList.add("tpl-dressed");
    }
    if (main && corners) main.appendChild(corners.cloneNode(true));
    if (cover) {
        var paper = cover.querySelector(".inv-cover__paper");
        if (crest && paper) paper.insertBefore(crest, paper.firstChild);
        if (sparkle && !reduced) cover.appendChild(sparkle);
        if (corners) cover.appendChild(corners);
    }
    if (decor) decor.remove();

    document.querySelectorAll(".inv-timeline__item").forEach(function (item, index) {
        var icons = ["rings", "toast", "dinner", "music"];
        item.setAttribute("data-tpl-icon", icons[index] || "heart");
    });

    if (reduced) return;
    body.classList.add("tpl-motion");

    /* --- Abertura -------------------------------------------------------- */
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
            }, OPEN_DELAY);
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

    /* --- Parallax suave do brasão ------------------------------------ */
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
