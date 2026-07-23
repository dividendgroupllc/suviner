# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""
Purchase Invoice "Доп. расход" (Landed Cost) oqimi.

- validate:  har bir доп-расход qatori uchun valyuta / kurs / baz. summani to'ldiradi
             va LCV ishlashi uchun "Update Stock"ni majburiy yoqadi.
- on_submit: Purchase Invoice submit bo'lgach avtomatik Landed Cost Voucher
             yaratadi, item'larni PI'dan tortadi, доп-расходларни LCV "taxes"
             jadvaliga ko'chiradi va submit qiladi.
- on_cancel: PI cancel qilinganda unga bog'liq LCV(lar)ni avval cancel qiladi
             (back-link tekshiruvidan oldin ishlaydi).
"""

import frappe
from frappe import _
from frappe.utils import flt
from erpnext.setup.utils import get_exchange_rate


def _has_dop_rasxod(doc):
	return bool(doc.get("custom_dop_rasxod")) and bool(doc.get("custom_dop_rasxod_items"))


def validate(doc, method=None):
	if not doc.get("custom_dop_rasxod"):
		return

	# Landed Cost Voucher faqat "Update Stock" yoqilgan PI bilan ishlaydi.
	if not doc.update_stock:
		doc.update_stock = 1
		frappe.msgprint(
			_("«Доп. расход» белгиланган — Landed Cost учун «Update Stock» автоматик ёқилди."),
			indicator="orange",
			alert=True,
		)

	company_currency = frappe.get_cached_value("Company", doc.company, "default_currency")

	for row in doc.get("custom_dop_rasxod_items") or []:
		if not row.currency:
			row.currency = (
				frappe.db.get_value("Supplier", row.supplier, "default_currency")
				or company_currency
			)

		if row.currency == company_currency:
			row.exchange_rate = 1
		elif not row.exchange_rate:
			row.exchange_rate = (
				get_exchange_rate(row.currency, company_currency, doc.posting_date) or 1
			)

		row.base_amount = flt(
			flt(row.amount) * flt(row.exchange_rate), row.precision("base_amount")
		)


def on_submit(doc, method=None):
	if not doc.get("custom_dop_rasxod"):
		return

	if not doc.get("custom_dop_rasxod_items"):
		frappe.throw(_("«Доп. расход» белгиланган, лекин харажат қаторлари киритилмаган."))

	create_landed_cost_voucher(doc)


def create_landed_cost_voucher(doc):
	"""PI submit bo'lgach Landed Cost Voucher yaratib submit qiladi."""

	# Bitta PI uchun ikki marta yaratilmasin (amend/qayta submit holatlari uchun).
	existing = frappe.db.exists(
		"Landed Cost Purchase Receipt",
		{
			"receipt_document_type": "Purchase Invoice",
			"receipt_document": doc.name,
			"docstatus": 1,
		},
	)
	if existing:
		return

	company_currency = frappe.get_cached_value("Company", doc.company, "default_currency")

	lcv = frappe.new_doc("Landed Cost Voucher")
	lcv.company = doc.company
	lcv.posting_date = doc.posting_date
	lcv.distribute_charges_based_on = doc.get("custom_distribute_charges_based_on") or "Amount"

	lcv.append(
		"purchase_receipts",
		{
			"receipt_document_type": "Purchase Invoice",
			"receipt_document": doc.name,
			"supplier": doc.supplier,
			"posting_date": doc.posting_date,
			"grand_total": doc.base_grand_total,
		},
	)

	lcv.get_items_from_purchase_receipts()

	for row in doc.custom_dop_rasxod_items:
		# Summa kompaniya валютасига ўтказилган (base_amount) ҳолда узатилади,
		# шунинг учун account_currency = company_currency, exchange_rate = 1.
		lcv.append(
			"taxes",
			{
				"expense_account": row.expense_account,
				"description": (
					f"{row.supplier}: {row.description}" if row.description else row.supplier
				),
				"amount": flt(row.base_amount),
				"account_currency": company_currency,
				"exchange_rate": 1,
			},
		)

	lcv.flags.ignore_permissions = True
	lcv.insert()
	lcv.submit()

	frappe.msgprint(
		_("Landed Cost Voucher {0} яратилди ва submit қилинди.").format(
			frappe.utils.get_link_to_form("Landed Cost Voucher", lcv.name)
		),
		indicator="green",
		alert=True,
	)


def on_cancel(doc, method=None):
	if not doc.get("custom_dop_rasxod"):
		return

	# PI'ga bog'liq submitted LCV'larni avval cancel qilamiz, aks holda
	# back-link tekshiruvi PI cancel'ini bloklaydi.
	links = frappe.get_all(
		"Landed Cost Purchase Receipt",
		filters={
			"receipt_document_type": "Purchase Invoice",
			"receipt_document": doc.name,
		},
		pluck="parent",
	)

	for lcv_name in set(links):
		lcv = frappe.get_doc("Landed Cost Voucher", lcv_name)
		if lcv.docstatus == 1:
			lcv.flags.ignore_permissions = True
			lcv.cancel()
