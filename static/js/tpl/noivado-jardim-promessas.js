/*
 * Jardim de Promessas — movimento próprio do template.
 * Só acrescenta decoração (brilhos, pó de luz) e revelações ao percorrer;
 * sem este ficheiro o convite continua completo e legível.
 */
(function () {
    "use strict";

    var body = document.body;
    if (!body || !body.classList.contains("inv--template-noivado-jardim-promessas")) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    var CONFIG = {"glints": [[55.2, 48.3, 6, 3.0, 4.8], [22, 30, 3, 4.4, 6.5], [82, 78, 3, 6, 7]], "dust": 10, "ringDraw": ""};

    function el(tag, className, style) {
        var node = document.createElement(tag);
        node.className = className;
        node.setAttribute("aria-hidden", "true");
        if (style) node.setAttribute("style", style);
        return node;
    }

    /* Capa: brilhos no diamante (só com o desenho do catálogo). */
    var cover = document.querySelector('#inv-cover.inv-cover--engagement[style*="covers/engagement"]');
    var card = cover && cover.querySelector(".inv-engagement-card");
    if (card) {
        CONFIG.glints.forEach(function (g) {
            card.appendChild(el("span", "tp-glint",
                "left:" + g[0] + "%;top:" + g[1] + "%;--s:" + g[2] + "cqw;--d:" + g[3] + "s;--t:" + (g[4] || 4.2) + "s"));
        });
        if (CONFIG.ringDraw) card.insertAdjacentHTML("beforeend", CONFIG.ringDraw);
    }

    /* Abertura do convite: pó de luz a subir dentro do arco. */
    var hero = document.querySelector("#inv-main .inv-hero");
    if (hero && CONFIG.dust) {
        for (var i = 0; i < CONFIG.dust; i++) {
            hero.appendChild(el("span", "tp-dust",
                "--x:" + (8 + Math.random() * 84).toFixed(1) + "%;--s:" + (2 + Math.random() * 3).toFixed(1) + "px;" +
                "--t:" + (7 + Math.random() * 6).toFixed(1) + "s;--d:" + (-Math.random() * 10).toFixed(1) + "s;" +
                "--dx:" + (Math.random() * 60 - 30).toFixed(0) + "px"));
        }
    }

    /* Revelação suave das partes do convite ao percorrer. */
    if (!("IntersectionObserver" in window)) return;
    var targets = [];
    if (hero) {
        Array.prototype.forEach.call(hero.children, function (child, index) {
            if (child.classList.contains("tp-dust")) return;
            child.style.setProperty("--rv-d", (Math.min(index, 8) * 0.08).toFixed(2) + "s");
            targets.push(child);
        });
    }
    document.querySelectorAll("#inv-main > .inv-section, #inv-main .inv-footer, #inv-main .inv-timeline__item, #inv-main .inv-qr__card")
        .forEach(function (node) { targets.push(node); });
    if (!targets.length) return;
    targets.forEach(function (node) { node.classList.add("tp-rv"); });
    body.classList.add("tp-motion");
    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add("is-in");
                observer.unobserve(entry.target);
            }
        });
    }, { root: null, rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    targets.forEach(function (node) { observer.observe(node); });
})();
