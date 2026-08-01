(function () {
    "use strict";
    const cards = document.querySelectorAll(".subscription-plan");
    function closeAll() {
        cards.forEach(function (card) {
            card.classList.remove("is-checking-out");
            const checkout = card.querySelector("[data-plan-checkout]");
            if (checkout) checkout.classList.remove("is-open");
        });
    }
    document.querySelectorAll("[data-plan-select]").forEach(function (button) {
        button.addEventListener("click", function () {
            const card = button.closest(".subscription-plan");
            const checkout = card.querySelector("[data-plan-checkout]");
            const wasOpen = checkout.classList.contains("is-open");
            closeAll();
            if (!wasOpen) {
                card.classList.add("is-checking-out");
                checkout.classList.add("is-open");
                window.setTimeout(function () { checkout.scrollIntoView({behavior:"smooth", block:"nearest"}); }, 120);
            }
        });
    });
    document.querySelectorAll("[data-plan-close]").forEach(function (button) {
        button.addEventListener("click", closeAll);
    });
    document.querySelectorAll("[data-plan-checkout].is-open").forEach(function (checkout) {
        checkout.closest(".subscription-plan").classList.add("is-checking-out");
    });
})();
