(function () {
    "use strict";

    const picker = document.querySelector("[data-template-carousel]");
    if (!picker) {
        return;
    }

    const tabs = Array.from(picker.querySelectorAll("[data-category-tab]"));
    const panels = Array.from(picker.querySelectorAll("[data-category-panel]"));
    const count = picker.querySelector("[data-carousel-count]");

    function updateArrows(panel) {
        const track = panel.querySelector("[data-carousel-track]");
        if (!track) {
            return;
        }
        const previous = panel.querySelector("[data-carousel-prev]");
        const next = panel.querySelector("[data-carousel-next]");
        const maxScroll = Math.max(0, track.scrollWidth - track.clientWidth);
        previous.disabled = track.scrollLeft <= 4;
        next.disabled = track.scrollLeft >= maxScroll - 4;
    }

    function activate(code, focusTab) {
        let activePanel = null;
        tabs.forEach(function (tab) {
            const active = tab.dataset.categoryTab === code;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", active ? "true" : "false");
            tab.tabIndex = active ? 0 : -1;
            if (active && focusTab) {
                tab.focus();
            }
        });
        panels.forEach(function (panel) {
            const active = panel.dataset.categoryPanel === code;
            panel.hidden = !active;
            panel.classList.toggle("is-active", active);
            if (active) {
                activePanel = panel;
            }
        });
        if (activePanel) {
            const total = Number(activePanel.dataset.templateCount || 0);
            count.textContent = total + (total === 1 ? " template" : " templates");
            window.requestAnimationFrame(function () {
                updateArrows(activePanel);
            });
        }
    }

    tabs.forEach(function (tab, index) {
        tab.addEventListener("click", function () {
            activate(tab.dataset.categoryTab, false);
        });
        tab.addEventListener("keydown", function (event) {
            if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
                return;
            }
            event.preventDefault();
            const direction = event.key === "ArrowRight" ? 1 : -1;
            const target = tabs[(index + direction + tabs.length) % tabs.length];
            activate(target.dataset.categoryTab, true);
        });
    });

    panels.forEach(function (panel) {
        const track = panel.querySelector("[data-carousel-track]");
        if (!track) {
            return;
        }
        const distance = function () {
            const card = track.querySelector(".market-template-card");
            return card ? card.getBoundingClientRect().width + 18 : track.clientWidth * 0.8;
        };
        panel.querySelector("[data-carousel-prev]").addEventListener("click", function () {
            track.scrollBy({ left: -distance(), behavior: "smooth" });
        });
        panel.querySelector("[data-carousel-next]").addEventListener("click", function () {
            track.scrollBy({ left: distance(), behavior: "smooth" });
        });
        track.addEventListener("scroll", function () {
            window.requestAnimationFrame(function () {
                updateArrows(panel);
            });
        }, { passive: true });
    });

    window.addEventListener("resize", function () {
        const active = picker.querySelector("[data-category-panel].is-active");
        if (active) {
            updateArrows(active);
        }
    });

    if (tabs.length) {
        activate(tabs[0].dataset.categoryTab, false);
    }
})();
