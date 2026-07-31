/*
 * Área de administração: DataTables, Select2, gráficos e navegação HTMX.
 *
 * Tudo é (re)inicializado por `activate()`, chamada no arranque e depois
 * de cada troca de secção — o HTMX substitui apenas `#admin-content`, por
 * isso os componentes do conteúdo novo têm de ser ligados outra vez.
 */
(function () {
    "use strict";

    const PT = {
        emptyTable: "Sem registos",
        info: "_START_ a _END_ de _TOTAL_ registos",
        infoEmpty: "0 registos",
        infoFiltered: "(filtrado de _MAX_)",
        lengthMenu: "_MENU_ por página",
        loadingRecords: "A carregar…",
        processing: "A processar…",
        search: "",
        searchPlaceholder: "Pesquisar…",
        zeroRecords: "Nada encontrado",
        paginate: { first: "Primeiro", last: "Último", next: "Seguinte", previous: "Anterior" }
    };

    const charts = [];

    function destroyCharts() {
        while (charts.length) {
            const chart = charts.pop();
            try {
                chart.destroy();
            } catch (error) {
                /* o canvas já saiu do DOM */
            }
        }
    }

    function initTables(root) {
        if (typeof window.jQuery === "undefined" || !window.jQuery.fn.DataTable) {
            return;
        }
        window.jQuery(root).find("table[data-table]").each(function () {
            const table = window.jQuery(this);
            if (window.jQuery.fn.DataTable.isDataTable(table)) {
                return;
            }
            table.DataTable({
                language: PT,
                pageLength: parseInt(table.data("page-length"), 10) || 25,
                order: table.data("order") ? JSON.parse(table.data("order")) : [],
                columnDefs: [{ targets: "no-sort", orderable: false }],
                autoWidth: false
            });
        });
    }

    function initSelects(root) {
        if (typeof window.jQuery === "undefined" || !window.jQuery.fn.select2) {
            return;
        }
        window.jQuery(root).find("select.js-select2").each(function () {
            const select = window.jQuery(this);
            if (select.hasClass("select2-hidden-accessible")) {
                return;
            }
            select.select2({
                width: "100%",
                placeholder: select.data("placeholder") || "Todos",
                allowClear: Boolean(select.data("allow-clear")),
                language: {
                    noResults: function () { return "Sem resultados"; },
                    searching: function () { return "A pesquisar…"; }
                }
            });
        });
    }

    /** Submete o formulário de filtros assim que um filtro muda. */
    function initFilterForms(root) {
        root.querySelectorAll("form[data-auto-submit]").forEach(function (form) {
            if (form.dataset.bound === "true") {
                return;
            }
            form.dataset.bound = "true";
            form.addEventListener("change", function (event) {
                if (event.target.matches("select, input[type=checkbox], input[type=radio]")) {
                    form.requestSubmit();
                }
            });
        });
    }

    function palette(count) {
        const base = ["#c8a96a", "#1f3a5f", "#b76e79", "#6b7f42", "#8b7bb8", "#b5651d", "#12796a", "#7b1e3a"];
        const colours = [];
        for (let index = 0; index < count; index += 1) {
            colours.push(base[index % base.length]);
        }
        return colours;
    }

    function initCharts(root) {
        if (typeof window.Chart === "undefined") {
            return;
        }
        root.querySelectorAll("canvas[data-chart]").forEach(function (canvas) {
            let payload;
            try {
                payload = JSON.parse(canvas.dataset.payload || "{}");
            } catch (error) {
                return;
            }
            const kind = canvas.dataset.chart;
            const labels = payload.labels || [];
            const values = payload.values || [];

            const config = {
                type: kind,
                data: {
                    labels: labels,
                    datasets: [{
                        label: canvas.dataset.label || "",
                        data: values,
                        backgroundColor: kind === "doughnut" ? palette(values.length) : "rgba(200, 169, 106, .75)",
                        borderColor: kind === "line" ? "#c8a96a" : undefined,
                        borderWidth: kind === "line" ? 2 : 0,
                        tension: .35,
                        fill: kind === "line" ? "origin" : undefined,
                        pointRadius: 3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: kind === "doughnut", position: "bottom" }
                    },
                    scales: kind === "doughnut" ? {} : {
                        y: { beginAtZero: true, ticks: { precision: 0 } },
                        x: { grid: { display: false } }
                    }
                }
            };
            charts.push(new window.Chart(canvas, config));
        });
    }

    /**
     * Liga os componentes do conteúdo actual.
     *
     * Cada passo é isolado: se uma biblioteca externa falhar (aconteceu com
     * o Select2 numa versão incompatível do jQuery), as restantes continuam
     * a funcionar em vez de a secção ficar sem tabelas nem gráficos.
     */
    function activate(root) {
        [
            ["tabelas", initTables],
            ["selects", initSelects],
            ["filtros", initFilterForms],
            ["gráficos", initCharts]
        ].forEach(function (step) {
            try {
                step[1](root);
            } catch (error) {
                console.error("[admin] falha a inicializar " + step[0], error);
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        activate(document);

        const toggle = document.getElementById("admin-sidebar-toggle");
        const sidebar = document.getElementById("admin-sidebar");
        if (toggle && sidebar) {
            toggle.addEventListener("click", function () {
                sidebar.classList.toggle("is-open");
            });
        }
    });

    /* --- Trocas de secção via HTMX ----------------------------------- */
    document.body.addEventListener("htmx:beforeRequest", function () {
        const progress = document.getElementById("admin-progress");
        if (progress) {
            progress.classList.add("is-busy");
        }
        destroyCharts();
    });

    document.body.addEventListener("htmx:afterSwap", function (event) {
        const progress = document.getElementById("admin-progress");
        if (progress) {
            progress.classList.remove("is-busy");
        }

        activate(event.target);

        // Realce da secção actual: vence a ligação com o caminho mais
        // específico. Sem isto, «/administracao/» (visão geral) marcaria
        // como activa qualquer subsecção, por ser prefixo de todas.
        const url = window.location.pathname;
        let best = null;
        const items = document.querySelectorAll(".admin-nav__item");
        items.forEach(function (item) {
            const href = item.getAttribute("href");
            if (!href || !url.startsWith(href)) {
                return;
            }
            if (!best || href.length > best.getAttribute("href").length) {
                best = item;
            }
        });
        items.forEach(function (item) {
            item.classList.toggle("is-active", item === best);
        });

        const heading = event.target.querySelector("[data-section-title]");
        const title = document.getElementById("admin-section-title");
        if (heading && title) {
            title.textContent = heading.dataset.sectionTitle;
        }

        // Fecha a sidebar em telemóvel depois de escolher a secção.
        const sidebar = document.getElementById("admin-sidebar");
        if (sidebar) {
            sidebar.classList.remove("is-open");
        }
    });

    document.body.addEventListener("htmx:responseError", function () {
        const progress = document.getElementById("admin-progress");
        if (progress) {
            progress.classList.remove("is-busy");
        }
        if (window.Swal) {
            window.Swal.fire({
                icon: "error",
                title: "Não foi possível carregar",
                text: "Verifique a ligação e tente novamente.",
                confirmButtonColor: "#c8a96a"
            });
        }
    });
})();
