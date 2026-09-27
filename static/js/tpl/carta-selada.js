/*
 * Carta Selada — acabamento e movimento próprios deste template.
 *
 * Só decora: coloca as peças da camada decorativa (brasão, aba com lacre
 * dourado, poeira dourada), revela as secções ao fazer scroll e dá à abertura
 * da capa um lacre que se parte antes de invitation.js mostrar o convite.
 * Sem este ficheiro o convite continua completo e legível.
 */
(function () {
    "use strict";

    var body = document.body;
    if (!body || !body.classList.contains("inv--template-carta-selada")) return;

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
    var flap = piece("flap");
    var dust = piece("dust");
    var burst = piece("burst");

    if (hero) {
        if (crest) hero.insertBefore(crest.cloneNode(true), hero.firstChild);
        var names = hero.querySelector(".inv-hero__names");
        if (flap && names) names.insertAdjacentElement("afterend", flap.cloneNode(true));
        body.classList.add("tpl-cs-dressed");
    }
    if (cover) {
        var paper = cover.querySelector(".inv-cover__paper");
        if (crest && paper) paper.insertBefore(crest, paper.firstChild);
        if (dust && !reduced) cover.appendChild(dust);
        if (burst) cover.appendChild(burst);
        cover.classList.add("tpl-cs-cover");
    }
    if (decor) decor.remove();

    /* --- Ícones do programa ------------------------------------------ */
    document.querySelectorAll(".inv-timeline__item").forEach(function (item, index) {
        var icons = ["rings", "toast", "dinner", "music"];
        item.setAttribute("data-tpl-icon", icons[index] || "heart");
    });

    if (reduced) return;
    body.classList.add("tpl-motion");

    /* --- Abertura: o lacre parte-se, a aba abre, depois o convite ------ */
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
            }, 980);
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

    /* --- Segundos que "respiram" ---------------------------------------- */
    var seconds = document.querySelector("[data-countdown] [data-unit=seconds]");
    if (seconds && "MutationObserver" in window) {
        new MutationObserver(function () {
            seconds.classList.remove("tpl-tick");
            void seconds.offsetWidth;
            seconds.classList.add("tpl-tick");
        }).observe(seconds, { childList: true, characterData: true, subtree: true });
    }

    /* --- Parallax suave da renda do topo -------------------------------- */
    if (hero) {
        var pending = false;
        var paint = function () {
            pending = false;
            var rect = hero.getBoundingClientRect();
            var top = viewport && viewport.scrollHeight > viewport.clientHeight + 1
                && window.getComputedStyle(viewport).overflowY !== "visible"
                ? viewport.getBoundingClientRect().top : 0;
            var offset = Math.max(-400, Math.min(400, top - rect.top));
            hero.style.setProperty("--tpl-par", offset.toFixed(1));
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
