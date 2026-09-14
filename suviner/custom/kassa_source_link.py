# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""Kassa yaratgan Payment Entry / Journal Entry'larda manba-Kassa'ga
BOSILADIGAN havola (Cheque/Reference No matn edi — link emas).
create_custom_fields idempotent."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

_FIELD = {
	"fieldname": "custom_source_kassa",
	"label": "Касса",
	"fieldtype": "Link",
	"options": "Kassa",
	"insert_after": "mode_of_payment",
	"read_only": 1,
	"no_copy": 1,
	"print_hide": 1,
	"depends_on": "eval:doc.custom_source_kassa",
}

CUSTOM_FIELDS = {
	"Payment Entry": [dict(_FIELD)],
	"Journal Entry": [{**_FIELD, "insert_after": "cheque_date"}],
}


def execute():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
