/* Diálogo local compatível com a API usada do SweetAlert2. */
(function () {
    "use strict";
    if (typeof window.Swal !== "undefined") return;

    let active = null;
    const icons = { success: "✓", error: "!", warning: "!", info: "i", question: "?" };

    function close(result) {
        if (!active) return;
        const current = active;
        active = null;
        current.element.remove();
        current.resolve(result || { isDismissed: true });
    }

    function button(label, className) {
        const element = document.createElement("button");
        element.type = "button";
        element.className = className;
        element.textContent = label;
        return element;
    }

    function fire(input) {
        const options = typeof input === "string" ? { title: input } : (input || {});
        if (active) close({ isDismissed: true });

        return new Promise(function (resolve) {
            const container = document.createElement("div");
            const popup = document.createElement("div");
            const toast = Boolean(options.toast);
            container.className = toast ? "mc-swal-container mc-swal-toast-container" : "mc-swal-container";
            popup.className = toast ? "mc-swal-popup mc-swal-toast" : "mc-swal-popup";
            popup.setAttribute("role", toast ? "status" : "alertdialog");
            popup.setAttribute("aria-live", "assertive");

            if (options.icon) {
                const icon = document.createElement("span");
                icon.className = "mc-swal-icon mc-swal-icon--" + options.icon;
                icon.textContent = icons[options.icon] || "i";
                popup.appendChild(icon);
            }
            if (options.title) {
                const title = document.createElement(toast ? "div" : "h2");
                title.className = "mc-swal-title";
                title.textContent = options.title;
                popup.appendChild(title);
            }
            if (options.text) {
                const text = document.createElement("p");
                text.className = "mc-swal-text";
                text.textContent = options.text;
                popup.appendChild(text);
            }

            if (options.showConfirmButton !== false || options.showCancelButton) {
                const actions = document.createElement("div");
                actions.className = "mc-swal-actions";
                if (options.showCancelButton) {
                    const cancel = button(options.cancelButtonText || "Cancelar", "mc-swal-button mc-swal-cancel");
                    cancel.addEventListener("click", function () { close({ isDismissed: true, dismiss: "cancel" }); });
                    actions.appendChild(cancel);
                }
                if (options.showConfirmButton !== false) {
                    const confirm = button(options.confirmButtonText || "OK", "mc-swal-button mc-swal-confirm");
                    if (options.confirmButtonColor) confirm.style.backgroundColor = options.confirmButtonColor;
                    confirm.addEventListener("click", function () { close({ isConfirmed: true }); });
                    actions.appendChild(confirm);
                    window.setTimeout(function () { confirm.focus(); }, 0);
                }
                popup.appendChild(actions);
            }

            container.appendChild(popup);
            document.body.appendChild(container);
            active = { element: container, popup: popup, resolve: resolve };

            if (!toast && options.allowOutsideClick !== false) {
                container.addEventListener("click", function (event) {
                    if (event.target === container) close({ isDismissed: true, dismiss: "backdrop" });
                });
            }
            if (options.timer) {
                window.setTimeout(function () {
                    if (active && active.element === container) close({ isDismissed: true, dismiss: "timer" });
                }, options.timer);
            }
            if (typeof options.didOpen === "function") options.didOpen(popup);
        });
    }

    function showLoading() {
        if (!active) return;
        let loader = active.popup.querySelector(".mc-swal-loader");
        if (!loader) {
            loader = document.createElement("span");
            loader.className = "mc-swal-loader";
            active.popup.insertBefore(loader, active.popup.firstChild);
        }
    }

    window.Swal = { fire: fire, showLoading: showLoading, close: close, isFallback: true };
})();
