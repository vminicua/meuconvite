(function () {
    "use strict";
    const list = document.getElementById("program-list");
    if (!list || list.dataset.sortable !== "true" || typeof window.Sortable === "undefined") return;
    window.Sortable.create(list, {
        handle: ".program-row__handle",
        animation: 180,
        ghostClass: "sortable-ghost",
        onEnd: function () {
            const order = Array.from(list.querySelectorAll(".program-row")).map(item => item.dataset.id);
            fetch(list.dataset.reorderUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": window.MeuConvite.getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify({order: order})
            });
        }
    });
})();
