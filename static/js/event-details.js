(function () {
    "use strict";
    function init(root) {
    const form = root.querySelector("[data-event-details]");
    if (!form || form.dataset.detailsReady === "1") return;
    form.dataset.detailsReady = "1";
    const coverInput = form.querySelector("[data-cover-input]");
    const cover = form.querySelector("[data-cover-preview]");
    const uploadPreview = form.querySelector("[data-cover-upload-preview]");
    const frame = form.querySelector(".cover-phone__frame");
    const reset = form.querySelector("[data-cover-reset]");
    const title = form.querySelector("[data-cover-title]");
    const clearInput = form.querySelector("[name=cover_image-clear]");
    if (coverInput) coverInput.addEventListener("change", function () {
        const file = coverInput.files && coverInput.files[0];
        if (!file) return;
        uploadPreview.style.backgroundImage = "url('" + URL.createObjectURL(file) + "')";
        uploadPreview.hidden = false;
        if (clearInput) clearInput.checked = false;
        if (reset) reset.disabled = false;
        if (title) title.textContent = "Nova fotografia";
    });
    if (reset) reset.addEventListener("click", function () {
        if (coverInput) coverInput.value = "";
        if (clearInput) clearInput.checked = true;
        uploadPreview.hidden = true;
        uploadPreview.style.backgroundImage = "none";
        if (frame && cover.dataset.defaultPreviewUrl) frame.src = cover.dataset.defaultPreviewUrl;
        reset.disabled = true;
        if (title) title.textContent = "Capa original do template";
    });
    const sms = form.querySelector("[name=sms_invitation_message]");
    const counter = form.querySelector("[data-sms-count]");
    function renderSms() {
        counter.textContent = sms.value.length;
    }
    if (sms) { sms.addEventListener("input", renderSms); renderSms(); }
    }
    init(document);
    document.addEventListener("workspace:loaded", function () { init(document); });
})();
