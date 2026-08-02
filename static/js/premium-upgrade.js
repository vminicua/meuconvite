(function () {
    "use strict";

    document.addEventListener("click", function (event) {
        const trigger = event.target.closest("[data-upgrade-modal]");
        if (!trigger) return;
        event.preventDefault();
        event.stopPropagation();
        const feature = trigger.dataset.upgradeFeature || "Esta funcionalidade";
        const message = trigger.dataset.upgradeMessage || "Escolha um pacote para desbloquear esta funcionalidade neste evento.";
        const modalElement = document.getElementById("upgradePlansModal");
        if (modalElement && window.bootstrap) {
            const title = modalElement.querySelector("#upgradePlansTitle");
            const description = modalElement.querySelector("[data-upgrade-modal-description]");
            if (title) title.textContent = feature;
            if (description) description.textContent = message;
            window.bootstrap.Modal.getOrCreateInstance(modalElement).show();
        } else if (window.Swal) {
            window.Swal.fire({
                icon: "info",
                title: feature,
                text: message,
                confirmButtonText: "Entendi",
                confirmButtonColor: "#b5903e"
            });
        }
    }, true);
})();
