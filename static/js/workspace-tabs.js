(function () {
    "use strict";

    let navigating = false;
    document.documentElement.dataset.workspaceNavigationCount = "0";

    async function loadWorkspace(url, pushState) {
        if (navigating) return;
        const currentMain = document.querySelector("main");
        if (!currentMain) {
            window.location.href = url;
            return;
        }
        navigating = true;
        currentMain.classList.add("workspace-is-loading");
        currentMain.setAttribute("aria-busy", "true");
        try {
            const response = await fetch(url, {
                credentials: "same-origin",
                headers: {"X-Workspace-Navigation": "true"}
            });
            if (!response.ok) throw new Error("navigation failed");
            const html = await response.text();
            const parsed = new DOMParser().parseFromString(html, "text/html");
            const nextMain = parsed.querySelector("main");
            if (!nextMain || !nextMain.querySelector("[data-wedding-workspace]")) {
                window.location.href = url;
                return;
            }
            currentMain.replaceWith(nextMain);
            document.documentElement.dataset.workspaceNavigationCount = String(
                Number(document.documentElement.dataset.workspaceNavigationCount || "0") + 1
            );
            document.title = parsed.title || document.title;
            if (pushState) history.pushState({workspace: true}, "", response.url || url);
            document.dispatchEvent(new CustomEvent("workspace:loaded", {detail: {url: response.url || url}}));
            window.scrollTo({top: 0, behavior: "smooth"});
        } catch (error) {
            window.location.href = url;
        } finally {
            navigating = false;
            const main = document.querySelector("main");
            if (main) {
                main.classList.remove("workspace-is-loading");
                main.removeAttribute("aria-busy");
            }
        }
    }

    document.addEventListener("click", function (event) {
        const link = event.target.closest("a[data-workspace-nav]");
        if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        if (link.origin !== window.location.origin) return;
        event.preventDefault();
        loadWorkspace(link.href, true);
    });

    window.addEventListener("popstate", function () {
        if (document.querySelector("[data-wedding-workspace]")) loadWorkspace(window.location.href, false);
    });
})();
