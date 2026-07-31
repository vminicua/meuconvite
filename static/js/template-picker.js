/*
 * Escolha do template na galeria do ecrã "Aspecto".
 *
 * Sem JavaScript a página continua a funcionar: os cartões são `label`s
 * ligados a botões de rádio chamados `selected_template`, que é o próprio
 * campo do formulário. O que este ficheiro acrescenta é o realce imediato
 * e a sugestão das cores do template escolhido.
 */
(function () {
    "use strict";

    const form = document.getElementById("design-form");
    if (!form) {
        return;
    }

    const cards = form.querySelectorAll(".template-card");
    const primaryInput = document.getElementById("id_primary_color");
    const secondaryInput = document.getElementById("id_secondary_color");
    const nameOutput = document.getElementById("selected-template-name");
    const descriptionOutput = document.getElementById("selected-template-description");

    // As cores só são substituídas se ainda forem as do template anterior:
    // assim, cores escolhidas à mão pelos noivos nunca se perdem.
    let suggestedPrimary = primaryInput ? primaryInput.value : "";
    let suggestedSecondary = secondaryInput ? secondaryInput.value : "";

    function applyColour(input, value, previous) {
        if (!input || !value) {
            return;
        }
        if (!previous || input.value.toLowerCase() === previous.toLowerCase()) {
            input.value = value;
        }
    }

    cards.forEach(function (card) {
        const radio = card.querySelector("input[type='radio']");
        if (!radio) {
            return;
        }

        radio.addEventListener("change", function () {
            if (!radio.checked) {
                return;
            }

            cards.forEach(function (other) {
                other.classList.toggle("is-selected", other === card);
            });

            applyColour(primaryInput, card.dataset.primary, suggestedPrimary);
            applyColour(secondaryInput, card.dataset.secondary, suggestedSecondary);
            suggestedPrimary = card.dataset.primary || suggestedPrimary;
            suggestedSecondary = card.dataset.secondary || suggestedSecondary;

            const nameElement = card.querySelector(".template-card__name");
            const descriptionElement = card.querySelector(".template-card__description");
            if (nameOutput && nameElement) {
                nameOutput.textContent = nameElement.textContent.trim();
            }
            if (descriptionOutput && descriptionElement) {
                descriptionOutput.textContent = descriptionElement.textContent.trim();
            }
        });
    });
})();
