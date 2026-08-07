(function () {
    "use strict";

    function initGiftList(scope) {
        const list = (scope || document).querySelector("[data-gift-list]");
        if (!list || list.dataset.giftListReady === "true") return;
        list.dataset.giftListReady = "true";

        const cards = Array.from(list.querySelectorAll("[data-gift-card]"));
        const footer = document.querySelector("[data-gift-footer]");
        const summary = document.querySelector("[data-gift-summary]");
        const pager = document.querySelector("[data-gift-pagination]");
        const mobileQuery = window.matchMedia("(max-width: 767.98px)");
        let page = 1;

        function render() {
            const perPage = mobileQuery.matches ? 8 : Math.max(cards.length, 1);
            const pages = Math.max(1, Math.ceil(cards.length / perPage));
            page = Math.min(page, pages);
            cards.forEach(function (card, index) {
                card.hidden = index < (page - 1) * perPage || index >= page * perPage;
            });
            if (footer) footer.hidden = !mobileQuery.matches || cards.length <= perPage;
            if (summary) summary.textContent = "A mostrar " + (((page - 1) * perPage) + 1) + "–" + Math.min(page * perPage, cards.length) + " de " + cards.length;
            if (!pager) return;
            pager.innerHTML = "";
            if (!mobileQuery.matches || pages <= 1) return;
            [
                {label: "‹", target: page - 1, disabled: page === 1},
                {label: page + " / " + pages, target: page, disabled: true},
                {label: "›", target: page + 1, disabled: page === pages}
            ].forEach(function (item) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "btn btn-sm btn-outline-secondary";
                button.textContent = item.label;
                button.disabled = item.disabled;
                button.addEventListener("click", function () {
                    page = item.target;
                    render();
                    list.scrollIntoView({behavior: "smooth", block: "start"});
                });
                pager.appendChild(button);
            });
        }

        render();
        mobileQuery.addEventListener("change", function () { page = 1; render(); });
    }

    initGiftList(document);
    document.addEventListener("workspace:loaded", function () { initGiftList(document); });
})();
