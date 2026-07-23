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
