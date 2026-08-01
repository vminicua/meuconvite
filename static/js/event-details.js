(function () {
    "use strict";
    const form = document.querySelector("[data-event-details]");
    if (!form) return;
    const coverInput = form.querySelector("[data-cover-input]");
    const cover = form.querySelector("[data-cover-preview]");
    const empty = form.querySelector("[data-cover-empty]");
    if (coverInput) coverInput.addEventListener("change", function () {
        const file = coverInput.files && coverInput.files[0];
        if (!file) return;
        cover.style.backgroundImage = "url('" + URL.createObjectURL(file) + "')";
        empty.hidden = true;
    });
    const sms = form.querySelector("[name=sms_invitation_message]");
    const preview = form.querySelector("[data-sms-preview]");
    const counter = form.querySelector("[data-sms-count]");
    function renderSms() {
        const raw = sms.value || "A sua mensagem aparece aqui…";
        preview.textContent = raw.replaceAll("{nome}", "Alberto").replaceAll("{evento}", form.dataset.eventName).replaceAll("{link}", form.dataset.eventLink);
        counter.textContent = sms.value.length;
    }
    sms.addEventListener("input", renderSms); renderSms();
})();
