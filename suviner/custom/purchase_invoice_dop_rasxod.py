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
			"label": "Распределение расходов (по умолчанию)",
			"fieldtype": "Select",
			"options": "Qty\nAmount\nKg",
			"default": "Amount",
			"insert_after": "custom_dop_rasxod_section",
			"depends_on": "eval:doc.custom_dop_rasxod",
			"description": "Ишлатилади, агар харажат қаторида ўз усули танланмаган бўлса. Kg — товар оғирлиги бўйича (Кг × Кол-во).",
		},
		{
			# Taqsimlash-usuli tanlovining o'ng yonidagi bo'sh joy uchun.
			"fieldname": "custom_dop_rasxod_cb",
			"fieldtype": "Column Break",
			"insert_after": "custom_distribute_charges_based_on",
		},
		{
			# Bank-uslubidagi jonli kurs-taxtasi (JS to'ldiradi:
			# suviner.currency_rates.get_latest_exchange_rates).
			"fieldname": "custom_kurs_html",
			"label": "Валюта курслари",
			"fieldtype": "HTML",
			"insert_after": "custom_dop_rasxod_cb",
			"depends_on": "eval:doc.custom_dop_rasxod",
		},
		{
			# Ustunlar tugadi — jadval TO'LIQ kenglikda bo'lishi uchun yangi
			# (chegarasiz) qator-bo'limi. Busiz jadval o'ng ustunga siqilib qoladi.
			"fieldname": "custom_dop_rasxod_table_sb",
			"fieldtype": "Section Break",
			"hide_border": 1,
			"insert_after": "custom_kurs_html",
			"depends_on": "eval:doc.custom_dop_rasxod",
		},
		{
			"fieldname": "custom_dop_rasxod_items",
			"label": "Доп. расходлар",
			"fieldtype": "Table",
			"options": "Suviner Dop Rasxod",
			"insert_after": "custom_dop_rasxod_table_sb",
			"depends_on": "eval:doc.custom_dop_rasxod",
		},
	],
	# Dop-rasxod qarzdorlik-JE'sini manba PI'ga bog'laydigan maydon (dashboard
	# Connections'da ko'rinishi va bekor qilishda topish uchun).
	"Journal Entry": [
		{
			"fieldname": "custom_source_purchase_invoice",
			"label": "Purchase Invoice",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"insert_after": "user_remark",
			"read_only": 1,
			"no_copy": 1,
			"print_hide": 1,
		},
	],
	# LCV soliq-qatorini uni yaratgan Доп. расход qatoriga bog'laydigan iz —
	# Sebestoimost reporti aynan qaysi rasxod qaysi tovarga qancha tushganini
	# taxminlarsiz, avtoritativ ko'rsatishi uchun.
	"Landed Cost Taxes and Charges": [
		{
			"fieldname": "custom_dop_rasxod_row",
			"label": "Доп. расход қатори (ички калит)",
			"fieldtype": "Data",
			"insert_after": "amount",
			"read_only": 1,
			"hidden": 1,
		},
		{
			"fieldname": "custom_distribution_basis",
			"label": "Тақсимлаш усули",
			"fieldtype": "Data",
			"insert_after": "custom_dop_rasxod_row",
			"read_only": 1,
		},
	],
}


# ERPNext'ning standart Purchase Invoice Item.weight_per_unit maydonini item
# jadvalida ko'rsatamiz (custom field emas — Item kartochkasidagi weight_per_unit
# qiymati get_item_details orqali avtomatik tortiladi, shuning uchun standart
# maydon afzal). Kg bo'yicha taqsimlash shu maydonga tayanadi.
WEIGHT_PROPERTY_SETTERS = [
	# (fieldname, property, value, property_type)
	("weight_per_unit", "in_list_view", "1", "Check"),
	("weight_per_unit", "columns", "1", "Int"),
	("weight_per_unit", "label", "Кг (за ед.)", "Data"),
	("weight_per_unit", "description", "Оғирлиги (кг) 1 дона учун. Умумийси: Кг × Кол-во. Item карточкасида weight_per_unit тўлдирилса — автоматик чиқади.", "Small Text"),
]


def execute():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)

	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	for fieldname, prop, value, prop_type in WEIGHT_PROPERTY_SETTERS:
		# make_property_setter avval eskisini o'chiradi — idempotent.
		make_property_setter(
			"Purchase Invoice Item",
			fieldname,
			prop,
			value,
			prop_type,
			validate_fields_for_doctype=False,
		)
