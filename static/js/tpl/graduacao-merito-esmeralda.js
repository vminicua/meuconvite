/*
 * Mérito Esmeralda — movimento do tema (revelações ao scroll, partículas, abertura).
 * Só decorativo: sem este ficheiro o convite continua completo.
 */
(function () {
    "use strict";

    var CFG = {"ambient": {"type": "star", "size": [0.3, 0.75], "duration": [3, 7], "count": [12, 18], "colors": ["#e8cd84", "#f1dc9c"], "opacity": [0.4, 0.9]}, "cover": {"type": "star", "size": [0.35, 0.9], "duration": [3, 6], "count": [12, 16], "colors": ["#f1dc9c", "#e8cd84", "#ffffff"], "opacity": [0.6, 1]}, "burst": {"type": "leaf", "count": 22, "size": [0.6, 1.1], "distance": [90, 260], "lift": 60}, "sectionReveal": ["", "zoom"], "code": "graduacao-merito-esmeralda"};
    var body = document.body;
    if (!body || !body.classList.contains("inv--template-" + CFG.code)) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    var main = document.getElementById("inv-main");
    var cover = document.getElementById("inv-cover");
    var viewport = document.querySelector("[data-invitation-viewport]");

    function rand(min, max) { return min + Math.random() * (max - min); }
    function pick(list) { return list[Math.floor(Math.random() * list.length)]; }

    function particle(parent, cls, vars) {
        var el = document.createElement("i");
        el.className = cls;
        el.setAttribute("aria-hidden", "true");
        Object.keys(vars).forEach(function (key) { el.style.setProperty("--" + key, vars[key]); });
        parent.appendChild(el);
        return el;
    }

    function scatter(parent, spec, count) {
        for (var i = 0; i < count; i += 1) {
            particle(parent, "tpl-p tpl-p--" + spec.type + (spec.variants ? " tpl-v" + (i % spec.variants) : ""), {
                x: rand(spec.x ? spec.x[0] : 0, spec.x ? spec.x[1] : 100).toFixed(1) + "%",
                y: rand(spec.y ? spec.y[0] : 0, spec.y ? spec.y[1] : 100).toFixed(1) + "%",
                s: rand(spec.size[0], spec.size[1]).toFixed(2) + "rem",
                d: (-rand(0, spec.duration[1])).toFixed(2) + "s",
                t: rand(spec.duration[0], spec.duration[1]).toFixed(2) + "s",
                r: Math.round(rand(-40, 40)) + "deg",
                c: spec.colors ? pick(spec.colors) : "currentColor",
                o: rand(spec.opacity ? spec.opacity[0] : .5, spec.opacity ? spec.opacity[1] : 1).toFixed(2)
            });
        }
    }

    /* 1. Ambiente no fundo do convite e na capa */
    var ambient = document.querySelector("[data-tpl-ambient]");
    var small = window.innerWidth < 480;
    if (ambient && CFG.ambient) scatter(ambient, CFG.ambient, small ? CFG.ambient.count[0] : CFG.ambient.count[1]);
    var scene = cover && cover.querySelector(".theme-cinematic-scene");
    if (scene && CFG.cover) {
        (Array.isArray(CFG.cover) ? CFG.cover : [CFG.cover]).forEach(function (spec) {
            scatter(scene, spec, small ? spec.count[0] : spec.count[1]);
        });
    }

    /* 2. Explosão na abertura */
    var opener = document.querySelector("[data-open-invitation]");
    if (opener && cover && CFG.burst) {
        opener.addEventListener("click", function () {
            var rect = cover.getBoundingClientRect();
            var b = opener.getBoundingClientRect();
            var by = ((b.top + b.height / 2 - rect.top) / Math.max(rect.height, 1) * 100).toFixed(1) + "%";
            var spec = CFG.burst;
            for (var i = 0; i < spec.count; i += 1) {
                var angle = rand(spec.spread ? spec.spread[0] : 0, spec.spread ? spec.spread[1] : 360) * Math.PI / 180;
                var dist = rand(spec.distance[0], spec.distance[1]);
                particle(cover, "tpl-burst tpl-burst--" + spec.type + (spec.variants ? " tpl-v" + (i % spec.variants) : ""), {
                    by: by,
                    dx: (Math.cos(angle) * dist).toFixed(0) + "px",
                    dy: (Math.sin(angle) * dist - (spec.lift || 0)).toFixed(0) + "px",
                    s: rand(spec.size[0], spec.size[1]).toFixed(2) + "rem",
                    d: rand(0, .18).toFixed(2) + "s",
                    r: Math.round(rand(-540, 540)) + "deg",
                    c: spec.colors ? pick(spec.colors) : "currentColor"
                });
            }
        });
    }

    /* 3. Revelações ao scroll */
    if (!main || !("IntersectionObserver" in window)) return;
    body.classList.add("tpl-motion");

    function mark(el, kind, delay) {
        if (!el || el.hasAttribute("data-tpl-reveal")) return;
        el.setAttribute("data-tpl-reveal", kind || "");
        if (delay) el.style.setProperty("--tpl-d", delay.toFixed(2) + "s");
    }
    var hero = main.querySelector(".theme-hero");
    if (hero) Array.prototype.forEach.call(hero.children, function (child, index) {
        mark(child, index === 1 ? "zoom" : "", .12 + index * .12);
    });
    main.querySelectorAll(":scope > .theme-section, :scope > .inv-section, :scope > .inv-footer").forEach(function (section, index) {
        mark(section, CFG.sectionReveal ? CFG.sectionReveal[index % CFG.sectionReveal.length] : "", 0);
    });
    main.querySelectorAll(".inv-timeline__item").forEach(function (item, index) { mark(item, "left", .15 + index * .14); });
    main.querySelectorAll(".theme-facts article").forEach(function (item, index) { mark(item, "zoom", .1 + index * .08); });
    main.querySelectorAll(".inv-gallery-teaser__stack span").forEach(function (item, index) { mark(item, "zoom", .15 + index * .12); });

    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (!entry.isIntersecting) return;
            entry.target.classList.add("is-in");
            observer.unobserve(entry.target);
        });
    }, { threshold: 0.12, rootMargin: "0px 0px -5% 0px" });
    main.querySelectorAll("[data-tpl-reveal], .inv-timeline").forEach(function (el) { observer.observe(el); });

    /* 4. Parallax suave da arte no topo do convite */
    function scroller() {
        return viewport && viewport.scrollHeight > viewport.clientHeight + 1
            && window.getComputedStyle(viewport).overflowY !== "visible" ? viewport : null;
    }
    var pending = false;
    function paint() {
        pending = false;
        if (!hero) return;
        var rect = hero.getBoundingClientRect();
        var base = scroller() ? scroller().getBoundingClientRect().top : 0;
        var offset = Math.max(-rect.height, Math.min(rect.height, base - rect.top));
        hero.style.setProperty("--tpl-par", (offset * 0.28).toFixed(1) + "px");
    }
    function request() { if (!pending) { pending = true; window.requestAnimationFrame(paint); } }
    window.addEventListener("scroll", request, { passive: true });
    if (viewport) viewport.addEventListener("scroll", request, { passive: true });

    /* 5. Contagem regressiva com um pequeno "tique" */
    var countdown = main.querySelector("[data-countdown]");
    if (countdown && "MutationObserver" in window) {
        new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                var cell = mutation.target.nodeType === 1 ? mutation.target : mutation.target.parentNode;
                if (!cell || !cell.matches || !cell.matches("[data-unit]")) return;
                cell.classList.remove("tpl-tick");
                void cell.offsetWidth;
                cell.classList.add("tpl-tick");
            });
        }).observe(countdown, { childList: true, characterData: true, subtree: true });
    }
})();
