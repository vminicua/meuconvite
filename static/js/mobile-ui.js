(function () {
    "use strict";

    const mobileQuery = window.matchMedia("(max-width: 575.98px)");

    function syncDisclosures(scope) {
        (scope || document).querySelectorAll("[data-mobile-collapsible]").forEach(function (details) {
            if (details.dataset.mobileDisclosureReady !== "true") {
                details.dataset.mobileDisclosureReady = "true";
                details.dataset.desktopOpen = details.open ? "true" : "false";
            }
            if (mobileQuery.matches && !details.dataset.mobileStateApplied) {
                details.open = false;
                details.dataset.mobileStateApplied = "true";
            } else if (!mobileQuery.matches) {
                details.open = details.dataset.desktopOpen === "true";
                delete details.dataset.mobileStateApplied;
            }
        });
    }

    syncDisclosures(document);
    document.addEventListener("workspace:loaded", function () { syncDisclosures(document); });
    mobileQuery.addEventListener("change", function () { syncDisclosures(document); });
})();
