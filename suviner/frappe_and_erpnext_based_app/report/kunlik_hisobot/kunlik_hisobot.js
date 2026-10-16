frappe.query_reports["Kunlik Hisobot"] = {
    onload: function(report) {
        // Hisobot to'liq kenglikda ochilsin
        $(report.page.wrapper).closest(".container").css({
            "max-width": "100%",
            "width": "100%",
        });
    },

    "filters": [
        {
            "fieldname": "company",
            "label": __("Kompaniya"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company"),
            "reqd": 1
        },
        {
            "fieldname": "from_date",
            "label": __("Sanadan"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("Sanagacha"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "transaction_type",
            "label": __("Turi"),
            "fieldtype": "MultiSelectList",
            get_data: function(txt) {
                return ["Sotuv", "Qaytarish", "Prixod", "Rasxod", "Peremesheniya", "Konvertatsiya"]
                    .filter(v => !txt || v.toLowerCase().includes(txt.toLowerCase()))
                    .map(v => ({ value: v, description: "" }));
            }
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        if (column.fieldname == "kirim" && data.kirim) {
            value = `<span style="color:#1e7e34;font-weight:600;">${value}</span>`;
        }
        if (column.fieldname == "chiqim" && data.chiqim) {
            value = `<span style="color:#b02a37;font-weight:600;">${value}</span>`;
        }
        if (column.fieldname == "tx_type" && value) {
            const colors = {
                "Sotuv": "#1e7e34",
                "Qaytarish": "#d35400",
                "Prixod": "#1e7e34",
                "Rasxod": "#b02a37",
                "Peremesheniya": "#2980b9",
                "Konvertatsiya": "#8e44ad"
            };
            const c = colors[data.tx_type] || "#555";
            value = `<span style="color:${c};font-weight:600;">${value}</span>`;
        }
        return value;
    }
};
