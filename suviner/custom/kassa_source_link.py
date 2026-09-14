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
	# Transaction ID bo'limida, Cheque/Reference yonida tursin — foydalanuvchi
	# Kassa raqamini aynan shu yerda ko'radi va bosishni shu yerda kutadi.
	"Payment Entry": [{**_FIELD, "insert_after": "reference_date"}],
	"Journal Entry": [{**_FIELD, "insert_after": "cheque_date"}],
}


def execute():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)

	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	# Kassa'dan kelgan hujjatda raqam ikki marta ko'rinmasin: link («Касса»)
	# bor bo'lsa matnli Cheque/Reference yashirinadi; qo'lda kiritilgan
	# PE/JE'larda (link bo'sh) avvalgidek ko'rinadi.
	for dt, fieldname in (("Payment Entry", "reference_no"), ("Journal Entry", "cheque_no")):
		make_property_setter(
			dt,
			fieldname,
			"depends_on",
			"eval:!doc.custom_source_kassa",
			"Data",
			validate_fields_for_doctype=False,
		)
