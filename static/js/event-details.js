(function () {
    "use strict";
    const form = document.querySelector("[data-event-details]");
    if (!form) return;
    const coverInput = form.querySelector("[data-cover-input]");
    const cover = form.querySelector("[data-cover-preview]");
    const empty = form.querySelector("[data-cover-empty]");
    const reset = form.querySelector("[data-cover-reset]");
    const title = form.querySelector("[data-cover-title]");
    const clearInput = form.querySelector("[name=cover_image-clear]");
    if (coverInput) coverInput.addEventListener("change", function () {
        const file = coverInput.files && coverInput.files[0];
        if (!file) return;
        cover.style.backgroundImage = "url('" + URL.createObjectURL(file) + "')";
        empty.hidden = true;
        if (clearInput) clearInput.checked = false;
        if (reset) reset.disabled = false;
        if (title) title.textContent = "Nova fotografia";
    });
    if (reset) reset.addEventListener("click", function () {
        if (coverInput) coverInput.value = "";
        if (clearInput) clearInput.checked = true;
        const source = cover.dataset.defaultCover || "";
        cover.style.backgroundImage = source ? "url('" + source + "')" : "none";
        empty.hidden = Boolean(source);
        reset.disabled = true;
        if (title) title.textContent = "Capa original do template";
    });
    const sms = form.querySelector("[name=sms_invitation_message]");
    const counter = form.querySelector("[data-sms-count]");
    function renderSms() {
        counter.textContent = sms.value.length;
    }
    sms.addEventListener("input", renderSms); renderSms();
})();
