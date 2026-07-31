(function () {
    "use strict";

    document.addEventListener("click", function (event) {
        const addButton = event.target.closest("[data-repeated-add]");
        if (addButton) {
            const field = addButton.closest("[data-repeated-field]");
            const template = field.querySelector("[data-repeated-template]");
            const items = field.querySelector("[data-repeated-items]");
            const fragment = template.content.cloneNode(true);
            items.appendChild(fragment);
            const inputs = items.querySelectorAll("input");
            inputs[inputs.length - 1].focus();
            return;
        }

        const removeButton = event.target.closest("[data-repeated-remove]");
        if (!removeButton) {
            return;
        }
        const field = removeButton.closest("[data-repeated-field]");
        const rows = field.querySelectorAll("[data-repeated-row]");
        const row = removeButton.closest("[data-repeated-row]");
        if (rows.length === 1) {
            row.querySelector("input").value = "";
        } else {
            row.remove();
        }
    });
})();
