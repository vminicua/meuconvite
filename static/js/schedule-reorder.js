/* Drag-and-drop ordering of the wedding programme (SortableJS). */
(function () {
    "use strict";

    const list = document.getElementById("schedule-list");
    if (!list || list.dataset.sortable !== "true" || typeof window.Sortable === "undefined") {
        return;
    }

    const status = document.getElementById("reorder-status");
    const url = list.dataset.reorderUrl;

    function setStatus(text, isError) {
        if (!status) {
            return;
        }
        status.textContent = text;
        status.classList.toggle("text-danger", Boolean(isError));
    }

    function persistOrder() {
        const order = Array.from(list.querySelectorAll(".schedule-item")).map(function (item) {
            return item.dataset.id;
        });

        setStatus("A guardar a nova ordem…", false);

        fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": window.MeuConvite.getCsrfToken(),
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify({ order: order })
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Resposta inválida do servidor.");
                }
                return response.json();
            })
            .then(function () {
                setStatus("Ordem guardada.", false);
            })
            .catch(function () {
                setStatus("Não foi possível guardar a ordem. Verifique a ligação e tente novamente.", true);
            });
    }

    window.Sortable.create(list, {
        handle: ".schedule-item__handle",
        animation: 150,
        ghostClass: "sortable-ghost",
        chosenClass: "sortable-chosen",
        onEnd: persistOrder
    });
})();
