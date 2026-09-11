// Copyright (c) 2026, Sardorbek Qamchibekov and contributors
// For license information, please see license.txt

// Mijoz tanlanganda uning joriy qoldig'i customer ostidagi read-only
// «Остаток контрагента» (custom_party_balance) maydonida ko'rsatiladi.
// Qiymat hujjat bilan saqlanadi — o'sha paytdagi qoldiq tarixi bo'lib qoladi.
frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {
        suviner_si_party_balance(frm);
    },
    customer(frm) {
        suviner_si_party_balance(frm);
    },
});

function suviner_si_party_balance(frm) {
    // Submitted hujjatda saqlangan (o'sha paytdagi) qiymat ko'rsatiladi.
    if (frm.doc.docstatus > 0) return;
    if (!frm.doc.customer) {
        suviner_set_balance_field(frm, 0, "");
        return;
    }
    const requested_customer = frm.doc.customer;
    frappe.call({
        method: "suviner.party_balance.get_party_balance",
        args: {
            party_type: "Customer",
            party: requested_customer,
            company: frm.doc.company,
            date: frm.doc.posting_date,
        },
        callback(r) {
            const m = r.message;
            // Javob kelguncha mijoz almashgan bo'lsa — eskirgan natijani yozmaymiz.
            if (!m || frm.doc.customer !== requested_customer) return;
            suviner_set_balance_field(frm, m.balance, m.message, m.currency);
        },
    });
}

// Qiymatni dirty-belgisiz yozish (Kassa'dagi set_derived_value uslubi).
function suviner_set_balance_field(frm, value, message, currency) {
    if (frm.doc.custom_party_balance_currency !== (currency || "")) {
        frm.doc.custom_party_balance_currency = currency || "";
        frm.refresh_field("custom_party_balance_currency");
    }
    if (frm.doc.custom_party_balance !== value) {
        frm.doc.custom_party_balance = value;
        frm.refresh_field("custom_party_balance");
    }
    frm.set_df_property("custom_party_balance", "description",
        frappe.utils.escape_html(message || ""));
}

// ─── Create > Payment o'rniga Kassa ───────────────────────────────────────
// Yadro tugmasi Payment Entry ochardi — endi to'lovlar Kassa orqali:
// kontragent, summa va izoh oldindan to'ldirilgan holda ochiladi.
frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {
        suviner_si_kassa_button(frm);
    },
});

function suviner_si_kassa_button(frm) {
    if (frm.doc.docstatus !== 1 || !flt(frm.doc.outstanding_amount)) return;
    frm.remove_custom_button(__("Payment"), __("Create"));
    frm.add_custom_button(__("Касса"), () => {
        frappe.call({
            method: "suviner.make_kassa.make_kassa",
            args: { doctype: frm.doc.doctype, name: frm.doc.name },
            callback(r) {
                if (!r.message) return;
                const doc = frappe.model.sync(r.message)[0];
                frappe.set_route("Form", doc.doctype, doc.name);
            },
        });
    }, __("Create"));
}
