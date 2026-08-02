(function () {
    "use strict";
    const upload = document.querySelector("[data-gallery-upload] input[type=file]");
    if (!upload) return;
    upload.addEventListener("change", function () {
        const count = upload.files ? upload.files.length : 0;
        const submit = upload.closest("form").querySelector("button[type=submit]");
        if (count) submit.innerHTML = '<i class="bi bi-cloud-arrow-up me-1"></i>Adicionar ' + count + (count === 1 ? ' fotografia' : ' fotografias');
    });
})();
