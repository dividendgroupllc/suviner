// Copyright (c) 2026, Sardorbek Qamchibekov and contributors
// For license information, please see license.txt

// Journal Entry qatorida kontragent (Employee/Supplier/Shareholder/Customer...)
// tanlanganda uning joriy qoldig'i qatorning «Остаток контрагента»
// (custom_party_balance) ustunida ko'rsatiladi — child-jadvalning o'zida.
frappe.ui.form.on("Journal Entry Account", {
    party(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.party_type || !row.party) {
            frappe.model.set_value(cdt, cdn, "custom_party_balance", 0);
            return;
        }
        const requested_party = row.party;
        frappe.call({
            method: "suviner.party_balance.get_party_balance",
            args: {
                party_type: row.party_type,
                party: requested_party,
                company: frm.doc.company,
                date: frm.doc.posting_date,
            },
            callback(r) {
                const m = r.message;
                const live_row = locals[cdt] && locals[cdt][cdn];
                // Javob kelguncha qator o'chirilgan/kontragent almashgan bo'lsa — yozmaymiz.
                if (!m || !live_row || live_row.party !== requested_party) return;
                frappe.model.set_value(cdt, cdn, "custom_party_balance", m.balance);
            },
        });
    },
});
