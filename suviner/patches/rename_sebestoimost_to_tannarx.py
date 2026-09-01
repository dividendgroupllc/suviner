# "Sebestoimost Tovara" reporti "Tannarx Shakllanishi" deb qayta nomlandi
# (2026-09-01). Fayllar yangi nom bilan sinxronlanadi; bu patch saytdagi ESKI
# Report hujjatini yangi nomga ko'chiradi (yangi allaqachon yaratilgan bo'lsa —
# eskisini o'chiradi), aks holda ro'yxatda buzuq eski yozuv qolib ketadi.

import frappe

OLD = "Sebestoimost Tovara"
NEW = "Tannarx Shakllanishi"


def execute():
	if not frappe.db.exists("Report", OLD):
		return

	if frappe.db.exists("Report", NEW):
		frappe.delete_doc("Report", OLD, force=True, ignore_permissions=True)
	else:
		frappe.rename_doc("Report", OLD, NEW, force=True)
