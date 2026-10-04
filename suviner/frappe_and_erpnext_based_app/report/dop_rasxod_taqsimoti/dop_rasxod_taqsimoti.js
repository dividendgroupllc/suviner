// Copyright (c) 2026, Sardorbek Qamchibekov and contributors
// For license information, please see license.txt

frappe.query_reports["Dop Rasxod Taqsimoti"] = {
    "tree": true,
    "name_field": "partiya",
    "parent_field": "parent_partiya",
    "initial_depth": 1,

    "filters": [
        {
            "fieldname": "company",
            "label": __("Компания"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company"),
            "reqd": 1
        },
        {
            "fieldname": "purchase_invoice",
            "label": __("Партия (Purchase Invoice)"),
            "fieldtype": "Link",
            "options": "Purchase Invoice",
            "get_query": () => ({
                filters: { docstatus: 1, custom_dop_rasxod: 1 }
            })
        },
        {
            "fieldname": "from_date",
            "label": __("Сана дан"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "to_date",
            "label": __("Сана гача"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "supplier",
            "label": __("Таъминотчи"),
            "fieldtype": "Link",
            "options": "Supplier"
        },
        {
            // Faqat bitta partiyada: bir nechta partiya doim kompaniya valyutasida
            // (USD va UZS partiyalar bir ustunda aralashmasin).
            "fieldname": "currency_mode",
            "label": __("Ҳисобот валютаси"),
            "fieldtype": "Select",
            "options": ["Валюта счета", "Валюта компании"],
            "default": "Валюта счета",
            "depends_on": "eval:doc.purchase_invoice"
        },
        {
            "fieldname": "row_mode",
            "label": __("Товар қаторлари"),
            "fieldtype": "Select",
            "options": ["На 1 единицу", "Итого по строке"],
            "default": "На 1 единицу"
        }
    ]
};
