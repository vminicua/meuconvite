/* MeuConvite — shared behaviour for the administration interface. */
(function () {
    "use strict";

    /**
     * Reads the CSRF cookie. Exposed so other scripts (reordering, HTMX
     * requests) can send it without duplicating the logic.
     */
    function getCsrfToken() {
        const name = "csrftoken=";
        const parts = document.cookie ? document.cookie.split(";") : [];
        for (const part of parts) {
            const value = part.trim();
            if (value.startsWith(name)) {
                return decodeURIComponent(value.substring(name.length));
            }
        }
        const input = document.querySelector("input[name=csrfmiddlewaretoken]");
        return input ? input.value : "";
    }

    window.MeuConvite = { getCsrfToken: getCsrfToken };

    /**
     * Any form with `data-confirm` asks for confirmation before being
     * submitted. Falls back to the native confirm() when SweetAlert2 is
     * not available (slow connection, blocked CDN).
     */
    document.addEventListener("submit", function (event) {
        const form = event.target;
        const message = form.getAttribute("data-confirm");
        if (!message || form.dataset.confirmed === "true") {
            return;
        }

        event.preventDefault();

        if (typeof window.Swal === "undefined") {
            if (window.confirm(message)) {
                form.dataset.confirmed = "true";
                form.submit();
            }
            return;
        }

        window.Swal.fire({
            title: "Confirmar",
            text: message,
            icon: "question",
            showCancelButton: true,
            confirmButtonText: "Sim, continuar",
            cancelButtonText: "Cancelar",
            confirmButtonColor: "#c8a96a",
            reverseButtons: true
        }).then(function (result) {
            if (result.isConfirmed) {
                form.dataset.confirmed = "true";
                form.submit();
            }
        });
    });

    /** Send the CSRF token with every HTMX request. */
    document.body.addEventListener("htmx:configRequest", function (event) {
        event.detail.headers["X-CSRFToken"] = getCsrfToken();
    });

    /** Auto-dismiss success messages after a few seconds. */
    window.setTimeout(function () {
        document.querySelectorAll(".messages .alert-success").forEach(function (alert) {
            if (window.bootstrap && window.bootstrap.Alert) {
                window.bootstrap.Alert.getOrCreateInstance(alert).close();
            }
        });
    }, 6000);
})();
