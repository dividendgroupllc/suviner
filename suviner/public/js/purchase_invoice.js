// Copyright (c) 2026, Sardorbek Qamchibekov and contributors
// For license information, please see license.txt

// "Доп. расход" child table'idagi "Счет расходов" (expense_account) maydonini
// faqat joriy kompaniyaning расход (Expense) ledger hisoblari bilan cheklaydi.
frappe.ui.form.on("Purchase Invoice", {
	onload(frm) {
		frm.set_query("expense_account", "custom_dop_rasxod_items", (doc) => {
			return {
				filters: {
					company: doc.company,
					is_group: 0,
					root_type: "Expense",
				},
			};
		});
	},
});

// Ta'minotchi tanlanganda uning joriy qoldig'i supplier ostidagi read-only
// «Остаток контрагента» (custom_party_balance) maydonida ko'rsatiladi.
frappe.ui.form.on("Purchase Invoice", {
    refresh(frm) {
        suviner_pi_party_balance(frm);
    },
    supplier(frm) {
        suviner_pi_party_balance(frm);
    },
});

function suviner_pi_party_balance(frm) {
    // Submitted hujjatda saqlangan (o'sha paytdagi) qiymat ko'rsatiladi.
    if (frm.doc.docstatus > 0) return;
    if (!frm.doc.supplier) {
        suviner_pi_set_balance(frm, 0, "");
        return;
    }
    const requested_supplier = frm.doc.supplier;
    frappe.call({
        method: "suviner.party_balance.get_party_balance",
        args: {
            party_type: "Supplier",
            party: requested_supplier,
            company: frm.doc.company,
            date: frm.doc.posting_date,
        },
        callback(r) {
            const m = r.message;
            if (!m || frm.doc.supplier !== requested_supplier) return;
            suviner_pi_set_balance(frm, m.balance, m.message);
        },
    });
}

// Qiymatni dirty-belgisiz yozish (Kassa'dagi set_derived_value uslubi).
function suviner_pi_set_balance(frm, value, message) {
    if (frm.doc.custom_party_balance !== value) {
        frm.doc.custom_party_balance = value;
        frm.refresh_field("custom_party_balance");
    }
    frm.set_df_property("custom_party_balance", "description",
        frappe.utils.escape_html(message || ""));
}

// ─── Kurs-taxtasi: dop-rasxod ochilganda kiritilgan kurslarni ko'rsatadi ───
// (Currency Exchange'dagi har juftlikning eng oxirgisi; dinamik — yangi
// valyuta kiritilsa o'zi chiqadi.)
frappe.ui.form.on("Purchase Invoice", {
    onload_post_render(frm) {
        suviner_render_kurs_board(frm);
    },
    custom_dop_rasxod(frm) {
        suviner_render_kurs_board(frm);
    },
    posting_date(frm) {
        suviner_render_kurs_board(frm);
    },
});

function suviner_render_kurs_board(frm) {
    if (!frm.doc.custom_dop_rasxod) return;
    const field = frm.get_field("custom_kurs_html");
    if (!field) return;
    const requested_date = frm.doc.posting_date || frappe.datetime.get_today();
    frappe.call({
        method: "suviner.currency_rates.get_latest_exchange_rates",
        // Hujjat sanasiga ko'ra: keyin ochilganda ham o'sha kungi kurslar.
        args: { company: frm.doc.company, date: requested_date },
        callback(r) {
            const m = r.message;
            // Javob kelguncha sana o'zgargan bo'lsa — eskirgan taxtani chizmaymiz.
            if (!m || (frm.doc.posting_date || frappe.datetime.get_today()) !== requested_date) return;
            if (!m.rates.length) {
                field.$wrapper.html(
                    `<div class="text-muted" style="font-size:12px;">` +
                    `Currency Exchange'да курс киритилмаган</div>`
                );
                return;
            }
            const rows = m.rates.map((x) => {
                const rate = format_number(x.exchange_rate, null,
                    x.exchange_rate >= 100 ? 2 : 4);
                return `<tr>
                    <td style="padding:3px 8px;font-weight:600;white-space:nowrap;">
                        1 ${frappe.utils.escape_html(x.from_currency)}</td>
                    <td style="padding:3px 4px;color:var(--text-muted);">=</td>
                    <td style="padding:3px 8px;text-align:right;font-weight:600;white-space:nowrap;">
                        ${rate} ${frappe.utils.escape_html(x.to_currency)}</td>
                    <td style="padding:3px 8px;color:var(--text-muted);font-size:11px;white-space:nowrap;">
                        ${frappe.datetime.str_to_user(x.date)}</td>
                </tr>`;
            }).join("");
            field.$wrapper.html(
                `<div style="border:1px solid var(--border-color);border-radius:8px;
                        padding:8px 6px;background:var(--control-bg);">
                    <div style="font-size:11px;letter-spacing:.5px;text-transform:uppercase;
                            color:var(--text-muted);padding:0 8px 6px;">Валюта курслари — ${frappe.datetime.str_to_user(frm.doc.posting_date || frappe.datetime.get_today())} ҳолатига</div>
                    <table style="border-collapse:collapse;font-size:13px;">${rows}</table>
                </div>`
            );
        },
    });
}

// ─── Create > Payment o'rniga Kassa ───────────────────────────────────────
frappe.ui.form.on("Purchase Invoice", {
    refresh(frm) {
        suviner_pi_kassa_button(frm);
    },
});

function suviner_pi_kassa_button(frm) {
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
