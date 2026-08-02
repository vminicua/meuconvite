(function () {
    "use strict";

    document.addEventListener("click", function (event) {
        const trigger = event.target.closest("[data-upgrade-modal]");
        if (!trigger) return;
        event.preventDefault();
        event.stopPropagation();
        const feature = trigger.dataset.upgradeFeature || "Esta funcionalidade";
        const url = trigger.dataset.upgradeUrl || trigger.getAttribute("href") || "/subscricao/";
        const message = trigger.dataset.upgradeMessage || "Escolha um pacote para desbloquear esta funcionalidade neste evento.";
        if (window.Swal) {
            window.Swal.fire({
                icon: "info",
                title: feature + " é Premium",
                text: message,
                confirmButtonText: "Ver pacotes",
                cancelButtonText: "Agora não",
                showCancelButton: true,
                reverseButtons: true,
                confirmButtonColor: "#b5903e"
            }).then(function (result) {
                if (result.isConfirmed) window.location.href = url;
            });
        } else if (window.confirm(feature + " é Premium. Ver os pacotes disponíveis?")) {
            window.location.href = url;
        }
    }, true);
})();
