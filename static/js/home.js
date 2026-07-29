/* Animações da página inicial: revelação ao deslizar e contagem dos números. */
(function () {
    "use strict";

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const revealables = document.querySelectorAll(".reveal");

    if (reducedMotion || !("IntersectionObserver" in window)) {
        revealables.forEach(function (element) {
            element.classList.add("is-visible");
        });
        return;
    }

    const revealObserver = new IntersectionObserver(
        function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    revealObserver.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );

    revealables.forEach(function (element) {
        revealObserver.observe(element);
    });

    /** Conta de 0 até ao valor final quando o número entra no ecrã. */
    function animateCount(element) {
        const target = parseInt(element.dataset.countTo, 10);
        if (Number.isNaN(target)) {
            return;
        }
        const duration = 900;
        const start = performance.now();

        function tick(now) {
            const progress = Math.min((now - start) / duration, 1);
            // easeOutCubic
            const eased = 1 - Math.pow(1 - progress, 3);
            element.textContent = String(Math.round(target * eased));
            if (progress < 1) {
                window.requestAnimationFrame(tick);
            }
        }

        window.requestAnimationFrame(tick);
    }

    const counterObserver = new IntersectionObserver(
        function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    animateCount(entry.target);
                    counterObserver.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.6 }
    );

    document.querySelectorAll("[data-count-to]").forEach(function (element) {
        counterObserver.observe(element);
    });
})();
