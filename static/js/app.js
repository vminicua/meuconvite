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

    function showLoading(form) {
        if (form.dataset.noLoading === "true" || typeof window.Swal === "undefined") return;
        const submitter = form.querySelector("button[type=submit]:focus, input[type=submit]:focus");
        window.Swal.fire({
            title: (submitter && submitter.dataset.loadingText) || "A processar…",
            allowOutsideClick: false,
            allowEscapeKey: false,
            showConfirmButton: false,
            didOpen: function () { window.Swal.showLoading(); }
        });
    }

    function showFlashMessages(root) {
        if (typeof window.Swal === "undefined") return;
        root.querySelectorAll(".js-flash-message:not([data-swal-shown])").forEach(function (element) {
            element.dataset.swalShown = "true";
            const kind = element.dataset.swalKind || "info";
            const icon = kind === "danger" || kind === "error" ? "error" : kind;
            const message = element.dataset.swalMessage || element.textContent.trim();
            element.hidden = true;
            if (icon === "error") {
                window.Swal.fire({
                    icon: "error", title: "Não foi possível concluir", text: message,
                    confirmButtonColor: "#c8a96a"
                });
            } else {
                window.Swal.fire({
                    toast: true, position: "top-end", icon: icon === "danger" ? "error" : icon,
                    title: message, showConfirmButton: false, timer: 4500, timerProgressBar: true
                });
            }
        });
    }

    window.MeuConvite = { getCsrfToken: getCsrfToken, showFlashMessages: showFlashMessages };

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

        // `form.submit()` não envia o botão que foi carregado. Em
        // formulários com mais do que um botão (confirmar/recusar, por
        // exemplo) esse valor é essencial, por isso é reposto num campo
        // escondido antes de submeter.
        const submitter = event.submitter;
        if (submitter && submitter.name) {
            const carried = document.createElement("input");
            carried.type = "hidden";
            carried.name = submitter.name;
            carried.value = submitter.value;
            form.appendChild(carried);
        }

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
                showLoading(form);
                form.submit();
            }
        });
    });

    /** Feedback consistente para todos os restantes submits. */
    document.addEventListener("submit", function (event) {
        if (!event.defaultPrevented && event.target.method.toLowerCase() !== "get") {
            showLoading(event.target);
        }
    });

    document.addEventListener("invalid", function (event) {
        const form = event.target.form;
        if (!form || form.dataset.invalidAlertShown === "true" || typeof window.Swal === "undefined") return;
        form.dataset.invalidAlertShown = "true";
        window.Swal.fire({
            icon: "warning", title: "Preencha os campos obrigatórios",
            text: event.target.validationMessage || "Revise os dados e tente novamente.",
            confirmButtonColor: "#c8a96a"
        }).then(function () { event.target.focus(); });
        window.setTimeout(function () { delete form.dataset.invalidAlertShown; }, 500);
    }, true);

    document.addEventListener("DOMContentLoaded", function () { showFlashMessages(document); });
    document.body.addEventListener("htmx:afterSwap", function (event) { showFlashMessages(event.target); });

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
