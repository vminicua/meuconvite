/*
 * Nuvem Doce — movimento do template (gerado).
 * Só acrescenta decoração e revelações; o convite funciona sem este script.
 */
(function () {
    "use strict";
    var body = document.body;
    if (!body || !body.classList.contains("inv--template-cha-bebe-nuvem-doce")) return;
    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var CFG = {"cover": [{"cls": "nd-cloud", "n": 2, "x": [5, 30], "y": [2, 12], "s": [0.8, 1.1], "dur": 16}, {"cls": "nd-dot", "n": 10, "x": [4, 60], "y": [4, 55], "s": [0.8, 1.6], "dur": 3}], "hero": [{"cls": "nd-star", "n": 9, "x": [4, 96], "y": [4, 60], "s": [0.6, 1.3], "dur": 4}, {"cls": "nd-dot", "n": 8, "x": [4, 96], "y": [6, 70], "s": [0.8, 1.5], "dur": 3}, {"cls": "nd-cloud", "n": 2, "x": [10, 90], "y": [60, 78], "s": [0.7, 0.9], "dur": 16}], "sections": [{"sel": ".theme-closing", "cls": "nd-star", "n": 5, "x": [6, 94], "y": [12, 88], "s": [0.6, 1.1], "dur": 4}], "reveal": ".theme-hero > :not(.t-layer), .theme-main > section, .theme-facts article, .inv-timeline__item, .inv-footer > *"};

    var seed = 7;
    function rand() { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; }

    function layer(host, cls) {
        if (!host) return null;
        var el = document.createElement("div");
        el.className = "t-layer " + cls;
        el.setAttribute("aria-hidden", "true");
        host.insertBefore(el, host.firstChild);
        return el;
    }

    function sprinkle(host, spec) {
        if (!host) return;
        var frag = document.createDocumentFragment();
        for (var i = 0; i < spec.n; i++) {
            var s = document.createElement("span");
            s.className = "t-deco " + spec.cls;
            s.setAttribute("aria-hidden", "true");
            var x = spec.x ? spec.x[0] + rand() * (spec.x[1] - spec.x[0]) : rand() * 100;
            var y = spec.y ? spec.y[0] + rand() * (spec.y[1] - spec.y[0]) : rand() * 100;
            s.style.setProperty("--x", x.toFixed(1) + "%");
            s.style.setProperty("--y", y.toFixed(1) + "%");
            s.style.setProperty("--s", (spec.s ? spec.s[0] + rand() * (spec.s[1] - spec.s[0]) : 1).toFixed(2));
            s.style.setProperty("--d", (-rand() * (spec.dur || 6)).toFixed(2) + "s");
            s.style.setProperty("--r", Math.round(rand() * 360) + "deg");
            s.style.setProperty("--i", String(i));
            frag.appendChild(s);
        }
        host.appendChild(frag);
    }

    var cover = document.getElementById("inv-cover");
    var main = document.getElementById("inv-main");
    var hero = main && main.querySelector(".theme-hero, .corp-hero");
    var coverScene = cover && (cover.querySelector("[data-theme-cinematic]") || layer(cover, "t-cover-layer"));
    var heroLayer = layer(hero, "t-hero-layer");

    (CFG.cover || []).forEach(function (spec) { sprinkle(coverScene, spec); });
    (CFG.hero || []).forEach(function (spec) { sprinkle(heroLayer, spec); });
    (CFG.sections || []).forEach(function (spec) {
        if (!main) return;
        main.querySelectorAll(spec.sel).forEach(function (section) {
            sprinkle(layer(section, "t-section-layer"), spec);
        });
    });

    if (reduced) return;

    /* Capa corporativa: o invitation.js faz o fade; aqui só se acrescenta a coreografia. */
    var opener = document.querySelector("[data-open-invitation]");
    if (opener && cover && !cover.classList.contains("theme-cover")) {
        opener.addEventListener("click", function () {
            cover.classList.add("t-leaving");
            if (main) main.classList.add("t-main-enter");
        });
    }

    /* Revelação ao scroll */
    if ("IntersectionObserver" in window && main) {
        var targets = main.querySelectorAll(CFG.reveal || "");
        if (targets.length) {
            body.classList.add("t-motion");
            var groups = new Map();
            targets.forEach(function (el) {
                var parent = el.parentElement;
                var index = groups.get(parent) || 0;
                groups.set(parent, index + 1);
                el.style.setProperty("--t-delay", Math.min(index * 0.09, 0.6).toFixed(2) + "s");
                el.classList.add("t-reveal");
            });
            var io = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (!entry.isIntersecting) return;
                    entry.target.classList.add("is-in");
                    io.unobserve(entry.target);
                });
            }, { threshold: 0.12, rootMargin: "0px 0px -5% 0px" });
            targets.forEach(function (el) { io.observe(el); });
        }
    }

    /* Parallax suave da arte no topo do convite */
    var viewport = document.querySelector("[data-invitation-viewport]");
    var pending = false;
    function paint() {
        pending = false;
        if (!hero || (main && main.hasAttribute("hidden"))) return;
        var rect = hero.getBoundingClientRect();
        var shift = Math.max(-260, Math.min(260, -rect.top * 0.28));
        hero.style.setProperty("--t-par", shift.toFixed(1));
    }
    function request() { if (!pending) { pending = true; window.requestAnimationFrame(paint); } }
    window.addEventListener("scroll", request, { passive: true });
    if (viewport) viewport.addEventListener("scroll", request, { passive: true });
    window.addEventListener("resize", request);
    request();
})();
