/** @odoo-module **/

import { dateField } from "@web/views/fields/datetime/datetime_field";
import { registry } from "@web/core/registry";
import { onMounted } from "@odoo/owl";

const DateFieldClass = dateField.component;

// Chargement immédiat au démarrage du module
let _periodes = [];
let _observerStarted = false;

// Charger dès que le module est exécuté
fetch("/gica/periodes_verrouillees", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", method: "call", id: 1, params: {} }),
})
.then(r => r.json())
.then(r => {
    _periodes = r.result || [];
    console.log("[GICA] Periodes chargees:", _periodes);
})
.catch(e => console.warn("[GICA] Erreur chargement periodes:", e));

function _griser() {
    if (!_periodes.length) return;

    const picker = document.querySelector(".o_datetime_picker");
    if (!picker) return;

    const titreEl = picker.querySelector("strong.o_header_part");
    if (!titreEl) return;

    const txt = titreEl.textContent.trim().toLowerCase();
    const moisFr = {
        "janvier":1,"février":2,"mars":3,"avril":4,"mai":5,"juin":6,
        "juillet":7,"août":8,"septembre":9,"octobre":10,"novembre":11,"décembre":12
    };

    let year = null, month = null;
    for (const [nom, num] of Object.entries(moisFr)) {
        if (txt.includes(nom)) {
            month = num;
            const m = txt.match(/\d{4}/);
            if (m) year = parseInt(m[0]);
            break;
        }
    }
    if (!year || !month) return;

    picker.querySelectorAll(".o_date_item_cell").forEach(cell => {
        const jour = parseInt(cell.querySelector("span")?.textContent.trim());
        if (!jour || jour < 1 || jour > 31) return;

        const ds = `${year}-${String(month).padStart(2,"0")}-${String(jour).padStart(2,"0")}`;
        cell.classList.remove("gica-date-verrouillee");
        cell.style.pointerEvents = "";
        cell.title = "";

        for (const p of _periodes) {
            if (ds >= p.from && ds <= p.to) {
                cell.classList.add("gica-date-verrouillee");
                cell.title = `Periode verrouillee : ${p.name}`;
                cell.style.pointerEvents = "none";
                break;
            }
        }
    });
}

function _startObserver() {
    if (_observerStarted) return;
    _observerStarted = true;
    new MutationObserver(() => {
        if (document.querySelector(".o_datetime_picker")) {
            setTimeout(_griser, 50);
        }
    }).observe(document.body, { childList: true, subtree: true });
}

class GicaDateFieldVerrouillee extends DateFieldClass {
    setup() {
        super.setup();
        onMounted(() => _startObserver());
    }
}

registry.category("fields").add("date_verrouillee", {
    ...dateField,
    component: GicaDateFieldVerrouillee,
});