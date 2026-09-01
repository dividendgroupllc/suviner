frappe.query_reports["Tannarx Shakllanishi"] = {
    "tree": true,
    "name_field": "component",
    "parent_field": "parent_component",
    "initial_depth": 2,

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
            "fieldname": "supplier",
            "label": __("Таъминотчи (асосий)"),
            "fieldtype": "Link",
            "options": "Supplier"
        },
        {
            "fieldname": "item",
            "label": __("Товар"),
            "fieldtype": "Link",
            "options": "Item"
        },
        {
            "fieldname": "dop_rasxod_supplier",
            "label": __("Доп. расход таъминотчиси"),
            "fieldtype": "Link",
            "options": "Supplier"
        },
        {
            "fieldname": "only_with_dop_rasxod",
            "label": __("Фақат Доп. расходли ҳужжатлар"),
            "fieldtype": "Check",
            "default": 0
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldtype == "Currency" && value) {
            value = value.replace(/\$/g, '');
        }

        if (!data) return value;

        // L0 (tovar qatori) — qalin; komponent yig'indisi mos kelmasa qizil ogohlantirish
        if (data.indent === 0) {
            if (["component", "amount", "per_unit"].includes(column.fieldname)) {
                value = `<span style="font-weight: 600;">${value}</span>`;
            }
            if (column.fieldname == "component" && Math.abs(data.farq || 0) >= 0.01) {
                value = `<span style="color:#c0392b;">⚠ ${value}</span>`;
            }
        }

        // L1 komponent qatorlari — usul belgisi rangli
        if (data.indent === 1 && column.fieldname == "basis" && value) {
            const colors = { "Qty": "#2980b9", "Amount": "#27ae60", "Kg": "#8e44ad" };
            const c = colors[data.basis] || "#7f8c8d";
            value = `<span style="color:${c}; font-weight:600;">${value}</span>`;
        }

        return value;
    }
}
