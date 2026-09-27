/*
 * azul-marinho — acabamento animado do convite (cartão clássico).
 *
 * Só decora: distribui as peças da camada decorativa, troca os ícones do
 * programa, anima a capa, a abertura e a entrada das secções ao percorrer.
 * Sem este script o convite continua completo e legível.
 */
(function () {
    "use strict";

    var body = document.body;
    if (!body || !body.classList.contains("inv--template-azul-marinho")) return;

    var CFG = { cover: 18, intro: 12, burst: 26, size: [0.35, 0.8], speed: [12, 22], openMs: 1100, variants: 3 };
    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var cover = document.getElementById("inv-cover");
    var main = document.getElementById("inv-main");
    var stash = document.querySelector("[data-tpl-decor]");

    function each(list, fn) { Array.prototype.forEach.call(list, fn); }
    function rand(min, max) { return min + Math.random() * (max - min); }

    /* --- 1. Peças decorativas: cada uma diz para onde vai. -------------- */
    if (stash) {
        each(stash.querySelectorAll("[data-tpl-into]"), function (piece) {
            var target = document.querySelector(piece.getAttribute("data-tpl-into"));
            if (!target) return;
            var where = piece.getAttribute("data-tpl-pos") || "append";
            piece.removeAttribute("data-tpl-into");
            if (where === "prepend") target.insertBefore(piece, target.firstChild);
            else if (where === "before") target.parentNode.insertBefore(piece, target);
            else if (where === "after") target.parentNode.insertBefore(piece, target.nextSibling);
            else target.appendChild(piece);
            var flag = piece.getAttribute("data-tpl-flag");
            if (flag) {
                var host = piece.closest(flag.split("|")[0]);
                if (host) host.classList.add(flag.split("|")[1]);
            }
        });
    }

    /* --- 2. Ícones desenhados no programa. ------------------------------ */
    var ICONS = [
        [/cerim|igreja|religi|votos|casamento|civil|bên[cç]/i, "rings"],
        [/cocktail|coquetel|brinde|boas[- ]vindas|welcome|aperitivo/i, "toast"],
        [/jantar|almo[cç]o|banquete|recep[cç]|refei/i, "dinner"],
        [/festa|dan[cç]a|baile|m[uú]sica|dj|pista/i, "music"],
        [/bolo/i, "cake"],
        [/foto|sess[aã]o/i, "camera"]
    ];
    each(document.querySelectorAll(".inv-timeline__item"), function (item, index) {
        var dot = item.querySelector(".inv-timeline__dot");
        var label = item.querySelector(".inv-timeline__label");
        if (!dot || !document.getElementById("tpl-i-heart")) return;
        var text = label ? label.textContent : "";
        var icon = "heart";
        for (var i = 0; i < ICONS.length; i++) {
            if (ICONS[i][0].test(text)) { icon = ICONS[i][1]; break; }
        }
        if (!document.getElementById("tpl-i-" + icon)) icon = "heart";
        dot.innerHTML = '<svg viewBox="0 0 32 32" aria-hidden="true" focusable="false"><use href="#tpl-i-' + icon + '"/></svg>';
        item.style.setProperty("--n", index);
    });

    if (reduced) return;

    /* --- 3. Movimento ---------------------------------------------------- */
    body.classList.add("tpl-motion");

    function particles(host, count, burst) {
        if (!host || !count) return null;
        var layer = document.createElement("div");
        layer.className = "tpl-particles";
        layer.setAttribute("aria-hidden", "true");
        for (var i = 0; i < count; i++) {
            var p = document.createElement("i");
            p.className = "tpl-p" + (1 + (i % (CFG.variants || 3)));
            var s = rand(CFG.size[0], CFG.size[1]);
            p.style.setProperty("--x", rand(-5, 100).toFixed(1) + "%");
            p.style.setProperty("--s", s.toFixed(2) + "rem");
            p.style.setProperty("--dur", rand(CFG.speed[0], CFG.speed[1]).toFixed(1) + "s");
            p.style.setProperty("--delay", (burst ? rand(0, 1.2) : rand(-14, 0)).toFixed(1) + "s");
            p.style.setProperty("--drift", rand(-6, 7).toFixed(1) + "rem");
            p.style.setProperty("--spin", rand(-420, 420).toFixed(0) + "deg");
            p.style.setProperty("--o", rand(.45, .95).toFixed(2));
            layer.appendChild(p);
        }
        host.appendChild(layer);
        return layer;
    }

    // Capa: os elementos entram em cascata depois da abertura do envelope.
    if (cover) {
        var paper = cover.querySelector(".inv-cover__paper");
        if (paper) {
            each(paper.children, function (child, i) {
                child.classList.add("tpl-cv");
                child.style.setProperty("--i", i);
            });
        }
        particles(cover, CFG.cover);
        var intro = document.querySelector("[data-opening-intro]");
        var go = function () { cover.classList.add("tpl-cover-go"); };
        if (intro && document.body.contains(intro)) {
            if (CFG.intro) particles(intro, CFG.intro);
            var started = false;
            var start = function () { if (!started) { started = true; window.setTimeout(go, 120); } };
            new MutationObserver(function () {
                if (intro.classList.contains("is-complete")) start();
            }).observe(intro, { attributes: true, attributeFilter: ["class"] });
            window.setTimeout(start, 3400);
        } else {
            window.requestAnimationFrame(go);
        }

        // Abertura cinematográfica antes da transição normal do convite.
        var opening = false;
        var passing = false;
        document.addEventListener("click", function (event) {
            var button = event.target && event.target.closest && event.target.closest("[data-open-invitation]");
            if (!button || passing || !document.body.contains(cover)) return;
            event.stopPropagation();
            event.preventDefault();
            if (opening) return;
            opening = true;
            cover.classList.add("tpl-opening");
            particles(cover, CFG.burst || 0, true);
            window.setTimeout(function () {
                passing = true;
                body.classList.add("tpl-opened");
                button.click();
            }, CFG.openMs || 1050);
        }, true);
    }

    // Revelação ao percorrer.
    if ("IntersectionObserver" in window && main) {
        var groups = [
            [".inv-hero > *", ""],
            [".inv-main > .inv-section > *:not(.inv-timeline)", ""],
            [".inv-timeline__item", "tpl-rv--left"],
            [".inv-countdown__cell", "tpl-rv--zoom"],
            [".inv-qr__events li", ""],
            [".inv-footer > *", ""]
        ].concat(CFG.reveal || []);
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add("is-in");
                io.unobserve(entry.target);
            });
        }, { threshold: 0.08, rootMargin: "0px 0px -7% 0px" });
        groups.forEach(function (group) {
            each(main.querySelectorAll(group[0]), function (el) {
                if (el.classList.contains("tpl-rv") || el.hasAttribute("hidden")) return;
                var siblings = Array.prototype.indexOf.call(el.parentNode.children, el);
                el.classList.add("tpl-rv");
                if (group[1]) el.classList.add(group[1]);
                el.style.setProperty("--d", Math.min(siblings * 0.09, 0.6).toFixed(2) + "s");
                io.observe(el);
            });
        });
    }

    // Linha do programa desenha-se com o scroll.
    var timelines = main ? Array.prototype.slice.call(main.querySelectorAll(".inv-timeline")) : [];
    var viewportEl = document.querySelector("[data-invitation-viewport]");
    function viewportBox() {
        if (viewportEl && viewportEl.scrollHeight > viewportEl.clientHeight + 1
            && window.getComputedStyle(viewportEl).overflowY !== "visible") {
            var r = viewportEl.getBoundingClientRect();
            return { top: r.top, height: r.height };
        }
        return { top: 0, height: window.innerHeight };
    }
    var pending = false;
    function paint() {
        pending = false;
        var vp = viewportBox();
        timelines.forEach(function (line) {
            var r = line.getBoundingClientRect();
            if (!r.height) return;
            var p = (vp.top + vp.height * 0.8 - r.top) / r.height;
            line.style.setProperty("--tpl-line", (Math.max(0, Math.min(1, p)) * 100).toFixed(1) + "%");
        });
        if (CFG.onScroll) CFG.onScroll(vp);
    }
    function request() { if (!pending) { pending = true; window.requestAnimationFrame(paint); } }
    if (timelines.length || CFG.onScroll) {
        window.addEventListener("scroll", request, { passive: true });
        window.addEventListener("resize", request);
        if (viewportEl) viewportEl.addEventListener("scroll", request, { passive: true });
        request();
    }

    // Contagem: cada número que muda cai no lugar.
    each(document.querySelectorAll(".inv-countdown__cell span"), function (span) {
        new MutationObserver(function () {
            span.classList.remove("tpl-tick");
            void span.offsetWidth;
            span.classList.add("tpl-tick");
        }).observe(span, { childList: true, characterData: true, subtree: true });
    });

    
})();
