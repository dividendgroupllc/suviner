# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""
Purchase Invoice'ga "Доп. расход" (Landed Cost) custom field'larini qo'shadi.

create_custom_fields idempotent — bir necha marta chaqirilsa ham xavfsiz,
shuning uchun patch va after_install'da ishlatsa bo'ladi.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Purchase Invoice": [
		{
			"fieldname": "custom_dop_rasxod",
			"label": "Доп. расход",
			"fieldtype": "Check",
			"insert_after": "base_tax_withholding_net_total",
			"description": "Дополнительные расходы (Landed Cost) киритиш учун белгиланг",
		},
		{
			"fieldname": "custom_dop_rasxod_section",
			"label": "Дополнительные расходы",
			"fieldtype": "Section Break",
			"insert_after": "custom_dop_rasxod",
			"depends_on": "eval:doc.custom_dop_rasxod",
		},
		{
			"fieldname": "custom_distribute_charges_based_on",
			"label": "Distribute Charges Based On",
			"fieldtype": "Select",
			"options": "Qty\nAmount\nDistribute Manually",
			"default": "Amount",
			"insert_after": "custom_dop_rasxod_section",
			"depends_on": "eval:doc.custom_dop_rasxod",
		},
		{
			"fieldname": "custom_dop_rasxod_items",
			"label": "Доп. расходлар",
			"fieldtype": "Table",
			"options": "Suviner Dop Rasxod",
			"insert_after": "custom_distribute_charges_based_on",
			"depends_on": "eval:doc.custom_dop_rasxod",
		},
	]
}


def execute():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
