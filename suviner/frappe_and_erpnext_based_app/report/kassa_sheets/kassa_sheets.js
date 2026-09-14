frappe.query_reports["Kassa Sheets"] = {
    onload: function(report) {
        // Bu report doim TO'LIQ kenglikda ochilsin (ikki yon bo'sh qolmasin).
        // Faqat shu sahifa konteyneriga ta'sir qiladi — global sozlamaga tegmaydi.
        $(report.page.wrapper).closest(".container").css({
            "max-width": "100%",
            "width": "100%",
        });
    },

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
            "fieldname": "from_date",
            "label": __("Сана дан"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("Сана гача"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "transaction_type",
            "label": __("Тип операции"),
            "fieldtype": "MultiSelectList",
            get_data: function(txt) {
                return ["Приход", "Расход", "Перемещения", "Конвертация"]
                    .filter(v => !txt || v.toLowerCase().includes(txt.toLowerCase()))
                    .map(v => ({ value: v, description: "" }));
            }
        },
        {
            "fieldname": "mode_of_payment",
            "label": __("Касса (способ оплаты)"),
            "fieldtype": "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_link_options("Mode of Payment", txt);
            }
        },
        {
            "fieldname": "currency",
            "label": __("Валюта"),
            "fieldtype": "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_link_options("Currency", txt, { enabled: 1 });
            }
        },
        {
            "fieldname": "party_type",
            "label": __("Тип контрагента"),
            "fieldtype": "MultiSelectList",
            get_data: function(txt) {
                return ["Customer", "Supplier", "Shareholder", "Employee", "Расходы"]
                    .filter(v => !txt || v.toLowerCase().includes(txt.toLowerCase()))
                    .map(v => ({ value: v, description: "" }));
            }
        },
        {
            "fieldname": "party",
            "label": __("Контрагент (номи)"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "include_drafts",
            "label": __("Черновиклар ҳам"),
            "fieldtype": "Check",
            "default": 0
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        if (column.fieldname == "prixod" && data.prixod) {
            value = `<span style="color:#1e7e34;font-weight:600;">${value}</span>`;
        }
        if (column.fieldname == "rasxod" && data.rasxod) {
            value = `<span style="color:#b02a37;font-weight:600;">${value}</span>`;
        }
        if (column.fieldname == "transaction_type" && value) {
            const colors = {
                "Приход": "#1e7e34",
                "Расход": "#b02a37",
                "Перемещения": "#2980b9",
                "Конвертация": "#8e44ad"
            };
            const c = colors[data.transaction_type] || "#555";
            value = `<span style="color:${c};font-weight:600;">${value}</span>`;
        }
        if (column.fieldname == "status" && data.docstatus === 0) {
            value = `<span style="color:#b8860b;">${value}</span>`;
        }
        return value;
    }
};
