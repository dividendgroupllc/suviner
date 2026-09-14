# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""Eski (maydon qo'shilishidan avval yaratilgan) PE/JE'larda custom_source_kassa
ni to'ldiradi. Manba — Kassa.linked_entry (avtoritativ) + zaxira sifatida
reference_no/cheque_no dagi KASSA-nomi. Informatsion maydon — GL'ga ta'sir yo'q."""

import frappe


def execute():
	for dt, ref_field in (("Payment Entry", "reference_no"), ("Journal Entry", "cheque_no")):
		if not frappe.db.has_column(dt, "custom_source_kassa"):
			continue

		# 1) Avtoritativ: Kassa -> linked_entry
		frappe.db.sql(f"""
			update `tab{dt}` t
			join `tabKassa` k on k.linked_doctype = %s and k.linked_entry = t.name
			set t.custom_source_kassa = k.name
			where ifnull(t.custom_source_kassa, '') = ''
		""", dt)

		# 2) Zaxira: reference/cheque'da Kassa nomi yozilgan bo'lsa
		frappe.db.sql(f"""
			update `tab{dt}` t
			join `tabKassa` k on k.name = t.{ref_field}
			set t.custom_source_kassa = k.name
			where ifnull(t.custom_source_kassa, '') = ''
		""")
