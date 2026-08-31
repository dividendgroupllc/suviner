frappe.query_reports["Sebestoimost Tovara"] = {
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

        // Bir xil itemning ikkinchi va keyingi Доп. расход qatorlarida
        // item darajasidagi (takrorlangan) qiymatlarni kamroq ko'zga
        // tashlanadigan qilib ko'rsatish — bu sof kosmetik, qiymatning
        // o'zini o'zgartirmaydi.
        const item_level_fields = [
            "posting_date", "purchase_invoice", "company", "supplier",
            "item_code", "item_name", "qty", "stock_uom",
            "base_net_amount", "item_tax_amount", "landed_cost_voucher_amount",
            "total_cost_value", "valuation_rate"
        ];
        if (data && data.is_item_repeat && item_level_fields.includes(column.fieldname)) {
            value = `<span style="color: #bbb;">${value}</span>`;
        }

        if (column.fieldname == "item_share_of_row" && value) {
            value = `<span style="font-weight: 600;">${value}</span>`;
        }

        return value;
    }
}
