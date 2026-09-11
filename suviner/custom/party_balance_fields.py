# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""Kontragent qoldig'i uchun read-only maydonlar.

Sales Invoice (customer ostida), Purchase Invoice (supplier ostida) va
Journal Entry Account qatorida (party ostida) — kontragent tanlanganda
JS suviner.party_balance.get_party_balance natijasini shu maydonlarga yozadi.
Kassa'da bunday maydon doctype'ning o'zida bor (party_balance).

Ishora: musbat — kontragent bizga qarzdor; manfiy — biz qarzdormiz.
create_custom_fields idempotent — patch/qo'lda qayta chaqirish xavfsiz.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

_COMMON = {
	"fieldname": "custom_party_balance",
	"label": "Остаток контрагента",
	"fieldtype": "Currency",
	# Valyuta belgisi kontragent hisobining valyutasidan (yonidagi yashirin
	# maydon, JS to'ldiradi) — aks holda desk doim kompaniya valyutasini chizadi.
	"options": "custom_party_balance_currency",
	"read_only": 1,
	"no_copy": 1,
	"print_hide": 1,
	"description": "Мусбат — контрагент бизга қарздор; манфий — биз қарздормиз",
}

_CURRENCY = {
	"fieldname": "custom_party_balance_currency",
	"label": "Валюта остатка (ички)",
	"fieldtype": "Data",
	"hidden": 1,
	"read_only": 1,
	"no_copy": 1,
	"print_hide": 1,
	"insert_after": "custom_party_balance",
}

CUSTOM_FIELDS = {
	"Sales Invoice": [
		{**_COMMON, "insert_after": "customer", "depends_on": "eval:doc.customer"},
		dict(_CURRENCY),
	],
	"Purchase Invoice": [
		{**_COMMON, "insert_after": "supplier", "depends_on": "eval:doc.supplier"},
		dict(_CURRENCY),
	],
	"Journal Entry Account": [
		{
			**_COMMON,
			"insert_after": "party",
			"depends_on": "eval:doc.party",
			# Child-jadvalning O'ZIDA ustun bo'lib ko'rinsin (user talabi).
			"in_list_view": 1,
			"columns": 1,
		},
		dict(_CURRENCY),
	],
}


def execute():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)

	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	# JE grid ustun-byudjeti to'la (12/11) — kam ishlatiladigan reference_name
	# ustunini grid'dan olamiz (qator formida qoladi), qoldiq-ustun sig'sin.
	make_property_setter(
		"Journal Entry Account",
		"reference_name",
		"in_list_view",
		"0",
		"Check",
		validate_fields_for_doctype=False,
	)

	# Payment Entry qoldiqlari Accounts Settings'dagi ikki bayroqqa bog'liq —
	# o'chiq bo'lsa yadro jimgina 0 qaytaradi. Yoqib qo'yamiz.
	import frappe

	frappe.db.set_single_value("Accounts Settings", "show_party_balance", 1)
	frappe.db.set_single_value("Accounts Settings", "show_account_balance", 1)

	# Payment Entry'da yadroning O'Z party_balance maydoni bor va kontragent
	# tanlanganda o'zi to'ladi (ishora qoidasi bizniki bilan bir xil) —
	# faqat nom/izohni boshqa hujjatlar bilan bir xillashtiramiz.
	for prop, value, ptype in (
		("label", "Остаток контрагента", "Data"),
		("description", "Мусбат — контрагент бизга қарздор; манфий — биз қарздормиз", "Small Text"),
	):
		make_property_setter(
			"Payment Entry",
			"party_balance",
			prop,
			value,
			ptype,
			validate_fields_for_doctype=False,
		)
