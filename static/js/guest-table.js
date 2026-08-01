(function () {
    "use strict";
    const root = document.querySelector("[data-guest-table]");
    if (!root) return;

    const rows = Array.from(root.querySelectorAll("[data-guest-row]"));
    const search = root.querySelector("[data-table-search]");
    const status = root.querySelector("[data-table-status]");
    const programme = root.querySelector("[data-table-programme]");
    const size = root.querySelector("[data-page-size]");
    const pager = root.querySelector("[data-table-pagination]");
    const summary = root.querySelector("[data-table-summary]");
    const empty = root.querySelector("[data-table-empty]");
    let page = 1;
    let sortKey = "name";
    let sortDirection = 1;

    function normalized(value) {
        return (value || "").toLocaleLowerCase("pt").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    }

    function filteredRows() {
        const term = normalized(search ? search.value : "");
        const wantedStatus = status ? status.value : "";
        const wantedProgramme = normalized(programme ? programme.value : "");
        return rows.filter(function (row) {
            const haystack = normalized(row.dataset.name + " " + row.dataset.contact);
            return (!term || haystack.includes(term)) &&
                (!wantedStatus || row.dataset.status === wantedStatus) &&
                (!wantedProgramme || normalized(row.dataset.programme).includes(wantedProgramme));
        }).sort(function (a, b) {
            const enabledOrder = Number(b.dataset.enabled) - Number(a.dataset.enabled);
            if (enabledOrder !== 0) return enabledOrder;
            const av = sortKey === "seats" ? Number(a.dataset[sortKey]) : normalized(a.dataset[sortKey]);
            const bv = sortKey === "seats" ? Number(b.dataset[sortKey]) : normalized(b.dataset[sortKey]);
            return (av > bv ? 1 : av < bv ? -1 : 0) * sortDirection;
        });
    }

    function render() {
        const found = filteredRows();
        const showAll = size && size.value === "all";
        const perPage = showAll ? Math.max(found.length, 1) : Number(size ? size.value : 10);
        const pages = Math.max(1, Math.ceil(found.length / perPage));
        page = Math.min(page, pages);
        rows.forEach(function (row) { row.hidden = true; });
        found.slice((page - 1) * perPage, page * perPage).forEach(function (row) { row.hidden = false; });
        if (summary) summary.textContent = found.length ? "A mostrar " + (((page - 1) * perPage) + 1) + "–" + Math.min(page * perPage, found.length) + " de " + found.length : "0 convidados";
        if (empty) empty.hidden = found.length !== 0;
        if (pager) {
            pager.innerHTML = "";
            if (showAll || found.length === 0) return;
            const makeButton = function (label, target, disabled, active) {
                const button = document.createElement("button");
                button.type = "button"; button.className = "btn btn-sm " + (active ? "btn-primary" : "btn-outline-secondary");
                button.textContent = label; button.disabled = disabled;
                button.addEventListener("click", function () { page = target; render(); });
                pager.appendChild(button);
            };
            makeButton("‹", page - 1, page === 1, false);
            for (let i = 1; i <= pages; i += 1) if (pages <= 7 || i === 1 || i === pages || Math.abs(i - page) <= 1) makeButton(String(i), i, false, i === page);
            makeButton("›", page + 1, page === pages, false);
        }
    }

    [search, status, programme, size].forEach(function (control) {
        if (control) control.addEventListener(control === search ? "input" : "change", function () { page = 1; render(); });
    });
    root.querySelectorAll("[data-sort]").forEach(function (button) {
        button.addEventListener("click", function () {
            const key = button.dataset.sort;
            sortDirection = sortKey === key ? sortDirection * -1 : 1;
            sortKey = key; render();
        });
    });

    const feedback = root.querySelector("[data-action-feedback]");
    let feedbackTimer;
    function showFeedback(message, kind) {
        if (!feedback) return;
        window.clearTimeout(feedbackTimer);
        feedback.className = "alert guest-action-feedback alert-" + (kind || "success");
        feedback.textContent = message;
        feedback.hidden = false;
        feedbackTimer = window.setTimeout(function () { feedback.hidden = true; }, 3500);
    }

    function legacyCopy(url) {
        const area = document.createElement("textarea");
        area.value = url;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        area.setSelectionRange(0, area.value.length);
        let copied = false;
        try { copied = document.execCommand("copy"); } catch (error) { copied = false; }
        area.remove();
        return copied;
    }

    async function copyLink(url, button, fallbackMessage) {
        let copied = false;
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(url);
                copied = true;
            }
        } catch (error) { copied = false; }
        if (!copied) copied = legacyCopy(url);
        if (copied) {
            const original = button.innerHTML;
            button.innerHTML = '<i class="bi bi-check2"></i>';
            window.setTimeout(function () { button.innerHTML = original; }, 1600);
            showFeedback(fallbackMessage || "Ligação do convite copiada.", "success");
            return true;
        }
        showFeedback("Não foi possível copiar automaticamente. Seleccione e copie a ligação apresentada.", "warning");
        window.prompt("Copie a ligação do convite:", url);
        return false;
    }
    root.querySelectorAll("[data-copy-link]:not([data-share-link])").forEach(function (button) { button.addEventListener("click", function () { copyLink(button.dataset.copyLink, button); }); });
    root.querySelectorAll("[data-share-link]").forEach(function (button) {
        button.addEventListener("click", function () {
            const url = button.dataset.shareLink;
            const name = button.dataset.shareName;
            const text = "Convite individual de " + name + ": " + url;
            const modalElement = document.getElementById("shareInvitationModal");
            if (!modalElement || !window.bootstrap) {
                copyLink(url, button, "A ligação foi copiada e está pronta para partilhar.");
                return;
            }
            modalElement.querySelector("[data-share-description]").textContent = "Enviar o convite individual de " + name + ".";
            const qrImage = modalElement.querySelector("[data-share-qr-image]");
            if (qrImage) {
                qrImage.src = button.dataset.shareQr || "";
                qrImage.alt = "QR Code individual de " + name;
            }
            modalElement.querySelector("[data-share-whatsapp]").href = "https://wa.me/?text=" + encodeURIComponent(text);
            modalElement.querySelector("[data-share-email]").href = "mailto:?subject=" + encodeURIComponent("Convite MeuConvite") + "&body=" + encodeURIComponent(text);
            const copyButton = modalElement.querySelector("[data-share-copy]");
            copyButton.dataset.copyLink = url;
            window.bootstrap.Modal.getOrCreateInstance(modalElement).show();
        });
    });
    const shareCopyButton = root.querySelector("[data-share-copy]");
    if (shareCopyButton) shareCopyButton.addEventListener("click", function () {
        copyLink(shareCopyButton.dataset.copyLink, shareCopyButton);
    });

    const exportButton = root.querySelector("[data-export-excel]");
    if (exportButton) exportButton.addEventListener("click", function () {
        const url = new URL(exportButton.href, window.location.origin);
        url.search = "";
        if (search && search.value) url.searchParams.set("q", search.value);
        if (status && status.value) url.searchParams.set("status", status.value);
        if (programme && programme.value) url.searchParams.set("programme", programme.value);
        exportButton.href = url.toString();
    });
    render();
})();
