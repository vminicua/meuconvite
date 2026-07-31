/* Página inicial: revelação ao deslizar e palavra que muda no título. */
(function () {
    "use strict";

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    /* --- Revelação dos blocos ao entrarem no ecrã --------------------- */
    const revealables = document.querySelectorAll(".reveal");

    if (reducedMotion || !("IntersectionObserver" in window)) {
        revealables.forEach(function (element) {
            element.classList.add("is-visible");
        });
    } else {
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
    }

    /* --- Tipo de evento que muda sozinho no título -------------------- */
    // A plataforma serve casamentos, aniversários, lobolo, batismos e
    // outros eventos: o título percorre essa lista.
    const rotator = document.querySelector(".rotator");
    if (!rotator || reducedMotion) {
        return;
    }

    const words = (rotator.dataset.words || "")
        .split("|")
        .map(function (word) { return word.trim(); })
        .filter(Boolean);

    if (words.length < 2) {
        return;
    }

    const slot = rotator.querySelector(".rotator__word");
    let index = words.indexOf(slot.textContent.trim());
    if (index < 0) {
        index = 0;
    }

    // Reserva a largura da palavra mais comprida para o título não saltar.
    function reserveWidth() {
        const probe = document.createElement("span");
        probe.style.cssText = "position:absolute;visibility:hidden;white-space:nowrap";
        probe.className = slot.className;
        rotator.appendChild(probe);

        let widest = 0;
        words.forEach(function (word) {
            probe.textContent = word;
            widest = Math.max(widest, probe.offsetWidth);
        });
        rotator.appendChild(probe);
        rotator.removeChild(probe);

        if (widest > 0) {
            rotator.style.minWidth = widest + "px";
        }
    }

    reserveWidth();
    window.addEventListener("resize", reserveWidth);

    window.setInterval(function () {
        slot.classList.add("is-leaving");

        window.setTimeout(function () {
            index = (index + 1) % words.length;
            slot.textContent = words[index];
            slot.classList.remove("is-leaving");
            slot.classList.add("is-entering");

            // Força o navegador a aplicar o estado inicial antes da entrada.
            void slot.offsetWidth;
            slot.classList.remove("is-entering");
        }, 350);
    }, 2800);
})();
