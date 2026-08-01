(function () {
    "use strict";

    function initTemplatePicker() {
        const form = document.getElementById("design-form");
        if (!form || form.dataset.templatePickerReady === "true") return;
        form.dataset.templatePickerReady = "true";

        const cards = Array.from(form.querySelectorAll(".template-card"));
        const primaryInput = document.getElementById("id_primary_color");
        const secondaryInput = document.getElementById("id_secondary_color");
        const nameOutput = document.getElementById("selected-template-name");
        const descriptionOutput = document.getElementById("selected-template-description");
        let suggestedPrimary = primaryInput ? primaryInput.value : "";
        let suggestedSecondary = secondaryInput ? secondaryInput.value : "";

        function applyColour(input, value, previous) {
            if (input && value && (!previous || input.value.toLowerCase() === previous.toLowerCase())) input.value = value;
        }

        cards.forEach(function (card) {
            const radio = card.querySelector("input[type='radio']");
            if (!radio) return;
            radio.addEventListener("change", function () {
                if (!radio.checked) return;
                cards.forEach(function (other) {
                    const selected = other === card;
                    other.classList.toggle("is-pending", selected && !other.classList.contains("is-selected"));
                    const wrapper = other.closest(".template-choice");
                    if (wrapper) wrapper.classList.toggle("is-pending", selected && !wrapper.classList.contains("is-selected"));
                });
                applyColour(primaryInput, card.dataset.primary, suggestedPrimary);
                applyColour(secondaryInput, card.dataset.secondary, suggestedSecondary);
                suggestedPrimary = card.dataset.primary || suggestedPrimary;
                suggestedSecondary = card.dataset.secondary || suggestedSecondary;
                if (nameOutput) nameOutput.textContent = card.dataset.name || "";
                if (descriptionOutput) descriptionOutput.textContent = card.dataset.description || "";
            });

            const applyButton = card.querySelector(".template-apply-button");
            if (applyButton) {
                applyButton.addEventListener("click", function () {
                    radio.checked = true;
                    radio.dispatchEvent(new Event("change", { bubbles: true }));
                });
            }
        });
    }

    window.initTemplatePicker = initTemplatePicker;
    document.addEventListener("DOMContentLoaded", initTemplatePicker);
    document.addEventListener("workspace:loaded", initTemplatePicker);
})();
