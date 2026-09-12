# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""SI/PI'dagi "Create > Касса" tugmasi uchun tayyor Kassa-hujjat.

frappe.route_options yangi hujjatga qiymatlarni ishonchsiz olib borardi
(read-only/depends_on maydonlarda yo'qolish holatlari) — shuning uchun
yadroning make_payment_entry naqshi: hujjatni server to'liq tayyorlaydi,
klient frappe.model.sync bilan ochadi. Hech narsa saqlanmaydi — kassir
kassani (mode_of_payment) tanlab o'zi saqlaydi.
"""

import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def make_kassa(doctype, name):
	if doctype not in ("Sales Invoice", "Purchase Invoice"):
		frappe.throw(_("Qo'llab-quvvatlanmaydigan hujjat turi: {0}").format(doctype))

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	outstanding = flt(doc.outstanding_amount)

	kassa = frappe.new_doc("Kassa")
	kassa.company = doc.company
	kassa.against_invoice_doctype = doctype
	kassa.against_invoice = doc.name
	kassa.date = frappe.utils.nowdate()
	kassa.time = frappe.utils.nowtime()
	kassa.amount = abs(outstanding)

	if doctype == "Sales Invoice":
		# Mijoz bizga to'laydi -> Приход; qaytarish (manfiy qoldiq) -> Расход
		kassa.transaction_type = "Приход" if outstanding >= 0 else "Расход"
		kassa.party_type = "Customer"
		kassa.party = doc.customer
		kassa.party_name = doc.customer_name or doc.customer
		kassa.remarks = f"Оплата по счету {doc.name}"
	else:
		# Biz ta'minotchiga to'laymiz -> Расход; qaytarish -> Приход
		kassa.transaction_type = "Расход" if outstanding >= 0 else "Приход"
		kassa.party_type = "Supplier"
		kassa.party = doc.supplier
		kassa.party_name = doc.supplier_name or doc.supplier
		kassa.remarks = f"Оплата поставщику по счету {doc.name}"

	return kassa
